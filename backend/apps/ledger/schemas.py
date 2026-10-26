from decimal import Decimal

from ninja import Schema

from apps.tenancy.schemas import OfficerOut


def dec(value: Decimal | None) -> str:
    if value is None:
        return "0"
    return format(value, "f")


class AccountAnatomyOut(Schema):
    class_code: str | None = None
    two_digit: str | None = None
    principal: str | None = None
    divisionary: str | None = None
    entity: str | None = None
    subclass: str | None = None
    secondary: str | None = None
    auxiliary: str | None = None


class AccountConstantOut(Schema):
    kind: str
    title: str
    detail: str


class AccountReadingOut(Schema):
    constants: list[AccountConstantOut] = []
    parallel_code: str | None = None
    parallel_label: str | None = None
    parallel_kind: str | None = None


class AccountOut(Schema):
    id: str
    code: str
    label: str
    account_class: str
    level: str
    level_label: str
    family: str
    family_label: str
    sense: str
    sense_label: str
    is_postable: bool
    is_collective: bool
    is_syscohada: bool
    notes: str = ""
    parent_id: str | None = None
    parent_code: str | None = None
    children_count: int = 0
    anatomy: AccountAnatomyOut
    reading: AccountReadingOut


class AccountFicheOut(Schema):
    code: str
    fiche_code: str
    title: str
    contenu: str = ""
    subdivisions: str = ""
    commentaires: str = ""
    fonctionnement: str = ""
    exclusions: str = ""
    controles: str = ""
    debit: list[str] = []
    credit: list[str] = []


class AccountIn(Schema):
    code: str
    label: str
    is_postable: bool | None = None
    notes: str = ""


class ImportRowOut(Schema):
    line: int
    code: str
    label: str
    action: str
    errors: list[str]
    level: str = ""
    family: str = ""
    account_class: str = ""


class ImportReportOut(Schema):
    applied: bool
    created: int
    updated: int
    errors: int
    rows: list[ImportRowOut]


class JournalOut(Schema):
    id: str
    code: str
    name: str
    type: str


class ExerciseOut(Schema):
    id: str
    year: int
    starts_on: str
    ends_on: str
    status: str
    closed_on: str | None = None
    approved_on: str | None = None
    notes_annexes: str = ""
    net_result: str = "0"
    revenue: str = "0"
    legal_reserve_amount: str = "0"
    free_reserve_amount: str = "0"
    retained_amount: str = "0"
    dividends_amount: str = "0"
    result_entry_id: str | None = None
    allocation_entry_id: str | None = None
    payment_entry_id: str | None = None
    opening_entry_id: str | None = None
    suggested_legal_reserve: str = "0"
    suggested_retained: str = "0"
    blockers: list[str] = []
    can_close: bool = False
    can_allocate: bool = False


class CloseExerciseIn(Schema):
    year: int | None = None
    closed_on: str | None = None


class AllocateIn(Schema):
    year: int | None = None
    approved_on: str
    legal_reserve: str = "0"
    free_reserve: str = "0"
    retained: str = "0"
    dividends: str = "0"
    pay_dividends: bool = False
    bank_account_id: str | None = None


class OpeningLineIn(Schema):
    code: str
    debit: str = "0"
    credit: str = "0"
    solde: str = ""


class OpeningIn(Schema):
    year: int | None = None
    csv: str = ""
    lines: list[OpeningLineIn] = []


class OpeningLineOut(Schema):
    account_id: str = ""
    code: str
    label: str = ""
    debit: str
    credit: str
    kind: str = "opening"


class OpeningPreviewOut(Schema):
    rows: list[OpeningLineOut]
    an_lines: list[OpeningLineOut] = []
    pnl_count: int = 0
    an_debit: str = "0"
    an_credit: str = "0"
    net_result_prior: str = "0"
    warnings: list[str] = []
    errors: list[str] = []
    ok: bool = False
    posted: bool = False
    entry_id: str | None = None
    entry_number: str = ""
    prior_seeded: int = 0


class OpeningStateOut(Schema):
    year: int
    prior_year: int
    posted: bool = False
    entry_id: str | None = None
    entry_number: str = ""
    prior_seeded: int = 0
    can_post: bool = False
    blockers: list[str] = []
    template: str = ""


class PeriodOut(Schema):
    id: str
    year: int
    month: int
    starts_on: str
    ends_on: str
    status: str
    validated_at: str | None = None
    it_closed_at: str | None = None
    seal: str = ""


class StatementLineOut(Schema):
    code: str = ""
    label: str
    current: str
    prior: str
    bold: bool = False
    gross: str | None = None
    amort: str | None = None
    kind: str = ""


class BilanOut(Schema):
    actif: list[StatementLineOut]
    passif: list[StatementLineOut]
    balanced: bool


class ResultOut(Schema):
    lines: list[StatementLineOut]
    net: str


class TftOut(Schema):
    lines: list[StatementLineOut]


class SmtEligibilityOut(Schema):
    regime: str
    activity_kind: str
    threshold: str
    threshold_label: str
    revenue: str
    eligible: bool
    warning: str = ""


class IndicatorOut(Schema):
    current: str
    prior: str


class AnalysisOut(Schema):
    fr: IndicatorOut
    fr_bas: IndicatorOut
    bfg: IndicatorOut
    bfe: IndicatorOut
    bf_hao: IndicatorOut
    tn: IndicatorOut
    conversion: IndicatorOut
    cafg: IndicatorOut
    ebe: IndicatorOut
    net: IndicatorOut


class EntityOut(Schema):
    name: str
    legal_name: str = ""
    country_code: str = ""
    country_label: str = ""
    currency_code: str = ""
    regime: str = "normal"
    regime_label: str = ""
    activity_kind: str = ""
    activity_label: str = ""
    starts_on: str = ""
    ends_on: str = ""
    duration_months: int = 12
    acronym: str = ""
    address: str = ""
    city: str = ""
    postal_code: str = ""
    phone: str = ""
    email: str = ""
    tax_id: str = ""
    rccm: str = ""
    social_register: str = ""
    legal_form: str = ""
    legal_form_label: str = ""
    tax_regime: str = ""
    tax_regime_label: str = ""
    naema_code: str = ""
    control_kind: str = ""
    control_label: str = ""
    establishments_domestic: int = 1
    establishments_foreign: int = 0
    distinct_branch_accounts: bool = False
    auditor_name: str = ""
    auditor_order_no: str = ""
    signatory_name: str = ""
    signatory_title: str = ""
    banks: str = ""
    officers: list[OfficerOut] = []


class NoteItemOut(Schema):
    number: int
    title: str
    status: str
    required: bool = False
    body: str = ""
    conformity: str = ""
    methods: str = ""
    derogations: str = ""
    extra: str = ""
    computed: str = ""


class NoteItemIn(Schema):
    number: int
    status: str = "NA"
    body: str = ""
    conformity: str = ""
    methods: str = ""
    derogations: str = ""
    extra: str = ""


class StatementsOut(Schema):
    regime: str
    scope: str | None = None
    exercise_year: int
    period_id: str
    period_label: str
    comparative_year: int | None = None
    going_concern: bool = True
    closed_on: str | None = None
    approved_on: str | None = None
    arrete_due_on: str
    ago_due_on: str
    notes_annexes: str = ""
    entity: EntityOut | None = None
    analysis: AnalysisOut | None = None
    notes: list[NoteItemOut] = []
    bilan: BilanOut
    result: ResultOut
    tft: TftOut
    smt: SmtEligibilityOut | None = None


class NotesIn(Schema):
    notes_annexes: str = ""
    notes: list[NoteItemIn] | None = None
    period_id: str | None = None
    closed_on: str | None = None
    approved_on: str | None = None


class FixedAssetIn(Schema):
    reference: str = ""
    label: str
    kind: str = "standalone"
    parent_id: str | None = None
    acquired_on: str
    in_service_on: str
    cost: str
    residual_value: str = "0"
    useful_life_months: int = 0
    asset_account_id: str
    amort_account_id: str | None = None
    expense_account_id: str | None = None
    notes: str = ""


class FixedAssetOut(Schema):
    id: str
    reference: str
    label: str
    kind: str
    parent_id: str | None = None
    acquired_on: str
    in_service_on: str
    cost: str
    residual_value: str
    useful_life_months: int
    method: str
    asset_account_id: str
    asset_account_code: str
    amort_account_id: str | None = None
    amort_account_code: str = ""
    expense_account_id: str | None = None
    expense_account_code: str = ""
    status: str
    disposed_on: str | None = None
    notes: str = ""
    accumulated: str
    net: str
    depreciable: bool = False
    charge_preview: str | None = None


class AssetSuggestOut(Schema):
    amort_account_id: str | None = None
    amort_account_code: str = ""
    expense_account_id: str | None = None
    expense_account_code: str = ""


class DepreciateIn(Schema):
    period_id: str


class DepreciateOut(Schema):
    posted: bool
    count: int = 0
    total: str = "0"
    entry_id: str | None = None
    number_display: str = ""


class DocumentOut(Schema):
    id: str
    entry_id: str | None = None
    original_name: str
    content_type: str
    size: int
    sha256: str
    issued_on: str
    keep_until: str
    created_at: str


class InventoryLineIn(Schema):
    account_id: str | None = None
    description: str
    quantity: str = "0"
    unit: str = ""
    unit_value: str = "0"


class InventoryLineOut(Schema):
    id: str
    account_id: str | None = None
    account_code: str = ""
    description: str
    quantity: str
    unit: str
    unit_value: str
    amount: str


class InventoryCampaignIn(Schema):
    inventoried_on: str
    notes: str = ""
    method: str = "cump"


class InventoryCampaignOut(Schema):
    id: str
    inventoried_on: str
    status: str
    notes: str
    method: str = "cump"
    method_label: str = "CUMP"
    variation_entry_id: str | None = None
    variation_entry_number: str = ""
    lines: list[InventoryLineOut]
    total: str


class BookLineOut(Schema):
    id: str
    number_display: str
    journal_code: str
    accounting_date: str
    value_date: str
    description: str
    document_ref: str
    total: str


class LegalBooksOut(Schema):
    numbered: bool = True
    dated: str
    journal: list[BookLineOut]
    inventory_summary: str = ""


class EntryLineIn(Schema):
    account_id: str
    debit: str = "0"
    credit: str = "0"
    label: str = ""
    third_party_id: str | None = None
    due_on: str = ""
    cage_section_id: str | None = None
    currency_code: str = ""
    fx_rate: str = ""


class EntryIn(Schema):
    journal_id: str
    accounting_date: str
    value_date: str | None = None
    description: str
    document_ref: str = ""
    idempotency_key: str = ""
    lines: list[EntryLineIn]


class EntryLineOut(Schema):
    id: str
    account_id: str
    account_code: str
    account_label: str
    label: str
    debit: str
    credit: str
    third_party_id: str | None = None
    third_party_name: str = ""
    lettering: str = ""
    due_on: str = ""
    cage_section_id: str | None = None
    cage_section_code: str = ""
    currency_code: str = ""
    foreign_amount: str = "0"
    fx_rate: str = "1"


class EntryOut(Schema):
    id: str
    journal_id: str
    journal_code: str
    number: int | None
    number_display: str
    accounting_date: str
    value_date: str
    description: str
    document_ref: str
    status: str
    period_id: str
    exercise_id: str
    reversed_entry_id: str | None = None
    lines: list[EntryLineOut]
    total_debit: str
    total_credit: str


class ReverseIn(Schema):
    description: str = ""


class BalanceRowOut(Schema):
    account_id: str
    code: str
    label: str
    open_debit: str
    open_credit: str
    mov_debit: str
    mov_credit: str
    close_debit: str
    close_credit: str


class LedgerLineOut(Schema):
    id: str
    entry_id: str
    number_display: str
    journal_code: str
    accounting_date: str
    label: str
    debit: str
    credit: str
    balance: str


class GeneralLedgerOut(Schema):
    account_id: str
    code: str
    label: str
    open_debit: str
    open_credit: str
    lines: list[LedgerLineOut]
    close_balance: str


class SetupIn(Schema):
    with_demo: bool = False


class OrgSetupOut(Schema):
    id: str
    slug: str
    type: str
    setup_data: str
    seeded: int = 0
    companies: int = 0
    already: bool = False


class LedgerStatusOut(Schema):
    ready: bool
    exercise: ExerciseOut | None = None
    current_period: PeriodOut | None = None
    accounts: int = 0
    journals: int = 0
    setup_data: str = ""
    needs_choice: bool = False
    entries: int = 0


class PartyIn(Schema):
    name: str
    kind: str = "customer"
    tax_id: str = ""
    reference: str = ""
    account_id: str | None = None


class PartyOut(Schema):
    id: str
    kind: str
    kind_label: str = ""
    name: str
    reference: str
    tax_id: str = ""
    account_id: str
    account_code: str
    is_active: bool = True


class OpenItemOut(Schema):
    id: str
    entry_id: str
    entry_number: str = ""
    accounting_date: str
    account_id: str
    account_code: str
    third_party_id: str | None = None
    third_party_name: str = ""
    label: str
    debit: str
    credit: str
    lettering: str = ""
    due_on: str = ""
    bucket: str = ""


class LetterIn(Schema):
    line_ids: list[str]


class LetterOut(Schema):
    code: str
    count: int = 0


class UnletterIn(Schema):
    code: str


class LineDueIn(Schema):
    due_on: str = ""


class BankStatementIn(Schema):
    account_id: str | None = None
    statement_date: str
    bank_balance: str = "0"


class BankStatementOut(Schema):
    id: str
    account_id: str
    account_code: str
    statement_date: str
    bank_balance: str


class BankStatementLineIn(Schema):
    line_date: str = ""
    label: str
    bank_debit: str = "0"
    bank_credit: str = "0"


class BankStatementLineOut(Schema):
    id: str
    statement_id: str
    line_date: str
    label: str
    bank_debit: str
    bank_credit: str
    pointage: str = ""


class BankBookLineOut(Schema):
    id: str
    entry_id: str
    entry_number: str = ""
    accounting_date: str
    account_id: str
    account_code: str
    label: str
    debit: str
    credit: str
    pointage: str = ""


class BankPointIn(Schema):
    book_ids: list[str]
    statement_ids: list[str]


class BankUnpointIn(Schema):
    code: str


class OfxImportOut(Schema):
    created: int = 0
    skipped: int = 0
    statement: BankStatementOut


class BankReconOut(Schema):
    account_id: str
    account_code: str
    account_label: str = ""
    book_balance: str
    bank_balance: str
    unpointed_book_net: str
    unpointed_statement_net: str
    control: str
    statement: BankStatementOut | None = None
    book_lines: list[BankBookLineOut]
    statement_lines: list[BankStatementLineOut]


class CashCountIn(Schema):
    account_id: str | None = None
    counted_on: str
    physical_amount: str = "0"
    notes: str = ""


class CashCountOut(Schema):
    id: str
    account_id: str
    account_code: str
    counted_on: str
    physical_amount: str
    book_amount: str
    variance: str
    variance_kind: str = ""
    contra_code: str = ""
    notes: str = ""
    entry_id: str | None = None
    entry_number: str = ""


class CashPanelOut(Schema):
    account_id: str
    account_code: str
    account_label: str = ""
    book_balance: str
    physical_amount: str = ""
    variance: str
    variance_kind: str = ""
    contra_code: str = ""
    count: CashCountOut | None = None
    counts: list[CashCountOut]
    book_lines: list[BankBookLineOut]


class CommitmentIn(Schema):
    kind: str
    side: str = "given"
    label: str
    counterparty: str = ""
    amount: str
    starts_on: str = ""
    ends_on: str = ""


class CommitmentOut(Schema):
    id: str
    kind: str
    kind_label: str = ""
    side: str
    side_label: str = ""
    label: str
    counterparty: str = ""
    amount: str
    starts_on: str = ""
    ends_on: str = ""
    is_active: bool = True
    entry_id: str | None = None
    entry_number: str = ""
    origin_entry_id: str | None = None
    class9_debit: str = ""
    class9_credit: str = ""


class Class9Out(Schema):
    engagements: list[BalanceRowOut]
    cage: list[BalanceRowOut]


class CageSectionIn(Schema):
    code: str
    label: str
    is_default: bool = False


class CageSectionPatch(Schema):
    label: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None


class CageSectionOut(Schema):
    id: str
    code: str
    label: str
    account_id: str
    account_code: str
    is_default: bool
    is_active: bool


class CageResultOut(Schema):
    section_id: str
    code: str
    label: str
    charges: str
    products: str
    result: str


class CagePanelOut(Schema):
    sections: list[CageSectionOut]
    results: list[CageResultOut]
    pending: int = 0
    reflected: int = 0
    last_entry_id: str | None = None
    last_entry_number: str = ""
    created: int = 0
    skipped: int = 0
    closed: bool = False
    close_entry_id: str | None = None
    close_entry_number: str = ""
    analytical_result: str = "0"


class CageAllocateIn(Schema):
    period_id: str | None = None
    section_id: str
    kind: str
    amount: str


class EsgIn(Schema):
    year: int | None = None
    headcount: int = 0
    hires: int = 0
    dismissals: int = 0
    disabled_count: int = 0
    social_dialogue: str = ""
    health: str = ""
    training: str = ""
    equality: str = ""
    env_policy: str = ""
    waste: str = ""
    water: str = ""
    energy: str = ""
    ghg: str = ""
    biodiversity: str = ""
    territory: str = ""
    neighbors: str = ""
    patronage: str = ""
    purchases: str = ""


class EscompteIn(Schema):
    nominal: str
    agios: str = "0"
    due_on: str = ""
    campaign: bool = False
    bank_account_id: str | None = None
    source_account_id: str | None = None
    third_party_id: str | None = None
    label: str = ""


class EscompteLineOut(Schema):
    account_id: str
    account_code: str = ""
    account_label: str = ""
    debit: str = "0"
    credit: str = "0"
    label: str = ""
    third_party_id: str | None = None
    due_on: str = ""


class EscomptePreviewOut(Schema):
    journal_id: str = ""
    journal_code: str = "BQ"
    description: str = ""
    nominal: str
    agios: str
    net: str
    liability_code: str = "565"
    lines: list[EscompteLineOut]


class EsgOut(Schema):
    id: str = ""
    year: int
    headcount: int = 0
    hires: int = 0
    dismissals: int = 0
    disabled_count: int = 0
    social_dialogue: str = ""
    health: str = ""
    training: str = ""
    equality: str = ""
    env_policy: str = ""
    waste: str = ""
    water: str = ""
    energy: str = ""
    ghg: str = ""
    biodiversity: str = ""
    territory: str = ""
    neighbors: str = ""
    patronage: str = ""
    purchases: str = ""
    required: bool = False
    threshold: int = 250
    chapter30_threshold: int = 500
    payroll: str = ""
    note_preview: str = ""


class FxRateIn(Schema):
    currency_code: str
    rate_date: str
    rate: str


class FxRateOut(Schema):
    id: str
    currency_code: str
    rate_date: str
    rate: str


class FxRevalueIn(Schema):
    as_of: str = ""


class FxRevalueLineOut(Schema):
    account_id: str
    account_code: str
    account_label: str
    currency_code: str
    foreign_net: str
    book_net: str
    closing_rate: str
    target: str
    difference: str
    kind: str
    debit_account_id: str = ""
    debit_account_code: str = ""
    credit_account_id: str = ""
    credit_account_code: str = ""


class FxRevalueOut(Schema):
    as_of: str
    functional: str
    ok: bool
    posted: bool = False
    entry_id: str | None = None
    entry_number: str = ""
    lines: list[FxRevalueLineOut] = []
    gain: str = "0"
    loss: str = "0"
    warnings: list[str] = []
    errors: list[str] = []


class ConsolidationMemberIn(Schema):
    company_id: str
    method: str = "full"
    ownership_pct: str = "100"
    is_parent: bool = False
    is_active: bool = True


class ConsolidationMemberPatch(Schema):
    method: str | None = None
    ownership_pct: str | None = None
    is_parent: bool | None = None
    is_active: bool | None = None


class ConsolidationMemberOut(Schema):
    id: str
    company_id: str
    company_name: str
    currency_code: str = "XOF"
    method: str
    ownership_pct: str
    is_parent: bool
    is_active: bool


class ConsolidationEliminationIn(Schema):
    code: str
    label: str = ""
    amount: str
    kind: str = "other"


class ConsolidationEliminationOut(Schema):
    id: str
    code: str
    label: str
    amount: str
    kind: str


class ConsolidationGroupIn(Schema):
    name: str
    kind: str = "consolidated"
    year: int
    currency_code: str = "XOF"
    parent_id: str | None = None
    notes: str = ""


class ConsolidationGroupPatch(Schema):
    name: str | None = None
    kind: str | None = None
    year: int | None = None
    currency_code: str | None = None
    parent_id: str | None = None
    notes: str | None = None


class ConsolidationSummaryOut(Schema):
    id: str
    company_id: str
    company_name: str
    currency_code: str = "XOF"
    method: str
    ownership_pct: str
    is_parent: bool
    is_active: bool
    included: bool = False
    warning: str = ""
    period_label: str = ""
    sales: str = "0"
    net: str = "0"
    total_actif: str = "0"


class ConsolidationOut(Schema):
    id: str
    name: str
    kind: str
    year: int
    currency_code: str
    parent_id: str | None = None
    parent_name: str = ""
    notes: str = ""
    members: list[ConsolidationMemberOut] = []
    eliminations: list[ConsolidationEliminationOut] = []
    warnings: list[str] = []
    minorities: str = "0"
    summaries: list[ConsolidationSummaryOut] = []
    statements: StatementsOut | None = None


class BetaScopeOut(Schema):
    restrict_mode: bool = False
    consolidation: bool = True
    class9_cage: bool = True
    esg: bool = True
    escompte: bool = True
