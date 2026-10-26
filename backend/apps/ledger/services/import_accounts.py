from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from django.db import transaction

from apps.ledger.models import Account
from apps.ledger.services.setup import relink_account_parents
from apps.ledger.taxonomy import (
    ancestor_codes,
    classify,
    infer_level,
    normalize_code,
)
from apps.tenancy.models import Company

HEADER_ALIASES = {
    "code": "code",
    "compte": "code",
    "numero": "code",
    "n°": "code",
    "intitule": "label",
    "intitulé": "label",
    "libelle": "label",
    "libellé": "label",
    "label": "label",
    "nom": "label",
    "imputable": "is_postable",
    "postable": "is_postable",
    "collectif": "is_collective",
    "notes": "notes",
    "commentaire": "notes",
}

TEMPLATE_CSV = (
    "code;intitule;imputable;collectif;notes\n"
    "4111;Clients nationaux;oui;non;subdivision du 411\n"
    "411-SOCOCIM;SOCOCIM Industries;oui;non;auxiliaire client\n"
    "401-TOTAL;TotalEnergies Marketing;oui;non;auxiliaire fournisseur\n"
)

MAX_IMPORT_BYTES = 2 * 1024 * 1024


@dataclass
class ImportRow:
    line: int
    code: str
    label: str
    is_postable: bool | None = None
    is_collective: bool | None = None
    notes: str = ""
    action: str = "create"
    errors: list[str] = field(default_factory=list)
    level: str = ""
    family: str = ""
    account_class: str = ""


@dataclass
class ImportReport:
    rows: list[ImportRow]
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    applied: bool = False


def _as_bool(raw: str | None) -> bool | None:
    if raw is None or str(raw).strip() == "":
        return None
    return str(raw).strip().lower() in {"1", "oui", "true", "yes", "o", "vrai"}


def parse_csv(content: bytes) -> list[dict]:
    text = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = content.decode("utf-8", errors="replace")
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,|\t") if sample.strip() else csv.excel
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows = []
    for raw in reader:
        mapped: dict[str, str] = {}
        for key, value in raw.items():
            alias = HEADER_ALIASES.get((key or "").strip().lower())
            if alias:
                mapped[alias] = (value or "").strip()
        if mapped.get("code") or mapped.get("label"):
            rows.append(mapped)
    return rows


def _sort_key(raw: dict) -> tuple[int, str]:
    code = normalize_code(raw.get("code", ""))
    return (len(code), code)


def preview_import(company: Company, raw_rows: list[dict]) -> ImportReport:
    existing = {a.code for a in Account.objects.filter(company=company).only("code")}
    incoming_codes: set[str] = set()
    report = ImportReport(rows=[])
    for index, raw in enumerate(sorted(raw_rows, key=_sort_key), start=2):
        code = normalize_code(raw.get("code", ""))
        label = (raw.get("label") or "").strip()
        info = classify(code) if code else {}
        row = ImportRow(
            line=index,
            code=code,
            label=label,
            is_postable=_as_bool(raw.get("is_postable")),
            is_collective=_as_bool(raw.get("is_collective")),
            notes=(raw.get("notes") or "")[:255],
            level=info.get("level", ""),
            family=info.get("family", ""),
            account_class=info.get("account_class", ""),
        )
        if not code:
            row.errors.append("Code manquant.")
        elif not code[0].isdigit() or code[0] not in "12345678":
            row.errors.append("Le code doit commencer par une classe SYSCOHADA (1 à 8).")
        if not label:
            row.errors.append("Intitulé manquant.")
        if code and code in incoming_codes:
            row.errors.append("Code en double dans le fichier.")
        if code:
            incoming_codes.add(code)
        if code and infer_level(code) != "class":
            ancestors = ancestor_codes(code)
            if ancestors and not any(parent in existing or parent in incoming_codes for parent in ancestors):
                row.errors.append(f"Aucun parent ({', '.join(ancestors)}) dans le plan ni dans le fichier.")
        if code in existing:
            row.action = "update"
        if row.errors:
            report.errors += 1
        elif row.action == "update":
            report.updated += 1
        else:
            report.created += 1
        report.rows.append(row)
    return report


@transaction.atomic
def apply_import(company: Company, raw_rows: list[dict]) -> ImportReport:
    report = preview_import(company, raw_rows)
    if report.errors:
        return report

    existing = {a.code: a for a in Account.objects.filter(company=company)}
    to_create: list[Account] = []
    to_update: list[Account] = []

    for row in report.rows:
        account = existing.get(row.code)
        is_new = account is None
        if is_new:
            account = Account(
                organization=company.organization,
                company=company,
                is_syscohada=False,
            )
        account.code = row.code
        account.label = row.label
        account.notes = row.notes
        if is_new:
            account.is_syscohada = False
        account.apply_taxonomy()
        if row.is_postable is not None:
            account.is_postable = row.is_postable and account.level != "class"
        if row.is_collective is not None:
            account.is_collective = row.is_collective
        if is_new:
            to_create.append(account)
            existing[row.code] = account
        else:
            to_update.append(account)

    if to_create:
        Account.objects.bulk_create(to_create)
    if to_update:
        Account.objects.bulk_update(
            to_update,
            [
                "code",
                "label",
                "notes",
                "account_class",
                "level",
                "family",
                "sense",
                "is_postable",
                "is_collective",
                "is_syscohada",
            ],
        )
    relink_account_parents(company)
    report.applied = True
    return report


def report_to_dict(report: ImportReport) -> dict:
    return {
        "applied": report.applied,
        "created": report.created,
        "updated": report.updated,
        "errors": report.errors,
        "rows": [
            {
                "line": row.line,
                "code": row.code,
                "label": row.label,
                "action": row.action,
                "errors": row.errors,
                "level": row.level,
                "family": row.family,
                "account_class": row.account_class,
            }
            for row in report.rows[:400]
        ],
    }
