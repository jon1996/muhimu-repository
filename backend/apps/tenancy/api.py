from ninja import Router
from ninja.errors import HttpError
from django.db import transaction

from apps.audit.services import record_audit
from apps.identity.models import User
from apps.ledger.services.setup import ensure_company_ledger
from apps.platform.access import user_can_access_organization
from apps.tenancy.access import require_admin, require_membership, require_writer
from apps.tenancy.middleware import companies_queryset_for, user_can_access_company
from apps.tenancy.liasse import identity_payload, serialize_officer
from apps.tenancy.ohada import UnknownOhadaCountry, resolve_country_currency
from apps.tenancy.models import (
    AccountingRegime,
    ActivityKind,
    Company,
    CompanyAccess,
    CompanyOfficer,
    ControlKind,
    LegalForm,
    Membership,
    OfficerRole,
    Organization,
    OrganizationType,
    Role,
    TaxRegime,
)
from apps.tenancy.schemas import (
    CompanyAccessIn,
    CompanyAccessOut,
    CompanyIn,
    CompanyOut,
    CompanySettingsIn,
    OfficerIn,
    OfficerOut,
    OrganizationIn,
    OrganizationOut,
    OwnOrganizationIn,
)

router = Router(tags=["tenancy"])


def _org_out(org: Organization) -> OrganizationOut:
    return OrganizationOut(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        type=org.type,
        setup_data=org.setup_data or "",
        is_demo=bool(org.is_demo),
    )


def _company_out(company: Company) -> CompanyOut:
    ident = identity_payload(company)
    return CompanyOut(
        id=str(company.id),
        name=company.name,
        legal_name=company.legal_name,
        country_code=company.country_code,
        currency_code=company.currency_code,
        accounting_regime=company.accounting_regime,
        activity_kind=company.activity_kind,
        procedure_manual=company.procedure_manual,
        going_concern=company.going_concern,
        is_active=company.is_active,
        setup_data=company.setup_data,
        **ident,
    )


@router.get("/organizations", response=list[OrganizationOut])
def list_organizations(request):
    orgs = Organization.objects.filter(
        memberships__user=request.user, memberships__is_active=True
    ).distinct()
    return [_org_out(o) for o in orgs if user_can_access_organization(request.user, o)]


@router.post("/organizations", response=OrganizationOut)
def create_organization(request, payload: OrganizationIn):
    if payload.type not in OrganizationType.values:
        raise HttpError(400, "Type d'organisation invalide (sme ou cabinet).")
    name = payload.name.strip()
    if not name:
        raise HttpError(400, "Le nom de l'organisation est obligatoire.")
    with transaction.atomic():
        org = Organization.objects.create(name=name, type=payload.type, is_demo=False)
        Membership.objects.create(
            organization=org, user=request.user, role=Role.OWNER
        )
    record_audit(
        request,
        action="organization.create",
        resource_type="organization",
        resource_id=str(org.id),
        organization=org,
        metadata={"name": org.name, "type": org.type},
    )
    return _org_out(org)


@router.post("/organizations/own", response=OrganizationOut)
def create_own_organization(request, payload: OwnOrganizationIn):
    """Dossier personnel à zéro : le testeur (ou le client) saisit sa propre entreprise."""
    from apps.ledger.services.demo import initialize_organization
    from apps.tenancy.rls import bind_tenant_context

    if payload.type not in OrganizationType.values:
        raise HttpError(400, "Type d'organisation invalide (sme ou cabinet).")
    name = payload.name.strip()
    company_name = payload.company_name.strip()
    if not name:
        raise HttpError(400, "Le nom de l'organisation est obligatoire.")
    if not company_name:
        raise HttpError(400, "Le nom de la société est obligatoire.")
    try:
        country, currency = resolve_country_currency(payload.country_code or "CI")
    except UnknownOhadaCountry:
        raise HttpError(400, "Pays invalide : choisissez un État membre OHADA.")

    # A1′ : pas de bypass GUC — contexte tenant après création org + membership owner.
    with transaction.atomic():
        org = Organization.objects.create(name=name, type=payload.type, is_demo=False)
        bind_tenant_context(
            user_id=str(request.user.id),
            organization_id=str(org.id),
            is_local=True,
        )
        Membership.objects.create(
            organization=org, user=request.user, role=Role.OWNER
        )
        Company.objects.create(
            organization=org,
            name=company_name,
            legal_name=(payload.legal_name.strip() or company_name),
            country_code=country,
            currency_code=currency,
        )
        initialize_organization(org, with_demo=False, user=request.user)

    record_audit(
        request,
        action="organization.create.own",
        resource_type="organization",
        resource_id=str(org.id),
        organization=org,
        metadata={"name": org.name, "type": org.type, "company": company_name},
    )
    return _org_out(org)


@router.get("/organizations/current", response=OrganizationOut)
def current_organization(request):
    org, _ = require_membership(request)
    return _org_out(org)


@router.get("/companies", response=list[CompanyOut])
def list_companies(request):
    _, membership = require_membership(request)
    qs = companies_queryset_for(request.user, membership).prefetch_related("officers")
    return [_company_out(c) for c in qs]


@router.post("/companies", response=CompanyOut)
def create_company(request, payload: CompanyIn):
    org, _ = require_admin(request)
    if payload.accounting_regime not in AccountingRegime.values:
        raise HttpError(400, "Régime invalide (normal ou smt).")
    if payload.activity_kind not in ActivityKind.values:
        raise HttpError(400, "Activité invalide (trade, craft ou services).")
    try:
        country, currency = resolve_country_currency(payload.country_code or "CI")
    except UnknownOhadaCountry:
        raise HttpError(400, "Pays invalide : choisissez un État membre OHADA.")
    company = Company.objects.create(
        organization=org,
        name=payload.name.strip(),
        legal_name=payload.legal_name.strip(),
        country_code=country,
        currency_code=currency,
        accounting_regime=payload.accounting_regime,
        activity_kind=payload.activity_kind,
        procedure_manual=payload.procedure_manual,
        going_concern=payload.going_concern,
    )
    ensure_company_ledger(company)
    record_audit(
        request,
        action="company.create",
        resource_type="company",
        resource_id=str(company.id),
        organization=org,
        company=company,
        metadata={"name": company.name},
    )
    return _company_out(company)


@router.get("/companies/{company_id}", response=CompanyOut)
def get_company(request, company_id: str):
    _, membership = require_membership(request)
    company = Company.objects.filter(id=company_id, organization=membership.organization).prefetch_related("officers").first()
    if not company or not user_can_access_company(request.user, membership, company):
        raise HttpError(404, "Société introuvable.")
    return _company_out(company)


@router.patch("/companies/{company_id}/settings", response=CompanyOut)
def update_company_settings(request, company_id: str, payload: CompanySettingsIn):
    _, _, company = require_writer(request)
    if str(company.id) != company_id:
        raise HttpError(400, "La société active ne correspond pas.")
    if payload.accounting_regime is not None:
        if payload.accounting_regime not in AccountingRegime.values:
            raise HttpError(400, "Régime invalide (normal ou smt).")
        company.accounting_regime = payload.accounting_regime
    if payload.activity_kind is not None:
        if payload.activity_kind not in ActivityKind.values:
            raise HttpError(400, "Activité invalide (trade, craft ou services).")
        company.activity_kind = payload.activity_kind
    if payload.procedure_manual is not None:
        company.procedure_manual = payload.procedure_manual
    if payload.going_concern is not None:
        company.going_concern = payload.going_concern
    if payload.legal_name is not None:
        company.legal_name = payload.legal_name.strip()
    if payload.country_code is not None:
        try:
            country, _ = resolve_country_currency(payload.country_code)
        except UnknownOhadaCountry:
            raise HttpError(400, "Pays invalide : choisissez un État membre OHADA.")
        company.country_code = country
    for field in (
        "acronym",
        "address",
        "city",
        "postal_code",
        "phone",
        "email",
        "tax_id",
        "rccm",
        "social_register",
        "naema_code",
        "auditor_name",
        "auditor_order_no",
        "signatory_name",
        "signatory_title",
        "banks",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(company, field, value.strip() if isinstance(value, str) else value)
    if payload.legal_form is not None:
        if payload.legal_form and payload.legal_form not in LegalForm.values:
            raise HttpError(400, "Forme juridique invalide.")
        company.legal_form = payload.legal_form
    if payload.tax_regime is not None:
        if payload.tax_regime and payload.tax_regime not in TaxRegime.values:
            raise HttpError(400, "Régime fiscal invalide.")
        company.tax_regime = payload.tax_regime
    if payload.control_kind is not None:
        if payload.control_kind and payload.control_kind not in ControlKind.values:
            raise HttpError(400, "Nature du contrôle invalide.")
        company.control_kind = payload.control_kind
    if payload.establishments_domestic is not None:
        company.establishments_domestic = max(0, payload.establishments_domestic)
    if payload.establishments_foreign is not None:
        company.establishments_foreign = max(0, payload.establishments_foreign)
    if payload.distinct_branch_accounts is not None:
        company.distinct_branch_accounts = payload.distinct_branch_accounts
    company.save()
    company = Company.objects.prefetch_related("officers").get(pk=company.pk)
    record_audit(
        request,
        action="company.settings",
        resource_type="company",
        resource_id=str(company.id),
        company=company,
        metadata={"regime": company.accounting_regime},
    )
    return _company_out(company)


@router.get("/companies/{company_id}/access", response=list[CompanyAccessOut])
def list_company_access(request, company_id: str):
    org, _ = require_admin(request)
    company = Company.objects.filter(id=company_id, organization=org).first()
    if not company:
        raise HttpError(404, "Société introuvable.")
    rows = CompanyAccess.objects.filter(company=company).select_related("user")
    return [
        CompanyAccessOut(
            id=str(row.id),
            user_id=str(row.user_id),
            user_email=row.user.email,
            company_id=str(row.company_id),
        )
        for row in rows
    ]


@router.post("/companies/{company_id}/access", response=CompanyAccessOut)
def grant_company_access(request, company_id: str, payload: CompanyAccessIn):
    org, _ = require_admin(request)
    company = Company.objects.filter(id=company_id, organization=org).first()
    if not company:
        raise HttpError(404, "Société introuvable.")
    user = User.objects.filter(email=payload.user_email.lower().strip()).first()
    if not user:
        raise HttpError(404, "Utilisateur introuvable.")
    if not Membership.objects.filter(organization=org, user=user, is_active=True).exists():
        raise HttpError(400, "L'utilisateur n'appartient pas à l'organisation.")
    access, _created = CompanyAccess.objects.get_or_create(
        organization=org, company=company, user=user
    )
    record_audit(
        request,
        action="company.access.grant",
        resource_type="company_access",
        resource_id=str(access.id),
        organization=org,
        company=company,
        metadata={"user_email": user.email},
    )
    return CompanyAccessOut(
        id=str(access.id),
        user_id=str(user.id),
        user_email=user.email,
        company_id=str(company.id),
    )


@router.delete("/companies/{company_id}/access/{access_id}")
def revoke_company_access(request, company_id: str, access_id: str):
    """Révoque un CompanyAccess (cabinets). Effet immédiat à la requête suivante."""
    org, membership = require_admin(request)
    company = Company.objects.filter(id=company_id, organization=org).first()
    if not company:
        raise HttpError(404, "Société introuvable.")
    access = (
        CompanyAccess.objects.filter(id=access_id, company=company, organization=org)
        .select_related("user")
        .first()
    )
    if not access:
        raise HttpError(404, "Accès introuvable.")
    user_email = access.user.email
    user_id = str(access.user_id)
    access_pk = str(access.id)
    access.delete()
    record_audit(
        request,
        action="company.access.revoke",
        resource_type="company_access",
        resource_id=access_pk,
        organization=org,
        company=company,
        metadata={
            "user_email": user_email,
            "user_id": user_id,
            "revoked_by": membership.role,
        },
    )
    return {"ok": True}


@router.post("/companies/{company_id}/officers", response=OfficerOut)
def create_officer(request, company_id: str, payload: OfficerIn):
    _, _, company = require_writer(request)
    if str(company.id) != company_id:
        raise HttpError(400, "La société active ne correspond pas.")
    if payload.role not in OfficerRole.values:
        raise HttpError(400, "Qualité du dirigeant invalide.")
    name = payload.full_name.strip()
    if not name:
        raise HttpError(400, "Le nom du dirigeant est requis.")
    officer = CompanyOfficer.objects.create(
        organization=company.organization,
        company=company,
        full_name=name,
        role=payload.role,
        nationality=payload.nationality.strip(),
        position=payload.position,
    )
    record_audit(
        request,
        action="company.officer.create",
        resource_type="officer",
        resource_id=str(officer.id),
        company=company,
        metadata={"name": officer.full_name},
    )
    return serialize_officer(officer)


@router.delete("/companies/{company_id}/officers/{officer_id}")
def delete_officer(request, company_id: str, officer_id: str):
    _, _, company = require_writer(request)
    if str(company.id) != company_id:
        raise HttpError(400, "La société active ne correspond pas.")
    officer = CompanyOfficer.objects.filter(id=officer_id, company=company).first()
    if not officer:
        raise HttpError(404, "Dirigeant introuvable.")
    officer.delete()
    record_audit(
        request,
        action="company.officer.delete",
        resource_type="officer",
        resource_id=officer_id,
        company=company,
    )
    return {"ok": True}
