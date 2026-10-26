from apps.platform.access import user_can_access_organization
from apps.tenancy.models import Company, CompanyAccess, Membership, OrganizationType, Role
from apps.tenancy.rls import bind_tenant_context, clear_tenant_context


class TenantMiddleware:
    """
    Résout l'organisation / société à partir des en-têtes et pose le contexte
    PostgreSQL utilisé par les politiques RLS (A1′).

    La console platform s'exécute sous le rôle PG ``muhimu_platform`` (BYPASSRLS) :
    aucun GUC de bypass n'est posé. L'ERP utilise ``muhimu_app`` (NOBYPASSRLS).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.organization = None
        request.membership = None
        request.company = None

        user = getattr(request, "user", None)
        # Identité d'abord : DemoGrant est isolé par user_id (RLS).
        _apply_rls_context(request)

        if user is not None and user.is_authenticated:
            slug = request.headers.get("X-Organization-Slug")
            if slug:
                membership = (
                    Membership.objects.select_related("organization")
                    .filter(user=user, is_active=True, organization__slug=slug)
                    .first()
                )
                if membership and user_can_access_organization(user, membership.organization):
                    request.membership = membership
                    request.organization = membership.organization
                    _apply_rls_context(request)

        if user is not None and user.is_authenticated and request.organization:
            company_id = request.headers.get("X-Company-Id")
            if company_id:
                company = Company.objects.filter(
                    id=company_id, organization=request.organization
                ).first()
                if company and user_can_access_company(user, request.membership, company):
                    request.company = company
        try:
            return self.get_response(request)
        finally:
            try:
                clear_tenant_context()
            except Exception:
                pass


def user_can_access_company(user, membership: Membership | None, company: Company) -> bool:
    if membership is None or company.organization_id != membership.organization_id:
        return False
    if membership.role in (Role.OWNER, Role.ADMIN):
        return True
    if membership.organization.type == OrganizationType.SME:
        return True
    return CompanyAccess.objects.filter(user=user, company=company).exists()


def companies_queryset_for(user, membership: Membership):
    qs = Company.objects.filter(organization=membership.organization, is_active=True)
    if membership.role in (Role.OWNER, Role.ADMIN):
        return qs
    if membership.organization.type == OrganizationType.SME:
        return qs
    return qs.filter(accesses__user=user).distinct()


def _apply_rls_context(request) -> None:
    org_id = str(request.organization.id) if getattr(request, "organization", None) else ""
    user_id = (
        str(request.user.id)
        if getattr(request, "user", None) and request.user.is_authenticated
        else ""
    )
    bind_tenant_context(user_id=user_id, organization_id=org_id, is_local=False)
