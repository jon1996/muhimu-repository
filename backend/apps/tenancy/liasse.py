"""Libellés fiche liasse R1–R3 (Titre IX ch. 2) et note 36."""

from __future__ import annotations

from apps.tenancy.ohada import country_label

LEGAL_FORM_LABELS = {
    "sa": "SA",
    "sas": "SAS",
    "sarl": "SARL",
    "suarl": "SUARL",
    "snc": "SNC",
    "scs": "SCS",
    "gie": "GIE",
    "ets": "Entreprise individuelle",
    "coop": "Coopérative",
    "other": "Autre",
}

TAX_REGIME_LABELS = {
    "reel_normal": "Réel normal",
    "reel_simplifie": "Réel simplifié",
    "synthetique": "Synthétique / unique",
    "exemption": "Exonéré",
    "other": "Autre",
}

CONTROL_LABELS = {
    "private_national": "Privé national",
    "public": "Public",
    "private_foreign": "Privé étranger",
}

OFFICER_ROLE_LABELS = {
    "manager": "Gérant",
    "chairman": "Président",
    "director": "Directeur général",
    "board": "Administrateur",
    "other": "Autre",
}

IDENTITY_REQUIRED_FIELDS = (
    "legal_name",
    "country_code",
    "address",
    "city",
    "rccm",
    "tax_id",
    "legal_form",
    "tax_regime",
)


def identity_missing_fields(company, officers=None) -> list[str]:
    missing = [
        field
        for field in IDENTITY_REQUIRED_FIELDS
        if not str(getattr(company, field, "") or "").strip()
    ]
    if officers is None:
        related = getattr(company, "officers", None)
        if related is None:
            officers = []
        elif hasattr(related, "all"):
            officers = list(related.all())
        else:
            officers = list(related)
    if not officers:
        missing.append("officers")
    return missing


def identity_is_complete(company, officers=None) -> bool:
    return not identity_missing_fields(company, officers=officers)

def note36_text(company) -> str:
    parts = []
    if company.legal_form:
        parts.append(f"forme {LEGAL_FORM_LABELS.get(company.legal_form, company.legal_form)}")
    if company.tax_regime:
        parts.append(f"régime fiscal {TAX_REGIME_LABELS.get(company.tax_regime, company.tax_regime)}")
    if company.country_code:
        parts.append(f"pays {country_label(company.country_code)}")
    if company.naema_code:
        parts.append(f"NAEMA {company.naema_code}")
    if company.control_kind:
        parts.append(f"contrôle {CONTROL_LABELS.get(company.control_kind, company.control_kind)}")
    if company.establishments_domestic or company.establishments_foreign:
        parts.append(
            f"établissements {company.establishments_domestic} dans le pays"
            + (f" / {company.establishments_foreign} hors pays" if company.establishments_foreign else "")
        )
    if company.distinct_branch_accounts:
        parts.append("comptabilité distincte par établissement")
    return " · ".join(parts)


def serialize_officer(officer) -> dict:
    return {
        "id": str(officer.id),
        "full_name": officer.full_name,
        "role": officer.role,
        "role_label": OFFICER_ROLE_LABELS.get(officer.role, officer.role),
        "nationality": officer.nationality,
        "position": officer.position,
    }


def identity_payload(company) -> dict:
    officers = [serialize_officer(item) for item in company.officers.all()]
    missing = identity_missing_fields(company, officers=officers)
    return {
        "acronym": company.acronym,
        "address": company.address,
        "city": company.city,
        "postal_code": company.postal_code,
        "phone": company.phone,
        "email": company.email,
        "tax_id": company.tax_id,
        "rccm": company.rccm,
        "social_register": company.social_register,
        "legal_form": company.legal_form,
        "legal_form_label": LEGAL_FORM_LABELS.get(company.legal_form, ""),
        "tax_regime": company.tax_regime,
        "tax_regime_label": TAX_REGIME_LABELS.get(company.tax_regime, ""),
        "naema_code": company.naema_code,
        "control_kind": company.control_kind,
        "control_label": CONTROL_LABELS.get(company.control_kind, ""),
        "country_label": country_label(company.country_code),
        "establishments_domestic": company.establishments_domestic,
        "establishments_foreign": company.establishments_foreign,
        "distinct_branch_accounts": company.distinct_branch_accounts,
        "auditor_name": company.auditor_name,
        "auditor_order_no": company.auditor_order_no,
        "signatory_name": company.signatory_name,
        "signatory_title": company.signatory_title,
        "banks": company.banks,
        "officers": officers,
        "identity_complete": not missing,
        "identity_missing": missing,
    }
