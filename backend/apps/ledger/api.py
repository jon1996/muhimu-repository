import hashlib
from datetime import date, datetime
from decimal import Decimal

from django.core.files.base import ContentFile
from django.db.models import Count, Prefetch, prefetch_related_objects
from django.http import HttpResponse
from django.utils import timezone
from ninja import File, Router, UploadedFile
from ninja.errors import HttpError

from apps.audit.services import record_audit
from apps.ledger.models import (
    Account,
    AccountingPeriod,
    Entry,
    EntryLine,
    EntryStatus,
    Exercise,
    FixedAsset,
    FxRate,
    InventoryCampaign,
    InventoryLine,
    InventoryStatus,
    Journal,
    SourceDocument,
    StockMethod,
    ThirdParty,
    Commitment,
)
from apps.ledger.schemas import (
    AccountAnatomyOut,
    AccountConstantOut,
    AccountFicheOut,
    AccountIn,
    AccountOut,
    AccountReadingOut,
    BalanceRowOut,
    BookLineOut,
    DocumentOut,
    EntryIn,
    EntryLineOut,
    EntryOut,
    ExerciseOut,
    GeneralLedgerOut,
    ImportReportOut,
    InventoryCampaignIn,
    InventoryCampaignOut,
    InventoryLineIn,
    InventoryLineOut,
    JournalOut,
    LedgerLineOut,
    LedgerStatusOut,
    LegalBooksOut,
    SetupIn,
    OrgSetupOut,
    NotesIn,
    PeriodOut,
    ReverseIn,
    StatementsOut,
    SmtEligibilityOut,
    AssetSuggestOut,
    DepreciateIn,
    DepreciateOut,
    FixedAssetIn,
    FixedAssetOut,
    AllocateIn,
    CloseExerciseIn,
    OpeningIn,
    OpeningPreviewOut,
    OpeningStateOut,
    OpeningLineOut,
    LetterIn,
    LetterOut,
    OpenItemOut,
    PartyIn,
    PartyOut,
    UnletterIn,
    LineDueIn,
    BankPointIn,
    BankReconOut,
    BankStatementIn,
    BankStatementLineIn,
    BankStatementLineOut,
    BankStatementOut,
    BankUnpointIn,
    OfxImportOut,
    CashCountIn,
    CashCountOut,
    CashPanelOut,
    CommitmentIn,
    CommitmentOut,
    Class9Out,
    CageAllocateIn,
    CagePanelOut,
    CageResultOut,
    CageSectionIn,
    CageSectionOut,
    CageSectionPatch,
    EscompteIn,
    EscomptePreviewOut,
    EsgIn,
    EsgOut,
    FxRateIn,
    FxRateOut,
    FxRevalueIn,
    FxRevalueOut,
    ConsolidationEliminationIn,
    ConsolidationGroupIn,
    ConsolidationGroupPatch,
    ConsolidationMemberIn,
    ConsolidationMemberPatch,
    ConsolidationOut,
    BetaScopeOut,
    dec,
)
from apps.ledger.beta_scope import (
    FEATURE_CLASS9_CAGE,
    FEATURE_CONSOLIDATION,
    FEATURE_ESG,
    FEATURE_ESCOMPTE,
    beta_scope_payload,
    is_beta_feature_enabled,
    require_beta_feature,
    require_escompte_allowed_for_entry,
)
from apps.ledger.services.balance import general_ledger, trial_balance
from apps.ledger.services.periods import it_close_period, validate_period
from apps.ledger.services.closing import allocate_result, close_exercise, closing_lines_for, preview_close, restore_pnl_rows
from apps.ledger.services.opening import (
    OPENING_TEMPLATE,
    opening_state,
    parse_opening_csv,
    parse_opening_text,
    post_opening,
    preview_opening,
)
from apps.ledger.services.notes_sn import serialize_notes
from apps.ledger.services.assets import (
    charge_for_period,
    next_reference,
    post_period_depreciation,
    resolve_account,
    serialize_asset,
    suggest_contra_codes,
    validate_asset_payload,
)
from apps.ledger.services.lettering import (
    create_party,
    letter_lines,
    open_lines,
    reference_date,
    serialize_open_item,
    serialize_party,
    set_line_due,
    unletter,
)
from apps.ledger.services.bank_rec import (
    add_statement_line,
    point_selection,
    reconciliation_payload,
    serialize_statement,
    serialize_statement_line,
    unpoint,
    upsert_statement,
    import_ofx,
)
from apps.ledger.services.cash import cash_payload, post_variance, serialize_count, upsert_count
from apps.ledger.services.escompte import close_discount_for_entry, preview_discount, sync_discount_commitment
from apps.ledger.services.commitments import (
    create_commitment,
    deactivate_commitment,
    post_commitment_class9,
    serialize_commitment,
)
from apps.ledger.services.cage import (
    allocate_cage,
    cage_panel,
    close_cage,
    create_section,
    reflect_period,
    serialize_section,
    update_section,
)
from apps.ledger.services.esg import get_report, payroll_from_rows, upsert_report
from apps.ledger.services.stocks import (
    METHOD_LABELS,
    close_inventory as close_stock_inventory,
    infer_stock_code,
)
from apps.ledger.money import parse_amount, quantize_amount
from apps.ledger.services.statements import build_statements
from apps.ledger.services.pdf_statements import STATEMENT_KINDS, pdf_filename, render_statements_pdf
from apps.ledger.services.pdf_books import BOOK_KINDS, books_filename, render_books_pdf
from apps.ledger.services.smt_map import eligibility_for
from apps.ledger.services.consolidation import (
    add_elimination,
    add_member,
    assert_group_access,
    create_group,
    group_panel,
    group_pdf,
    list_groups,
    remove_elimination,
    remove_member,
    update_group,
    update_member,
    _get_group,
)
from apps.ledger.services.import_accounts import (
    MAX_IMPORT_BYTES,
    TEMPLATE_CSV,
    apply_import,
    parse_csv,
    preview_import,
    report_to_dict,
)
from apps.ledger.services.posting import create_draft, post_entry, reverse_entry, update_draft
from apps.ledger.services.fx import (
    compute_revalue,
    post_revalue,
    serialize_rate,
    upsert_rate,
)
from apps.ledger.fiches import resolve_fiche
from apps.ledger.services.demo import initialize_ledger, initialize_organization
from apps.ledger.services.setup import ensure_company_ledger, find_parent_account
from apps.ledger.taxonomy import (
    CLASS_META,
    FAMILY_LABELS,
    LEVEL_LABELS,
    SENSE_LABELS,
    account_reading,
    code_anatomy,
    infer_level,
    normalize_code,
)
from apps.tenancy.access import require_company, require_membership, require_org_writer, require_writer

router = Router(tags=["ledger"])


def _parse_date(raw: str, field: str) -> date:
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise HttpError(400, f"Date {field} invalide (AAAA-MM-JJ).") from exc


def _exercise_out(ex: Exercise, preview: dict | None = None) -> ExerciseOut:
    p = preview or {}
    if ex.status == "closed":
        net = ex.net_result
        revenue = ex.revenue
    else:
        net = p.get("net_result", ex.net_result)
        revenue = p.get("revenue", ex.revenue)
    return ExerciseOut(
        id=str(ex.id),
        year=ex.year,
        starts_on=ex.starts_on.isoformat(),
        ends_on=ex.ends_on.isoformat(),
        status=ex.status,
        closed_on=ex.closed_on.isoformat() if ex.closed_on else None,
        approved_on=ex.approved_on.isoformat() if ex.approved_on else None,
        notes_annexes=ex.notes_annexes,
        net_result=format(net, "f"),
        revenue=format(revenue, "f"),
        legal_reserve_amount=format(ex.legal_reserve_amount, "f"),
        free_reserve_amount=format(ex.free_reserve_amount, "f"),
        retained_amount=format(ex.retained_amount, "f"),
        dividends_amount=format(ex.dividends_amount, "f"),
        result_entry_id=str(ex.result_entry_id) if ex.result_entry_id else None,
        allocation_entry_id=str(ex.allocation_entry_id) if ex.allocation_entry_id else None,
        payment_entry_id=str(ex.payment_entry_id) if ex.payment_entry_id else None,
        opening_entry_id=str(ex.opening_entry_id) if ex.opening_entry_id else None,
        suggested_legal_reserve=format(p.get("suggested_legal_reserve") or 0, "f"),
        suggested_retained=format(p.get("suggested_retained") or 0, "f"),
        blockers=p.get("blockers") or [],
        can_close=bool(p.get("can_close")),
        can_allocate=bool(p.get("can_allocate")),
    )


def _period_out(period: AccountingPeriod) -> PeriodOut:
    return PeriodOut(
        id=str(period.id),
        year=period.year,
        month=period.month,
        starts_on=period.starts_on.isoformat(),
        ends_on=period.ends_on.isoformat(),
        status=period.status,
        validated_at=period.validated_at.isoformat() if period.validated_at else None,
        it_closed_at=period.it_closed_at.isoformat() if period.it_closed_at else None,
        seal=period.seal,
    )


def _entry_out(entry: Entry) -> EntryOut:
    lines = list(entry.lines.select_related("account", "third_party", "cage_section").all())
    return EntryOut(
        id=str(entry.id),
        journal_id=str(entry.journal_id),
        journal_code=entry.journal.code,
        number=entry.number,
        number_display=entry.number_display,
        accounting_date=entry.accounting_date.isoformat(),
        value_date=entry.value_date.isoformat(),
        description=entry.description,
        document_ref=entry.document_ref,
        status=entry.status,
        period_id=str(entry.period_id),
        exercise_id=str(entry.exercise_id),
        reversed_entry_id=str(entry.reversed_entry_id) if entry.reversed_entry_id else None,
        lines=[
            EntryLineOut(
                id=str(line.id),
                account_id=str(line.account_id),
                account_code=line.account.code,
                account_label=line.account.label,
                label=line.label,
                debit=dec(line.debit),
                credit=dec(line.credit),
                third_party_id=str(line.third_party_id) if line.third_party_id else None,
                third_party_name=line.third_party.name if line.third_party_id else "",
                lettering=line.lettering,
                due_on=line.due_on.isoformat() if line.due_on else "",
                cage_section_id=str(line.cage_section_id) if line.cage_section_id else None,
                cage_section_code=line.cage_section.code if line.cage_section_id else "",
                currency_code=line.currency_code or "",
                foreign_amount=dec(line.foreign_amount),
                fx_rate=format(line.fx_rate, "f") if line.fx_rate is not None else "1",
            )
            for line in lines
        ],
        total_debit=dec(sum((line.debit for line in lines), Decimal("0"))),
        total_credit=dec(sum((line.credit for line in lines), Decimal("0"))),
    )


def _raw_lines(payload: EntryIn) -> list[dict]:
    return [
        {
            "account_id": line.account_id,
            "debit": line.debit,
            "credit": line.credit,
            "label": line.label,
            "third_party_id": line.third_party_id,
            "due_on": line.due_on,
            "cage_section_id": line.cage_section_id,
            "currency_code": line.currency_code,
            "fx_rate": line.fx_rate,
        }
        for line in payload.lines
    ]


def _account_out(account: Account, children_count: int | None = None) -> AccountOut:
    anatomy = code_anatomy(account.code)
    reading = account_reading(account.code)
    family_label = FAMILY_LABELS.get(account.family) or CLASS_META.get(account.account_class, {}).get(
        "family_label", ""
    )
    return AccountOut(
        id=str(account.id),
        code=account.code,
        label=account.label,
        account_class=account.account_class,
        level=account.level,
        level_label=LEVEL_LABELS.get(account.level, account.level),
        family=account.family,
        family_label=family_label,
        sense=account.sense,
        sense_label=SENSE_LABELS.get(account.sense, account.sense),
        is_postable=account.is_postable,
        is_collective=account.is_collective,
        is_syscohada=account.is_syscohada,
        notes=account.notes,
        parent_id=str(account.parent_id) if account.parent_id else None,
        parent_code=account.parent.code if getattr(account, "parent", None) else None,
        children_count=children_count if children_count is not None else getattr(account, "children_count", 0),
        anatomy=AccountAnatomyOut(
            class_code=anatomy["class"],
            two_digit=anatomy["two_digit"],
            principal=anatomy["principal"],
            divisionary=anatomy["divisionary"],
            entity=anatomy["entity"],
            subclass=anatomy["subclass"],
            secondary=anatomy["secondary"],
            auxiliary=anatomy["auxiliary"],
        ),
        reading=AccountReadingOut(
            constants=[
                AccountConstantOut(kind=item["kind"], title=item["title"], detail=item["detail"])
                for item in reading["constants"]
            ],
            parallel_code=reading["parallel_code"],
            parallel_label=reading["parallel_label"],
            parallel_kind=reading["parallel_kind"],
        ),
    )


def _read_import_file(uploaded: UploadedFile) -> bytes:
    content = uploaded.read()
    if not content:
        raise HttpError(400, "Fichier CSV vide.")
    if len(content) > MAX_IMPORT_BYTES:
        raise HttpError(400, "Fichier trop volumineux (2 Mo maximum).")
    return content


def _current_period(company):
    today = timezone.localdate()
    return AccountingPeriod.objects.filter(
        company=company, starts_on__lte=today, ends_on__gte=today
    ).first()


@router.post("/ledger/setup", response=LedgerStatusOut)
def setup_ledger(request, payload: SetupIn):
    _, _, company = require_writer(request)
    result = initialize_ledger(company, with_demo=payload.with_demo, user=request.user)
    record_audit(
        request,
        action="ledger.setup",
        resource_type="company",
        resource_id=str(company.id),
        company=company,
        metadata={"setup_data": result["setup_data"], "seeded": result["seeded"]},
    )
    return _status(company)


@router.post("/ledger/setup-organization", response=OrgSetupOut)
def setup_organization(request, payload: SetupIn):
    org, _ = require_org_writer(request)
    result = initialize_organization(org, with_demo=payload.with_demo, user=request.user)
    record_audit(
        request,
        action="ledger.setup.organization",
        resource_type="organization",
        resource_id=str(org.id),
        organization=org,
        metadata={"setup_data": result["setup_data"], "seeded": result["seeded"]},
    )
    return OrgSetupOut(
        id=str(org.id),
        slug=org.slug,
        type=org.type,
        setup_data=result["setup_data"],
        seeded=result["seeded"],
        companies=result["companies"],
        already=result["already"],
    )


@router.get("/ledger/status", response=LedgerStatusOut)
def ledger_status(request):
    _, _, company = require_company(request)
    if not Account.objects.filter(company=company).exists():
        return _status(company, ready=False)
    return _status(company)


def _status(company, ready: bool = True) -> LedgerStatusOut:
    today = timezone.localdate()
    exercise = Exercise.objects.filter(company=company, year=today.year).first()
    period = _current_period(company)
    org_choice = getattr(company.organization, "setup_data", "") or ""
    return LedgerStatusOut(
        ready=ready,
        exercise=_exercise_out(exercise) if exercise else None,
        current_period=_period_out(period) if period else None,
        accounts=Account.objects.filter(company=company).count(),
        journals=Journal.objects.filter(company=company).count(),
        setup_data=org_choice or (company.setup_data or ""),
        needs_choice=not bool(org_choice or company.setup_data),
        entries=Entry.objects.filter(company=company).count(),
    )


@router.get("/ledger/accounts", response=list[AccountOut])
def list_accounts(request, postable: bool | None = None):
    _, _, company = require_company(request)
    qs = (
        Account.objects.filter(company=company, is_active=True)
        .select_related("parent")
        .annotate(children_count=Count("children"))
    )
    if postable is True:
        qs = qs.filter(is_postable=True)
    return [_account_out(account) for account in qs]


@router.get("/ledger/accounts/fiche", response=AccountFicheOut)
def get_account_fiche(request, code: str):
    require_company(request)
    fiche = resolve_fiche(code)
    if not fiche:
        raise HttpError(404, "Aucune fiche officielle pour ce compte.")
    return fiche


@router.post("/ledger/accounts", response=AccountOut)
def create_account(request, payload: AccountIn):
    _, _, company = require_writer(request)
    code = normalize_code(payload.code)
    if not code or code[0] not in "12345678":
        raise HttpError(400, "Le code doit commencer par une classe SYSCOHADA (1 à 9).")
    if infer_level(code) == "class":
        raise HttpError(400, "Les classes 1 à 9 sont déjà fournies par le PCGO.")
    if Account.objects.filter(company=company, code=code).exists():
        raise HttpError(409, f"Le compte {code} existe déjà.")
    label = payload.label.strip()
    if not label:
        raise HttpError(400, "Intitulé manquant.")
    parent = find_parent_account(company, code)
    if parent is None:
        raise HttpError(400, "Aucun compte parent dans le plan. Créez d’abord la sous-classe ou le principal.")
    account = Account(
        organization=company.organization,
        company=company,
        code=code,
        label=label,
        notes=payload.notes[:255],
        parent=parent,
        is_syscohada=False,
    )
    account.apply_taxonomy()
    if payload.is_postable is not None:
        account.is_postable = payload.is_postable and account.level != "class"
    account.save()
    record_audit(
        request,
        action="ledger.account.create",
        resource_type="account",
        resource_id=str(account.id),
        company=company,
        metadata={"code": account.code, "level": account.level},
    )
    return _account_out(account)


@router.delete("/ledger/accounts/{account_id}")
def delete_account(request, account_id: str):
    _, _, company = require_writer(request)
    account = Account.objects.filter(company=company, id=account_id).first()
    if not account:
        raise HttpError(404, "Compte introuvable.")
    if account.level == "class":
        raise HttpError(409, "Une classe SYSCOHADA ne peut pas être supprimée.")
    if account.is_syscohada:
        raise HttpError(409, "Un compte officiel du PCGO ne peut pas être supprimé.")
    if account.children.exists():
        raise HttpError(409, "Ce compte a des subdivisions. Supprimez-les d’abord.")
    if account.lines.exists():
        raise HttpError(409, "Ce compte a déjà des écritures. Il ne peut pas être supprimé.")
    record_audit(
        request,
        action="ledger.account.delete",
        resource_type="account",
        resource_id=str(account.id),
        company=company,
        metadata={"code": account.code},
    )
    account.delete()
    return {"ok": True}


@router.get("/ledger/accounts/template")
def download_account_template(request):
    require_company(request)
    response = HttpResponse(TEMPLATE_CSV, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="plan-comptable-muhimu.csv"'
    return response


@router.post("/ledger/accounts/import/preview", response=ImportReportOut)
def preview_account_import(request, file: UploadedFile = File(...)):
    _, _, company = require_writer(request)
    rows = parse_csv(_read_import_file(file))
    if not rows:
        raise HttpError(400, "Aucune ligne reconnue. Colonnes attendues : code, intitulé.")
    return report_to_dict(preview_import(company, rows))


@router.post("/ledger/accounts/import", response=ImportReportOut)
def commit_account_import(request, file: UploadedFile = File(...)):
    _, _, company = require_writer(request)
    rows = parse_csv(_read_import_file(file))
    if not rows:
        raise HttpError(400, "Aucune ligne reconnue. Colonnes attendues : code, intitulé.")
    report = apply_import(company, rows)
    if report.applied:
        record_audit(
            request,
            action="ledger.account.import",
            resource_type="account",
            resource_id=str(company.id),
            company=company,
            metadata={"created": report.created, "updated": report.updated},
        )
    return report_to_dict(report)


@router.get("/ledger/journals", response=list[JournalOut])
def list_journals(request):
    _, _, company = require_company(request)
    return [
        JournalOut(id=str(j.id), code=j.code, name=j.name, type=j.type)
        for j in Journal.objects.filter(company=company)
    ]


@router.get("/ledger/periods", response=list[PeriodOut])
def list_periods(request):
    _, _, company = require_company(request)
    exercise = Exercise.objects.filter(company=company, year=timezone.localdate().year).first()
    if not exercise:
        return []
    return [_period_out(p) for p in exercise.periods.all()]


@router.get("/ledger/entries", response=list[EntryOut])
def list_entries(request, status: str | None = None, journal_id: str | None = None):
    _, _, company = require_company(request)
    qs = (
        Entry.objects.filter(company=company)
        .select_related("journal")
        .prefetch_related(Prefetch("lines", queryset=EntryLine.objects.select_related("account")))
    )
    if status:
        qs = qs.filter(status=status)
    if journal_id:
        qs = qs.filter(journal_id=journal_id)
    return [_entry_out(entry) for entry in qs[:200]]


@router.get("/ledger/entries/{entry_id}", response=EntryOut)
def get_entry(request, entry_id: str):
    _, _, company = require_company(request)
    entry = (
        Entry.objects.filter(company=company, id=entry_id)
        .select_related("journal")
        .prefetch_related("lines__account")
        .first()
    )
    if not entry:
        raise HttpError(404, "Écriture introuvable.")
    return _entry_out(entry)


@router.post("/ledger/entries", response=EntryOut)
def create_entry(request, payload: EntryIn):
    _, _, company = require_writer(request)
    journal = Journal.objects.filter(company=company, id=payload.journal_id).first()
    if not journal:
        raise HttpError(404, "Journal introuvable.")
    entry = create_draft(
        company=company,
        journal=journal,
        accounting_date=_parse_date(payload.accounting_date, "comptable"),
        value_date=_parse_date(payload.value_date, "de valeur") if payload.value_date else None,
        description=payload.description,
        document_ref=payload.document_ref,
        raw_lines=_raw_lines(payload),
        idempotency_key=payload.idempotency_key,
    )
    record_audit(
        request,
        action="ledger.entry.create",
        resource_type="entry",
        resource_id=str(entry.id),
        company=company,
        metadata={"status": entry.status},
    )
    return _entry_out(entry)


@router.put("/ledger/entries/{entry_id}", response=EntryOut)
def update_entry(request, entry_id: str, payload: EntryIn):
    _, _, company = require_writer(request)
    entry = Entry.objects.filter(company=company, id=entry_id).first()
    if not entry:
        raise HttpError(404, "Écriture introuvable.")
    journal = Journal.objects.filter(company=company, id=payload.journal_id).first()
    if not journal:
        raise HttpError(404, "Journal introuvable.")
    entry = update_draft(
        entry,
        journal=journal,
        accounting_date=_parse_date(payload.accounting_date, "comptable"),
        value_date=_parse_date(payload.value_date, "de valeur") if payload.value_date else None,
        description=payload.description,
        document_ref=payload.document_ref,
        raw_lines=_raw_lines(payload),
    )
    return _entry_out(entry)


@router.post("/ledger/entries/{entry_id}/post", response=EntryOut)
def post_entry_api(request, entry_id: str):
    _, _, company = require_writer(request)
    entry = Entry.objects.select_related("journal").filter(company=company, id=entry_id).first()
    if not entry:
        raise HttpError(404, "Écriture introuvable.")
    require_escompte_allowed_for_entry(entry)
    entry = post_entry(entry, request.user)
    if is_beta_feature_enabled(FEATURE_ESCOMPTE):
        sync_discount_commitment(entry)
    record_audit(
        request,
        action="ledger.entry.post",
        resource_type="entry",
        resource_id=str(entry.id),
        company=company,
        metadata={"number": entry.number_display},
    )
    return _entry_out(entry)


@router.post("/ledger/entries/{entry_id}/reverse", response=EntryOut)
def reverse_entry_api(request, entry_id: str, payload: ReverseIn):
    _, _, company = require_writer(request)
    entry = Entry.objects.filter(company=company, id=entry_id).first()
    if not entry:
        raise HttpError(404, "Écriture introuvable.")
    require_escompte_allowed_for_entry(entry)
    reversal = reverse_entry(entry, request.user, payload.description)
    if is_beta_feature_enabled(FEATURE_ESCOMPTE):
        close_discount_for_entry(entry, request.user)
    record_audit(
        request,
        action="ledger.entry.reverse",
        resource_type="entry",
        resource_id=str(reversal.id),
        company=company,
        metadata={"original": str(entry.id), "number": reversal.number_display},
    )
    return _entry_out(reversal)


@router.delete("/ledger/entries/{entry_id}")
def delete_draft(request, entry_id: str):
    _, _, company = require_writer(request)
    entry = Entry.objects.filter(company=company, id=entry_id).first()
    if not entry:
        raise HttpError(404, "Écriture introuvable.")
    if entry.status != EntryStatus.DRAFT:
        raise HttpError(409, "Une écriture validée ne peut pas être supprimée.")
    entry.delete()
    return {"ok": True}


@router.get("/ledger/balance", response=list[BalanceRowOut])
def get_balance(request, period_id: str | None = None):
    _, _, company = require_company(request)
    period = _resolve_period(company, period_id)
    rows = trial_balance(company, period)
    return [
        BalanceRowOut(
            account_id=row["account_id"],
            code=row["code"],
            label=row["label"],
            open_debit=dec(row["open_debit"]),
            open_credit=dec(row["open_credit"]),
            mov_debit=dec(row["mov_debit"]),
            mov_credit=dec(row["mov_credit"]),
            close_debit=dec(row["close_debit"]),
            close_credit=dec(row["close_credit"]),
        )
        for row in rows
    ]


@router.get("/ledger/general-ledger/{account_id}", response=GeneralLedgerOut)
def get_general_ledger(request, account_id: str, period_id: str | None = None):
    _, _, company = require_company(request)
    account = Account.objects.filter(company=company, id=account_id).first()
    if not account:
        raise HttpError(404, "Compte introuvable.")
    period = _resolve_period(company, period_id)
    data = general_ledger(company, account, period)
    return GeneralLedgerOut(
        account_id=data["account_id"],
        code=data["code"],
        label=data["label"],
        open_debit=dec(data["open_debit"]),
        open_credit=dec(data["open_credit"]),
        close_balance=dec(data["close_balance"]),
        lines=[
            LedgerLineOut(
                id=line["id"],
                entry_id=line["entry_id"],
                number_display=line["number_display"],
                journal_code=line["journal_code"],
                accounting_date=line["accounting_date"],
                label=line["label"],
                debit=dec(line["debit"]),
                credit=dec(line["credit"]),
                balance=dec(line["balance"]),
            )
            for line in data["lines"]
        ],
    )


def _resolve_period(company, period_id: str | None) -> AccountingPeriod:
    if period_id:
        period = AccountingPeriod.objects.filter(company=company, id=period_id).first()
        if not period:
            raise HttpError(404, "Période introuvable.")
        return period
    period = _current_period(company)
    if not period:
        raise HttpError(400, "Aucune période courante. Initialisez le ledger.")
    return period


def _document_out(doc: SourceDocument) -> DocumentOut:
    return DocumentOut(
        id=str(doc.id),
        entry_id=str(doc.entry_id) if doc.entry_id else None,
        original_name=doc.original_name,
        content_type=doc.content_type,
        size=doc.size,
        sha256=doc.sha256,
        issued_on=doc.issued_on.isoformat(),
        keep_until=doc.keep_until.isoformat(),
        created_at=doc.created_at.isoformat(),
    )


def _inventory_out(campaign: InventoryCampaign) -> InventoryCampaignOut:
    lines = list(campaign.lines.select_related("account").all())
    entry = campaign.variation_entry
    return InventoryCampaignOut(
        id=str(campaign.id),
        inventoried_on=campaign.inventoried_on.isoformat(),
        status=campaign.status,
        notes=campaign.notes,
        method=campaign.method,
        method_label=METHOD_LABELS.get(campaign.method, campaign.method),
        variation_entry_id=str(campaign.variation_entry_id) if campaign.variation_entry_id else None,
        variation_entry_number=entry.number_display if entry else "",
        total=dec(sum((line.amount for line in lines), Decimal("0"))),
        lines=[
            InventoryLineOut(
                id=str(line.id),
                account_id=str(line.account_id) if line.account_id else None,
                account_code=line.account.code if line.account_id else "",
                description=line.description,
                quantity=dec(line.quantity),
                unit=line.unit,
                unit_value=dec(line.unit_value),
                amount=dec(line.amount),
            )
            for line in lines
        ],
    )


@router.get("/ledger/beta-scope", response=BetaScopeOut)
def get_beta_scope(request):
    require_membership(request)
    return beta_scope_payload()


@router.get("/ledger/statements", response=StatementsOut)
def get_statements(request, period_id: str | None = None):
    _, _, company = require_company(request)
    prefetch_related_objects([company], "officers")
    period = _resolve_period(company, period_id)
    try:
        return build_statements(company, period)
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc


@router.get("/ledger/smt", response=SmtEligibilityOut)
def get_smt_eligibility(request, period_id: str | None = None):
    _, _, company = require_company(request)
    period = _resolve_period(company, period_id)
    return eligibility_for(company, period)


@router.get("/ledger/statements/pdf")
def get_statements_pdf(request, period_id: str | None = None, kind: str = "liasse"):
    _, _, company = require_company(request)
    prefetch_related_objects([company], "officers")
    kind = (kind or "liasse").lower()
    if kind not in STATEMENT_KINDS:
        raise HttpError(400, "État PDF inconnu (bilan, result, tft, notes ou liasse).")
    period = _resolve_period(company, period_id)
    try:
        payload = build_statements(company, period)
        pdf = render_statements_pdf(payload, kind)
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{pdf_filename(payload, kind)}"'
    return response


def _exercise_for(company, year: int | None) -> Exercise:
    year = year or timezone.localdate().year
    exercise = Exercise.objects.filter(company=company, year=year).first()
    if not exercise:
        raise HttpError(404, f"Exercice {year} introuvable.")
    return exercise


@router.get("/ledger/exercises", response=list[ExerciseOut])
def list_exercises(request):
    _, _, company = require_company(request)
    out = []
    for exercise in Exercise.objects.filter(company=company).order_by("-year"):
        out.append(_exercise_out(exercise, preview_close(company, exercise)))
    return out


def _opening_lines(payload: OpeningIn) -> list[dict]:
    lines = []
    if payload.csv.strip():
        lines.extend(parse_opening_text(payload.csv))
    for line in payload.lines:
        lines.append(
            {
                "code": line.code,
                "debit": line.debit,
                "credit": line.credit,
                "solde": line.solde,
            }
        )
    if not lines:
        raise HttpError(400, "Collez un CSV ou saisissez au moins une ligne (code, débit, crédit).")
    return lines


def _opening_preview_out(payload: dict) -> OpeningPreviewOut:
    return OpeningPreviewOut(
        rows=[OpeningLineOut(**item) for item in payload.get("rows") or []],
        an_lines=[
            OpeningLineOut(
                account_id=item.get("account_id") or "",
                code=item["code"],
                label=item.get("label") or "",
                debit=item["debit"],
                credit=item["credit"],
                kind="opening",
            )
            for item in payload.get("an_lines") or []
        ],
        pnl_count=payload.get("pnl_count", 0),
        an_debit=payload.get("an_debit") or "0",
        an_credit=payload.get("an_credit") or "0",
        net_result_prior=payload.get("net_result_prior") or "0",
        warnings=payload.get("warnings") or [],
        errors=payload.get("errors") or [],
        ok=bool(payload.get("ok")),
        posted=bool(payload.get("posted")),
        entry_id=payload.get("entry_id"),
        entry_number=payload.get("entry_number") or "",
        prior_seeded=payload.get("prior_seeded") or 0,
    )


@router.get("/ledger/opening", response=OpeningStateOut)
def get_opening(request, year: int | None = None):
    _, _, company = require_company(request)
    exercise = _exercise_for(company, year)
    return OpeningStateOut(**opening_state(company, exercise))


@router.get("/ledger/opening/template")
def opening_template(request):
    response = HttpResponse(OPENING_TEMPLATE, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="soldes-ouverture.csv"'
    return response


@router.post("/ledger/opening/preview", response=OpeningPreviewOut)
def preview_opening_api(request, payload: OpeningIn):
    _, _, company = require_company(request)
    return _opening_preview_out(preview_opening(company, _opening_lines(payload)))


@router.post("/ledger/opening", response=OpeningPreviewOut)
def post_opening_api(request, payload: OpeningIn):
    _, _, company = require_writer(request)
    exercise = _exercise_for(company, payload.year)
    result = post_opening(company, exercise, request.user, _opening_lines(payload))
    record_audit(
        request,
        action="ledger.opening.post",
        resource_type="exercise",
        resource_id=str(exercise.id),
        company=company,
        metadata={"number": result.get("entry_number"), "prior": result.get("prior_seeded")},
    )
    return _opening_preview_out(result)


@router.post("/ledger/opening/csv/preview", response=OpeningPreviewOut)
def preview_opening_csv(request, file: UploadedFile = File(...)):
    _, _, company = require_company(request)
    content = _read_import_file(file)
    return _opening_preview_out(preview_opening(company, parse_opening_csv(content)))


@router.post("/ledger/opening/csv", response=OpeningPreviewOut)
def post_opening_csv(request, file: UploadedFile = File(...), year: int | None = None):
    _, _, company = require_writer(request)
    exercise = _exercise_for(company, year)
    content = _read_import_file(file)
    result = post_opening(company, exercise, request.user, parse_opening_csv(content))
    record_audit(
        request,
        action="ledger.opening.post",
        resource_type="exercise",
        resource_id=str(exercise.id),
        company=company,
        metadata={"number": result.get("entry_number"), "file": file.name},
    )
    return _opening_preview_out(result)


@router.get("/ledger/fx-rates", response=list[FxRateOut])
def list_fx_rates(request, currency: str = ""):
    _, _, company = require_company(request)
    qs = FxRate.objects.filter(company=company)
    if currency.strip():
        qs = qs.filter(currency_code=currency.strip().upper())
    return [FxRateOut(**serialize_rate(row)) for row in qs]


@router.post("/ledger/fx-rates", response=FxRateOut)
def upsert_fx_rate_api(request, payload: FxRateIn):
    _, _, company = require_writer(request)
    row = upsert_rate(
        company,
        payload.currency_code,
        _parse_date(payload.rate_date, "de cours"),
        payload.rate,
    )
    record_audit(
        request,
        action="ledger.fx.rate",
        resource_type="fx_rate",
        resource_id=str(row.id),
        company=company,
        metadata={"currency": row.currency_code, "date": row.rate_date.isoformat(), "rate": format(row.rate, "f")},
    )
    return FxRateOut(**serialize_rate(row))


@router.delete("/ledger/fx-rates/{rate_id}")
def delete_fx_rate(request, rate_id: str):
    _, _, company = require_writer(request)
    row = FxRate.objects.filter(company=company, id=rate_id).first()
    if not row:
        raise HttpError(404, "Cours introuvable.")
    currency = row.currency_code
    row.delete()
    record_audit(
        request,
        action="ledger.fx.rate.delete",
        resource_type="fx_rate",
        resource_id=rate_id,
        company=company,
        metadata={"currency": currency},
    )
    return {"ok": True}


@router.get("/ledger/fx/revalue", response=FxRevalueOut)
def preview_fx_revalue(request, as_of: str = ""):
    _, _, company = require_company(request)
    day = _parse_date(as_of, "d'arrêté") if as_of else timezone.localdate()
    return FxRevalueOut(**compute_revalue(company, day))


@router.post("/ledger/fx/revalue", response=FxRevalueOut)
def post_fx_revalue_api(request, payload: FxRevalueIn):
    _, _, company = require_writer(request)
    day = _parse_date(payload.as_of, "d'arrêté") if payload.as_of else timezone.localdate()
    result = post_revalue(company, day, request.user)
    record_audit(
        request,
        action="ledger.fx.revalue",
        resource_type="entry",
        resource_id=result.get("entry_id") or "",
        company=company,
        metadata={"as_of": result.get("as_of"), "number": result.get("entry_number")},
    )
    return FxRevalueOut(**result)


@router.post("/ledger/exercise/close", response=ExerciseOut)
def close_exercise_api(request, payload: CloseExerciseIn):
    _, _, company = require_writer(request)
    exercise = _exercise_for(company, payload.year)
    closed_on = _parse_date(payload.closed_on, "closed_on") if payload.closed_on else None
    exercise = close_exercise(company, exercise, request.user, closed_on=closed_on)
    record_audit(
        request,
        action="ledger.exercise.close",
        resource_type="exercise",
        resource_id=str(exercise.id),
        company=company,
        metadata={"year": exercise.year, "net": str(exercise.net_result)},
    )
    return _exercise_out(exercise, preview_close(company, exercise))


@router.post("/ledger/exercise/allocate", response=ExerciseOut)
def allocate_exercise_api(request, payload: AllocateIn):
    _, _, company = require_writer(request)
    exercise = _exercise_for(company, payload.year)
    exercise = allocate_result(
        company,
        exercise,
        request.user,
        {
            "approved_on": _parse_date(payload.approved_on, "approved_on"),
            "legal_reserve": payload.legal_reserve,
            "free_reserve": payload.free_reserve,
            "retained": payload.retained,
            "dividends": payload.dividends,
            "pay_dividends": payload.pay_dividends,
            "bank_account_id": payload.bank_account_id,
        },
    )
    record_audit(
        request,
        action="ledger.exercise.allocate",
        resource_type="exercise",
        resource_id=str(exercise.id),
        company=company,
        metadata={"dividends": str(exercise.dividends_amount)},
    )
    return _exercise_out(exercise, preview_close(company, exercise))


@router.patch("/ledger/exercise/notes", response=ExerciseOut)
def update_exercise_notes(request, payload: NotesIn):
    _, _, company = require_writer(request)
    exercise = None
    if payload.period_id:
        period = _resolve_period(company, payload.period_id)
        exercise = period.exercise
    if not exercise:
        exercise = Exercise.objects.filter(company=company, year=timezone.localdate().year).first()
    if not exercise:
        raise HttpError(404, "Exercice introuvable.")
    if payload.notes is not None:
        exercise.notes_annexes = serialize_notes(
            [
                {
                    "number": item.number,
                    "status": item.status,
                    "body": item.body,
                    "conformity": item.conformity,
                    "methods": item.methods,
                    "derogations": item.derogations,
                    "extra": item.extra,
                }
                for item in payload.notes
            ]
        )
    else:
        exercise.notes_annexes = payload.notes_annexes
    if payload.closed_on:
        exercise.closed_on = _parse_date(payload.closed_on, "closed_on")
    if payload.approved_on:
        exercise.approved_on = _parse_date(payload.approved_on, "approved_on")
    exercise.save()
    record_audit(
        request,
        action="ledger.exercise.notes",
        resource_type="exercise",
        resource_id=str(exercise.id),
        company=company,
    )
    return _exercise_out(exercise)


@router.post("/ledger/periods/{period_id}/validate", response=PeriodOut)
def validate_period_api(request, period_id: str):
    _, _, company = require_writer(request)
    period = AccountingPeriod.objects.filter(company=company, id=period_id).first()
    if not period:
        raise HttpError(404, "Période introuvable.")
    period = validate_period(period)
    record_audit(
        request,
        action="ledger.period.validate",
        resource_type="period",
        resource_id=str(period.id),
        company=company,
        metadata={"month": period.month},
    )
    return _period_out(period)


@router.post("/ledger/periods/{period_id}/it-close", response=PeriodOut)
def it_close_period_api(request, period_id: str):
    _, _, company = require_writer(request)
    period = AccountingPeriod.objects.filter(company=company, id=period_id).first()
    if not period:
        raise HttpError(404, "Période introuvable.")
    period = it_close_period(period)
    record_audit(
        request,
        action="ledger.period.it_close",
        resource_type="period",
        resource_id=str(period.id),
        company=company,
        metadata={"seal": period.seal},
    )
    return _period_out(period)


@router.get("/ledger/documents", response=list[DocumentOut])
def list_documents(request, entry_id: str | None = None):
    _, _, company = require_company(request)
    qs = SourceDocument.objects.filter(company=company)
    if entry_id:
        qs = qs.filter(entry_id=entry_id)
    return [_document_out(doc) for doc in qs[:200]]


@router.post("/ledger/documents", response=DocumentOut)
def upload_document(
    request,
    file: UploadedFile = File(...),
    entry_id: str | None = None,
    issued_on: str | None = None,
):
    _, _, company = require_writer(request)
    content = file.read()
    if not content:
        raise HttpError(400, "Fichier vide.")
    if len(content) > 8_000_000:
        raise HttpError(400, "Pièce trop volumineuse (8 Mo).")
    entry = None
    if entry_id:
        entry = Entry.objects.filter(company=company, id=entry_id).first()
        if not entry:
            raise HttpError(404, "Écriture introuvable.")
    issued = _parse_date(issued_on, "issued_on") if issued_on else timezone.localdate()
    try:
        keep_until = date(issued.year + 10, issued.month, issued.day)
    except ValueError:
        keep_until = date(issued.year + 10, 2, 28)
    doc = SourceDocument(
        organization=company.organization,
        company=company,
        entry=entry,
        original_name=file.name or "piece",
        content_type=file.content_type or "",
        size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        issued_on=issued,
        keep_until=keep_until,
    )
    doc.file.save(file.name or "piece", ContentFile(content), save=True)
    record_audit(
        request,
        action="ledger.document.upload",
        resource_type="document",
        resource_id=str(doc.id),
        company=company,
        metadata={"entry_id": entry_id, "name": doc.original_name},
    )
    return _document_out(doc)


@router.get("/ledger/documents/{document_id}/file")
def download_document(request, document_id: str):
    _, _, company = require_company(request)
    doc = SourceDocument.objects.filter(company=company, id=document_id).first()
    if not doc or not doc.file:
        raise HttpError(404, "Pièce introuvable.")
    response = HttpResponse(doc.file.open("rb").read(), content_type=doc.content_type or "application/octet-stream")
    response["Content-Disposition"] = f'attachment; filename="{doc.original_name}"'
    return response


@router.get("/ledger/inventories", response=list[InventoryCampaignOut])
def list_inventories(request):
    _, _, company = require_company(request)
    campaigns = (
        InventoryCampaign.objects.filter(company=company)
        .select_related("variation_entry")
        .prefetch_related("lines__account")
    )
    return [_inventory_out(item) for item in campaigns]


@router.post("/ledger/inventories", response=InventoryCampaignOut)
def create_inventory(request, payload: InventoryCampaignIn):
    _, _, company = require_writer(request)
    inventoried_on = _parse_date(payload.inventoried_on, "inventoried_on")
    exercise = Exercise.objects.filter(
        company=company, starts_on__lte=inventoried_on, ends_on__gte=inventoried_on
    ).first()
    if not exercise:
        raise HttpError(400, "Aucun exercice à cette date d’inventaire.")
    method = (payload.method or StockMethod.CUMP).lower()
    if method not in StockMethod.values:
        raise HttpError(400, "Méthode de stocks invalide (cump ou peps).")
    campaign = InventoryCampaign.objects.create(
        organization=company.organization,
        company=company,
        exercise=exercise,
        inventoried_on=inventoried_on,
        notes=payload.notes,
        method=method,
    )
    return _inventory_out(campaign)


@router.post("/ledger/inventories/{campaign_id}/lines", response=InventoryCampaignOut)
def add_inventory_line(request, campaign_id: str, payload: InventoryLineIn):
    _, _, company = require_writer(request)
    campaign = InventoryCampaign.objects.filter(company=company, id=campaign_id).first()
    if not campaign:
        raise HttpError(404, "Inventaire introuvable.")
    if campaign.status != InventoryStatus.DRAFT:
        raise HttpError(409, "Cet inventaire est arrêté.")
    account = None
    description = payload.description.strip()
    if payload.account_id:
        account = Account.objects.filter(
            company=company, id=payload.account_id, is_active=True, is_postable=True
        ).first()
        if not account:
            raise HttpError(400, "Compte introuvable.")
        if account.code.startswith("39"):
            raise HttpError(400, "Les dépréciations 39 se passent à part, pas à l’inventaire physique.")
    else:
        inferred = infer_stock_code(description)
        if inferred:
            account = resolve_account(company, inferred)
    currency = company.currency_code or "XOF"
    qty = Decimal(payload.quantity or "0")
    unit_value = parse_amount(payload.unit_value or "0", currency)
    InventoryLine.objects.create(
        organization=company.organization,
        company=company,
        campaign=campaign,
        account=account,
        description=description,
        quantity=qty,
        unit=payload.unit,
        unit_value=unit_value,
        amount=quantize_amount(qty * unit_value, currency),
    )
    return _inventory_out(campaign)


@router.post("/ledger/inventories/{campaign_id}/close", response=InventoryCampaignOut)
def close_inventory(request, campaign_id: str):
    _, _, company = require_writer(request)
    campaign = (
        InventoryCampaign.objects.filter(company=company, id=campaign_id)
        .select_related("variation_entry")
        .first()
    )
    if not campaign:
        raise HttpError(404, "Inventaire introuvable.")
    campaign = close_stock_inventory(campaign, request.user)
    record_audit(
        request,
        action="ledger.inventory.close",
        resource_type="inventory",
        resource_id=str(campaign.id),
        company=company,
        metadata={"entry_id": str(campaign.variation_entry_id) if campaign.variation_entry_id else None},
    )
    campaign = (
        InventoryCampaign.objects.filter(id=campaign.id).select_related("variation_entry").first()
    )
    return _inventory_out(campaign)


@router.get("/ledger/parties", response=list[PartyOut])
def list_parties(request):
    _, _, company = require_company(request)
    parties = ThirdParty.objects.filter(company=company, is_active=True).select_related("account")
    return [serialize_party(item) for item in parties]


@router.post("/ledger/parties", response=PartyOut)
def add_party(request, payload: PartyIn):
    _, _, company = require_writer(request)
    party = create_party(
        company,
        {
            "name": payload.name,
            "kind": payload.kind,
            "tax_id": payload.tax_id,
            "reference": payload.reference,
            "account_id": payload.account_id,
        },
    )
    record_audit(
        request,
        action="ledger.party.create",
        resource_type="party",
        resource_id=str(party.id),
        company=company,
        metadata={"name": party.name},
    )
    return serialize_party(party)


@router.get("/ledger/parties/open", response=list[OpenItemOut])
def list_open_items(request, party_id: str | None = None, account_id: str | None = None):
    _, _, company = require_company(request)
    as_of = reference_date(company)
    return [
        serialize_open_item(line, as_of)
        for line in open_lines(company, party_id=party_id, account_id=account_id)
    ]


@router.post("/ledger/lettering", response=LetterOut)
def post_lettering(request, payload: LetterIn):
    _, _, company = require_writer(request)
    code = letter_lines(company, payload.line_ids)
    record_audit(
        request,
        action="ledger.lettering",
        resource_type="lettering",
        resource_id=code,
        company=company,
        metadata={"count": len(payload.line_ids)},
    )
    return LetterOut(code=code, count=len(payload.line_ids))


@router.post("/ledger/lettering/unletter")
def post_unletter(request, payload: UnletterIn):
    _, _, company = require_writer(request)
    count = unletter(company, payload.code)
    record_audit(
        request,
        action="ledger.unletter",
        resource_type="lettering",
        resource_id=payload.code,
        company=company,
    )
    return {"ok": True, "count": count}


@router.patch("/ledger/lines/{line_id}/due", response=OpenItemOut)
def patch_line_due(request, line_id: str, payload: LineDueIn):
    _, _, company = require_writer(request)
    line = set_line_due(company, line_id, payload.due_on)
    record_audit(
        request,
        action="ledger.line.due",
        resource_type="entry_line",
        resource_id=str(line.id),
        company=company,
        metadata={"due_on": line.due_on.isoformat() if line.due_on else ""},
    )
    return serialize_open_item(line)


@router.get("/ledger/bank/reconciliation", response=BankReconOut)
def get_bank_reconciliation(request, account_id: str | None = None):
    _, _, company = require_company(request)
    return reconciliation_payload(company, account_id)


@router.post("/ledger/bank/statements", response=BankStatementOut)
def post_bank_statement(request, payload: BankStatementIn):
    _, _, company = require_writer(request)
    statement = upsert_statement(
        company,
        {
            "account_id": payload.account_id,
            "statement_date": payload.statement_date,
            "bank_balance": payload.bank_balance,
        },
    )
    record_audit(
        request,
        action="ledger.bank.statement",
        resource_type="bank_statement",
        resource_id=str(statement.id),
        company=company,
        metadata={"date": statement.statement_date.isoformat()},
    )
    return serialize_statement(statement)


@router.post("/ledger/bank/statements/{statement_id}/lines", response=BankStatementLineOut)
def post_bank_statement_line(request, statement_id: str, payload: BankStatementLineIn):
    _, _, company = require_writer(request)
    line = add_statement_line(
        company,
        statement_id,
        {
            "line_date": payload.line_date,
            "label": payload.label,
            "bank_debit": payload.bank_debit,
            "bank_credit": payload.bank_credit,
        },
    )
    record_audit(
        request,
        action="ledger.bank.statement_line",
        resource_type="bank_statement_line",
        resource_id=str(line.id),
        company=company,
    )
    return serialize_statement_line(line)


@router.post("/ledger/bank/ofx", response=OfxImportOut)
def post_bank_ofx(request, file: UploadedFile = File(...), account_id: str | None = None):
    _, _, company = require_writer(request)
    content = file.read()
    if not content:
        raise HttpError(400, "Fichier OFX vide.")
    if len(content) > 4_000_000:
        raise HttpError(400, "Fichier trop volumineux (4 Mo).")
    result = import_ofx(company, content, account_id)
    record_audit(
        request,
        action="ledger.bank.ofx",
        resource_type="bank_statement",
        resource_id=result["statement"]["id"],
        company=company,
        metadata={"created": result["created"], "skipped": result["skipped"]},
    )
    return result


@router.post("/ledger/bank/pointage", response=LetterOut)
def post_bank_pointage(request, payload: BankPointIn):
    _, _, company = require_writer(request)
    code = point_selection(company, payload.book_ids, payload.statement_ids)
    record_audit(
        request,
        action="ledger.bank.pointage",
        resource_type="bank_pointage",
        resource_id=code,
        company=company,
        metadata={"books": len(payload.book_ids), "statement": len(payload.statement_ids)},
    )
    return LetterOut(code=code, count=len(payload.book_ids) + len(payload.statement_ids))


@router.post("/ledger/bank/unpoint")
def post_bank_unpoint(request, payload: BankUnpointIn):
    _, _, company = require_writer(request)
    count = unpoint(company, payload.code)
    record_audit(
        request,
        action="ledger.bank.unpoint",
        resource_type="bank_pointage",
        resource_id=payload.code,
        company=company,
    )
    return {"ok": True, "count": count}


@router.get("/ledger/cash", response=CashPanelOut)
def get_cash_panel(request, account_id: str | None = None):
    _, _, company = require_company(request)
    return cash_payload(company, account_id)


@router.post("/ledger/cash", response=CashCountOut)
def post_cash_count(request, payload: CashCountIn):
    _, _, company = require_writer(request)
    item = upsert_count(
        company,
        {
            "account_id": payload.account_id,
            "counted_on": payload.counted_on,
            "physical_amount": payload.physical_amount,
            "notes": payload.notes,
        },
    )
    record_audit(
        request,
        action="ledger.cash.count",
        resource_type="cash_count",
        resource_id=str(item.id),
        company=company,
        metadata={"date": item.counted_on.isoformat(), "physical": format(item.physical_amount, "f")},
    )
    return serialize_count(item)


@router.post("/ledger/cash/{count_id}/variance", response=CashCountOut)
def post_cash_variance(request, count_id: str):
    _, _, company = require_writer(request)
    item = post_variance(company, count_id, request.user)
    record_audit(
        request,
        action="ledger.cash.variance",
        resource_type="cash_count",
        resource_id=str(item.id),
        company=company,
        metadata={"entry": item.entry.number_display if item.entry_id else ""},
    )
    return serialize_count(item)


@router.post("/ledger/escompte/preview", response=EscomptePreviewOut)
def post_escompte_preview(request, payload: EscompteIn):
    require_beta_feature(FEATURE_ESCOMPTE)
    _, _, company = require_company(request)
    return preview_discount(
        company,
        {
            "nominal": payload.nominal,
            "agios": payload.agios,
            "due_on": payload.due_on,
            "campaign": payload.campaign,
            "bank_account_id": payload.bank_account_id,
            "source_account_id": payload.source_account_id,
            "third_party_id": payload.third_party_id,
            "label": payload.label,
        },
    )


@router.get("/ledger/commitments", response=list[CommitmentOut])
def list_commitments(request):
    _, _, company = require_company(request)
    items = Commitment.objects.filter(company=company, is_active=True).select_related("entry")
    return [serialize_commitment(item) for item in items]


@router.post("/ledger/commitments", response=CommitmentOut)
def add_commitment(request, payload: CommitmentIn):
    _, _, company = require_writer(request)
    item = create_commitment(
        company,
        {
            "kind": payload.kind,
            "side": payload.side,
            "label": payload.label,
            "counterparty": payload.counterparty,
            "amount": payload.amount,
            "starts_on": payload.starts_on,
            "ends_on": payload.ends_on,
        },
    )
    record_audit(
        request,
        action="ledger.commitment.create",
        resource_type="commitment",
        resource_id=str(item.id),
        company=company,
        metadata={"kind": item.kind, "amount": format(item.amount, "f")},
    )
    return serialize_commitment(item)


@router.delete("/ledger/commitments/{commitment_id}")
def remove_commitment(request, commitment_id: str):
    _, _, company = require_writer(request)
    deactivate_commitment(company, commitment_id, request.user)
    record_audit(
        request,
        action="ledger.commitment.deactivate",
        resource_type="commitment",
        resource_id=commitment_id,
        company=company,
    )
    return {"ok": True}


@router.post("/ledger/commitments/{commitment_id}/class9", response=CommitmentOut)
def post_commitment_class9_api(request, commitment_id: str):
    require_beta_feature(FEATURE_CLASS9_CAGE)
    _, _, company = require_writer(request)
    item = post_commitment_class9(company, commitment_id, request.user)
    record_audit(
        request,
        action="ledger.commitment.class9",
        resource_type="commitment",
        resource_id=commitment_id,
        company=company,
        metadata={"entry": item.entry.number_display if item.entry_id else ""},
    )
    return serialize_commitment(item)


@router.get("/ledger/class9", response=Class9Out)
def get_class9(request, period_id: str | None = None):
    require_beta_feature(FEATURE_CLASS9_CAGE)
    _, _, company = require_company(request)
    period = _resolve_period(company, period_id)
    rows = trial_balance(company, period)
    engagements = [row for row in rows if str(row["code"]).startswith("90") or str(row["code"]).startswith("91")]
    cage = [row for row in rows if str(row["code"])[:2] in {"92", "93", "94", "95", "96", "97", "98", "99"}]
    return Class9Out(
        engagements=[
            BalanceRowOut(
                account_id=row["account_id"],
                code=row["code"],
                label=row["label"],
                open_debit=dec(row["open_debit"]),
                open_credit=dec(row["open_credit"]),
                mov_debit=dec(row["mov_debit"]),
                mov_credit=dec(row["mov_credit"]),
                close_debit=dec(row["close_debit"]),
                close_credit=dec(row["close_credit"]),
            )
            for row in engagements
        ],
        cage=[
            BalanceRowOut(
                account_id=row["account_id"],
                code=row["code"],
                label=row["label"],
                open_debit=dec(row["open_debit"]),
                open_credit=dec(row["open_credit"]),
                mov_debit=dec(row["mov_debit"]),
                mov_credit=dec(row["mov_credit"]),
                close_debit=dec(row["close_debit"]),
                close_credit=dec(row["close_credit"]),
            )
            for row in cage
        ],
    )


def _cage_panel_out(payload: dict) -> CagePanelOut:
    return CagePanelOut(
        sections=[CageSectionOut(**item) for item in payload["sections"]],
        results=[
            CageResultOut(
                section_id=item["section_id"],
                code=item["code"],
                label=item["label"],
                charges=item["charges"],
                products=item["products"],
                result=item["result"],
            )
            for item in payload["results"]
        ],
        pending=payload.get("pending", 0),
        reflected=payload.get("reflected", 0),
        last_entry_id=payload.get("last_entry_id"),
        last_entry_number=payload.get("last_entry_number") or "",
        created=payload.get("created", 0),
        skipped=payload.get("skipped", 0),
        closed=payload.get("closed", False),
        close_entry_id=payload.get("close_entry_id"),
        close_entry_number=payload.get("close_entry_number") or "",
        analytical_result=payload.get("analytical_result") or "0",
    )


@router.get("/ledger/cage", response=CagePanelOut)
def get_cage(request, period_id: str | None = None):
    require_beta_feature(FEATURE_CLASS9_CAGE)
    _, _, company = require_company(request)
    period = _resolve_period(company, period_id)
    return _cage_panel_out(cage_panel(company, period))


@router.post("/ledger/cage/sections", response=CageSectionOut)
def create_cage_section_api(request, payload: CageSectionIn):
    require_beta_feature(FEATURE_CLASS9_CAGE)
    _, _, company = require_writer(request)
    section = create_section(
        company,
        {"code": payload.code, "label": payload.label, "is_default": payload.is_default},
    )
    record_audit(
        request,
        action="ledger.cage.section.create",
        resource_type="cage_section",
        resource_id=str(section.id),
        company=company,
        metadata={"code": section.code},
    )
    return CageSectionOut(**serialize_section(section))


@router.patch("/ledger/cage/sections/{section_id}", response=CageSectionOut)
def update_cage_section_api(request, section_id: str, payload: CageSectionPatch):
    require_beta_feature(FEATURE_CLASS9_CAGE)
    _, _, company = require_writer(request)
    section = update_section(
        company,
        section_id,
        {
            "label": payload.label,
            "is_default": payload.is_default,
            "is_active": payload.is_active,
        },
    )
    record_audit(
        request,
        action="ledger.cage.section.update",
        resource_type="cage_section",
        resource_id=section_id,
        company=company,
        metadata={"code": section.code},
    )
    return CageSectionOut(**serialize_section(section))


@router.post("/ledger/cage/reflect", response=CagePanelOut)
def reflect_cage_api(request, period_id: str | None = None):
    require_beta_feature(FEATURE_CLASS9_CAGE)
    _, _, company = require_writer(request)
    period = _resolve_period(company, period_id)
    payload = reflect_period(company, period, request.user)
    record_audit(
        request,
        action="ledger.cage.reflect",
        resource_type="period",
        resource_id=str(period.id),
        company=company,
        metadata={"created": payload.get("created", 0), "skipped": payload.get("skipped", 0)},
    )
    return _cage_panel_out(payload)


@router.post("/ledger/cage/allocate", response=CagePanelOut)
def allocate_cage_api(request, payload: CageAllocateIn):
    require_beta_feature(FEATURE_CLASS9_CAGE)
    _, _, company = require_writer(request)
    period = _resolve_period(company, payload.period_id)
    panel = allocate_cage(
        company,
        period,
        request.user,
        {"section_id": payload.section_id, "kind": payload.kind, "amount": payload.amount},
    )
    record_audit(
        request,
        action="ledger.cage.allocate",
        resource_type="period",
        resource_id=str(period.id),
        company=company,
        metadata={"kind": payload.kind, "section_id": payload.section_id},
    )
    return _cage_panel_out(panel)


@router.post("/ledger/cage/close", response=CagePanelOut)
def close_cage_api(request, period_id: str | None = None):
    require_beta_feature(FEATURE_CLASS9_CAGE)
    _, _, company = require_writer(request)
    period = _resolve_period(company, period_id)
    panel = close_cage(company, period, request.user)
    record_audit(
        request,
        action="ledger.cage.close",
        resource_type="period",
        resource_id=str(period.id),
        company=company,
        metadata={"close_entry_id": panel.get("close_entry_id")},
    )
    return _cage_panel_out(panel)


def _esg_payroll(company, year: int | None):
    year = year or timezone.localdate().year
    exercise = Exercise.objects.filter(company=company, year=year).first()
    if not exercise:
        return None
    period = exercise.periods.order_by("-ends_on").first()
    if not period:
        return None
    rows = restore_pnl_rows(trial_balance(company, period), closing_lines_for(exercise))
    total = payroll_from_rows(rows)
    return total or None


@router.get("/ledger/esg", response=EsgOut)
def get_esg(request, year: int | None = None):
    require_beta_feature(FEATURE_ESG)
    _, _, company = require_company(request)
    return get_report(company, year, payroll=_esg_payroll(company, year))


@router.put("/ledger/esg", response=EsgOut)
def save_esg(request, payload: EsgIn):
    require_beta_feature(FEATURE_ESG)
    _, _, company = require_writer(request)
    report = upsert_report(
        company,
        {
            "year": payload.year,
            "headcount": payload.headcount,
            "hires": payload.hires,
            "dismissals": payload.dismissals,
            "disabled_count": payload.disabled_count,
            "social_dialogue": payload.social_dialogue,
            "health": payload.health,
            "training": payload.training,
            "equality": payload.equality,
            "env_policy": payload.env_policy,
            "waste": payload.waste,
            "water": payload.water,
            "energy": payload.energy,
            "ghg": payload.ghg,
            "biodiversity": payload.biodiversity,
            "territory": payload.territory,
            "neighbors": payload.neighbors,
            "patronage": payload.patronage,
            "purchases": payload.purchases,
        },
    )
    record_audit(
        request,
        action="ledger.esg.save",
        resource_type="esg",
        resource_id=str(report.id),
        company=company,
        metadata={"year": report.year, "headcount": report.headcount},
    )
    return get_report(company, report.year, payroll=_esg_payroll(company, report.year))


@router.get("/ledger/books", response=LegalBooksOut)
def legal_books(request):
    _, _, company = require_company(request)
    entries = (
        Entry.objects.filter(company=company, status=EntryStatus.POSTED)
        .select_related("journal")
        .prefetch_related("lines")
        .order_by("accounting_date", "number")[:2000]
    )
    inventory = InventoryCampaign.objects.filter(company=company, status=InventoryStatus.CLOSED).first()
    summary = ""
    if inventory:
        total = sum((line.amount for line in inventory.lines.all()), Decimal("0"))
        summary = (
            f"Inventaire du {inventory.inventoried_on.isoformat()} — "
            f"{inventory.lines.count()} poste(s), total {dec(total)}."
        )
    return LegalBooksOut(
        numbered=True,
        dated=timezone.localdate().isoformat(),
        inventory_summary=summary,
        journal=[
            BookLineOut(
                id=str(entry.id),
                number_display=entry.number_display,
                journal_code=entry.journal.code,
                accounting_date=entry.accounting_date.isoformat(),
                value_date=entry.value_date.isoformat(),
                description=entry.description,
                document_ref=entry.document_ref,
                total=dec(sum((line.debit for line in entry.lines.all()), Decimal("0"))),
            )
            for entry in entries
        ],
    )


@router.get("/ledger/books/pdf")
def get_books_pdf(request, period_id: str | None = None, kind: str = "all"):
    _, _, company = require_company(request)
    kind = (kind or "all").lower()
    if kind not in BOOK_KINDS:
        raise HttpError(400, "Livre PDF inconnu (journal, ledger, balance, inventory ou all).")
    period = _resolve_period(company, period_id)
    try:
        pdf = render_books_pdf(company, period, kind)
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{books_filename(period, kind)}"'
    return response


@router.get("/ledger/assets/suggest", response=AssetSuggestOut)
def suggest_asset_accounts(request, account_id: str):
    _, _, company = require_company(request)
    account = Account.objects.filter(id=account_id, company=company).first()
    if not account:
        raise HttpError(404, "Compte introuvable.")
    amort_code, expense_code = suggest_contra_codes(account.code)
    amort = resolve_account(company, amort_code)
    expense = resolve_account(company, expense_code)
    return {
        "amort_account_id": str(amort.id) if amort else None,
        "amort_account_code": amort.code if amort else amort_code,
        "expense_account_id": str(expense.id) if expense else None,
        "expense_account_code": expense.code if expense else expense_code,
    }


@router.get("/ledger/assets", response=list[FixedAssetOut])
def list_assets(request, period_id: str | None = None):
    _, _, company = require_company(request)
    period = _resolve_period(company, period_id) if period_id else None
    assets = (
        FixedAsset.objects.filter(company=company)
        .select_related("asset_account", "amort_account", "expense_account")
        .order_by("reference")
    )
    out = []
    for asset in assets:
        payload = serialize_asset(asset)
        if period:
            payload["charge_preview"] = format(charge_for_period(asset, period), "f")
        out.append(payload)
    return out


@router.post("/ledger/assets", response=FixedAssetOut)
def create_asset(request, payload: FixedAssetIn):
    _, _, company = require_writer(request)
    data = validate_asset_payload(
        company,
        {
            "cost": payload.cost,
            "residual_value": payload.residual_value,
            "useful_life_months": payload.useful_life_months,
            "kind": payload.kind,
            "parent_id": payload.parent_id,
            "asset_account_id": payload.asset_account_id,
            "amort_account_id": payload.amort_account_id,
            "expense_account_id": payload.expense_account_id,
            "acquired_on": _parse_date(payload.acquired_on, "acquired_on"),
            "in_service_on": _parse_date(payload.in_service_on, "in_service_on"),
        },
    )
    asset = FixedAsset.objects.create(
        organization=company.organization,
        company=company,
        parent=data["parent"],
        reference=(payload.reference or "").strip() or next_reference(company),
        label=payload.label.strip(),
        kind=data["kind"],
        acquired_on=data["acquired_on"],
        in_service_on=data["in_service_on"],
        cost=data["cost"],
        residual_value=data["residual_value"],
        useful_life_months=data["useful_life_months"],
        asset_account=data["asset_account"],
        amort_account=data["amort_account"],
        expense_account=data["expense_account"],
        notes=payload.notes.strip(),
    )
    record_audit(
        request,
        action="ledger.asset.create",
        resource_type="fixed_asset",
        resource_id=str(asset.id),
        company=company,
        metadata={"reference": asset.reference},
    )
    return serialize_asset(asset)


@router.post("/ledger/assets/depreciate", response=DepreciateOut)
def depreciate_assets(request, payload: DepreciateIn):
    _, _, company = require_writer(request)
    period = _resolve_period(company, payload.period_id)
    entry = post_period_depreciation(company, period, request.user)
    if not entry:
        return {"posted": False, "count": 0, "total": "0"}
    total = sum((charge.amount for charge in entry.depreciation_charges.all()), Decimal("0"))
    record_audit(
        request,
        action="ledger.asset.depreciate",
        resource_type="period",
        resource_id=str(period.id),
        company=company,
        metadata={"entry": entry.number_display, "total": str(total)},
    )
    return {
        "posted": True,
        "count": entry.depreciation_charges.count(),
        "total": format(total, "f"),
        "entry_id": str(entry.id),
        "number_display": entry.number_display,
    }


@router.get("/ledger/consolidation", response=list[ConsolidationOut])
def list_consolidation(request):
    require_beta_feature(FEATURE_CONSOLIDATION)
    org, membership = require_membership(request)
    return list_groups(org, user=request.user, membership=membership)


@router.post("/ledger/consolidation", response=ConsolidationOut)
def create_consolidation(request, payload: ConsolidationGroupIn):
    require_beta_feature(FEATURE_CONSOLIDATION)
    org, membership = require_org_writer(request)
    panel = create_group(org, payload.dict(), user=request.user, membership=membership)
    record_audit(
        request,
        action="ledger.consolidation.create",
        resource_type="consolidation_group",
        resource_id=panel["id"],
        company=request.company,
        metadata={"name": panel["name"], "kind": panel["kind"], "year": panel["year"]},
    )
    return panel


@router.get("/ledger/consolidation/{group_id}", response=ConsolidationOut)
def get_consolidation(request, group_id: str):
    require_beta_feature(FEATURE_CONSOLIDATION)
    org, membership = require_membership(request)
    return group_panel(org, group_id, user=request.user, membership=membership)


@router.patch("/ledger/consolidation/{group_id}", response=ConsolidationOut)
def patch_consolidation(request, group_id: str, payload: ConsolidationGroupPatch):
    require_beta_feature(FEATURE_CONSOLIDATION)
    org, membership = require_org_writer(request)
    panel = update_group(
        org, group_id, payload.dict(exclude_unset=True), user=request.user, membership=membership
    )
    record_audit(
        request,
        action="ledger.consolidation.update",
        resource_type="consolidation_group",
        resource_id=group_id,
        company=request.company,
    )
    return panel


@router.post("/ledger/consolidation/{group_id}/members", response=ConsolidationOut)
def add_consolidation_member(request, group_id: str, payload: ConsolidationMemberIn):
    require_beta_feature(FEATURE_CONSOLIDATION)
    org, membership = require_org_writer(request)
    panel = add_member(
        org, group_id, payload.dict(), user=request.user, membership=membership
    )
    record_audit(
        request,
        action="ledger.consolidation.member.add",
        resource_type="consolidation_group",
        resource_id=group_id,
        company=request.company,
        metadata={"company_id": payload.company_id},
    )
    return panel


@router.patch("/ledger/consolidation/{group_id}/members/{member_id}", response=ConsolidationOut)
def patch_consolidation_member(request, group_id: str, member_id: str, payload: ConsolidationMemberPatch):
    require_beta_feature(FEATURE_CONSOLIDATION)
    org, membership = require_org_writer(request)
    assert_group_access(request.user, membership, _get_group(org, group_id))
    return update_member(org, group_id, member_id, payload.dict(exclude_unset=True))


@router.delete("/ledger/consolidation/{group_id}/members/{member_id}", response=ConsolidationOut)
def delete_consolidation_member(request, group_id: str, member_id: str):
    require_beta_feature(FEATURE_CONSOLIDATION)
    org, membership = require_org_writer(request)
    assert_group_access(request.user, membership, _get_group(org, group_id))
    return remove_member(org, group_id, member_id)


@router.post("/ledger/consolidation/{group_id}/eliminations", response=ConsolidationOut)
def add_consolidation_elimination(request, group_id: str, payload: ConsolidationEliminationIn):
    require_beta_feature(FEATURE_CONSOLIDATION)
    org, membership = require_org_writer(request)
    assert_group_access(request.user, membership, _get_group(org, group_id))
    panel = add_elimination(org, group_id, payload.dict())
    record_audit(
        request,
        action="ledger.consolidation.elim.add",
        resource_type="consolidation_group",
        resource_id=group_id,
        company=request.company,
        metadata={"code": payload.code, "amount": payload.amount},
    )
    return panel


@router.delete("/ledger/consolidation/{group_id}/eliminations/{elimination_id}", response=ConsolidationOut)
def delete_consolidation_elimination(request, group_id: str, elimination_id: str):
    require_beta_feature(FEATURE_CONSOLIDATION)
    org, membership = require_org_writer(request)
    assert_group_access(request.user, membership, _get_group(org, group_id))
    return remove_elimination(org, group_id, elimination_id)


@router.get("/ledger/consolidation/{group_id}/pdf")
def get_consolidation_pdf(request, group_id: str, kind: str = "liasse"):
    require_beta_feature(FEATURE_CONSOLIDATION)
    org, membership = require_membership(request)
    kind = (kind or "liasse").lower()
    if kind not in STATEMENT_KINDS:
        raise HttpError(400, "État PDF inconnu (bilan, result, tft, notes ou liasse).")
    try:
        pdf, filename = group_pdf(
            org, group_id, kind, user=request.user, membership=membership
        )
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
