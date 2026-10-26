"""Mentions legales et avertissements beta pour les PDF et notes (PDF-CLAIM)."""

from __future__ import annotations

# Texte affiche dans les PDF (latin-1 via pdf_text).
PDF_BETA_DISCLAIMER_TITLE = "DOCUMENT DE TEST - DONNEES FICTIVES"

PDF_BETA_DISCLAIMER_LINES = (
    "Etat genere par MUHIMU Accounting, version beta.",
    "Presentation et correspondances comptables en cours de validation.",
    "Document non certifie et non destine au depot reglementaire.",
)

PDF_FOOTER_LEFT = (
    "Version beta — document non certifie. "
    "Numerotation et horodatage internes MUHIMU Accounting."
)

NOTE2_SECTION_LABEL = "A. Referentiel comptable et presentation (SYSCOHADA / PCGO)"

DEFAULT_NOTE2_CONFORMITY = (
    "Les etats sont produits a partir du referentiel SYSCOHADA et du PCGO. "
    "La correspondance des postes et la presentation sont en cours de validation "
    "dans MUHIMU Accounting (version beta). "
    "Ce libelle ne constitue ni une attestation de conformite, ni une certification, "
    "ni une validation par un expert-comptable."
)

# Sous-chaines interdites dans les PDF generes (revendications non attestees).
FORBIDDEN_PDF_CLAIM_SUBSTRINGS = (
    "conformement au SYSCOHADA",
    "conformement au syscohada",
    "certifie SYSCOHADA",
    "certifie OHADA",
    "conforme SYSCOHADA",
    "sans reserve.",
    "validé par un expert",
    "valide par un expert",
    "etats financiers officiels",
)
