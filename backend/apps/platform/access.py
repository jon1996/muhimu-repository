from apps.platform.models import DemoGrant
from apps.tenancy.models import OrganizationType


def demo_grant_for(user) -> DemoGrant | None:
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    return DemoGrant.objects.filter(user=user, is_active=True).first()


def user_can_access_organization(user, organization) -> bool:
    """Les dossiers démo n'apparaissent dans l'ERP que si un grant SaaS est actif."""
    if organization is None:
        return False
    if not organization.is_demo:
        return True
    grant = demo_grant_for(user)
    if grant is None:
        return False
    if organization.type == OrganizationType.SME:
        return bool(grant.access_pme)
    if organization.type == OrganizationType.CABINET:
        return bool(grant.access_cabinet)
    return False
