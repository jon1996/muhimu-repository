from ninja.errors import HttpError

from apps.tenancy.models import Company, Membership, Organization, Role

ADMIN_ROLES = {Role.OWNER, Role.ADMIN}
WRITE_ROLES = {Role.OWNER, Role.ADMIN, Role.ACCOUNTANT}


def require_membership(request) -> tuple[Organization, Membership]:
    if not request.organization or not request.membership:
        raise HttpError(403, "Organisation absente ou accès refusé.")
    return request.organization, request.membership


def require_admin(request) -> tuple[Organization, Membership]:
    org, membership = require_membership(request)
    if membership.role not in ADMIN_ROLES:
        raise HttpError(403, "Droits administrateur requis.")
    return org, membership


def require_company(request) -> tuple[Organization, Membership, Company]:
    org, membership = require_membership(request)
    if not request.company:
        raise HttpError(400, "Société active requise (en-tête X-Company-Id).")
    return org, membership, request.company


def require_writer(request) -> tuple[Organization, Membership, Company]:
    org, membership, company = require_company(request)
    if membership.role not in WRITE_ROLES:
        raise HttpError(403, "Saisie comptable non autorisée pour ce rôle.")
    return org, membership, company


def require_org_writer(request) -> tuple[Organization, Membership]:
    org, membership = require_membership(request)
    if membership.role not in WRITE_ROLES:
        raise HttpError(403, "Saisie comptable non autorisée pour ce rôle.")
    return org, membership
