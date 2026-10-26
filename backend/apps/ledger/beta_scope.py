"""BETA-SCOPE-01 — feature flags périmètre bêta privée (API + UI)."""

from __future__ import annotations

from django.conf import settings
from ninja.errors import HttpError

FEATURE_CONSOLIDATION = "consolidation"
FEATURE_CLASS9_CAGE = "class9_cage"
FEATURE_ESG = "esg"
FEATURE_ESCOMPTE = "escompte"

FEATURE_ENV_VARS = {
    FEATURE_CONSOLIDATION: "BETA_FEATURES_CONSOLIDATION",
    FEATURE_CLASS9_CAGE: "BETA_FEATURES_CLASS9_CAGE",
    FEATURE_ESG: "BETA_FEATURES_ESG",
    FEATURE_ESCOMPTE: "BETA_FEATURES_ESCOMPTE",
}

ALL_FEATURES = tuple(FEATURE_ENV_VARS.keys())


def is_beta_feature_enabled(name: str) -> bool:
    features = getattr(settings, "BETA_FEATURES", None) or {}
    return bool(features.get(name, True))


def require_beta_feature(name: str) -> None:
    if name not in FEATURE_ENV_VARS:
        raise ValueError(f"Feature inconnue: {name}")
    if not is_beta_feature_enabled(name):
        raise HttpError(
            403,
            "Fonctionnalité hors périmètre de la bêta privée.",
        )


def entry_requires_escompte(entry) -> bool:
    """True si la pièce déclenche la logique escompte (engagement ou lignes 415/564/565)."""
    from apps.ledger.models import Commitment
    from apps.ledger.services.escompte import discount_nominal_from_entry

    if Commitment.objects.filter(origin_entry_id=entry.pk).exists():
        return True
    nominal, _, _ = discount_nominal_from_entry(entry)
    return nominal > 0


def require_escompte_allowed_for_entry(entry) -> None:
    """Refus explicite si escompte désactivé et pièce concernée (pas de contournement silencieux)."""
    if is_beta_feature_enabled(FEATURE_ESCOMPTE):
        return
    if entry_requires_escompte(entry):
        raise HttpError(
            403,
            "Escompte d'effet hors périmètre de la bêta privée.",
        )


def beta_scope_payload() -> dict:
    return {
        "restrict_mode": bool(getattr(settings, "BETA_SCOPE_RESTRICT", False)),
        "consolidation": is_beta_feature_enabled(FEATURE_CONSOLIDATION),
        "class9_cage": is_beta_feature_enabled(FEATURE_CLASS9_CAGE),
        "esg": is_beta_feature_enabled(FEATURE_ESG),
        "escompte": is_beta_feature_enabled(FEATURE_ESCOMPTE),
    }
