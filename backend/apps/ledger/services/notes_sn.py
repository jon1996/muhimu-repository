"""Notes annexes du Système Normal — Titre IX chapitre 6 (notes 1–36)."""

from __future__ import annotations

import json
from typing import Any

from apps.ledger.services.pdf_disclaimers import DEFAULT_NOTE2_CONFORMITY

NOTE_TITLES: dict[int, str] = {
    1: "Sûretés réelles et engagements",
    2: "Règles et méthodes comptables",
    3: "Immobilisations incorporelles et corporelles",
    4: "Immobilisations financières",
    5: "Actif circulant HAO",
    6: "Stocks et encours",
    7: "Clients et produits à recevoir",
    8: "Autres créances",
    9: "Titres de placement",
    10: "Valeurs à encaisser",
    11: "Disponibilités",
    12: "Écarts de conversion",
    13: "Capital",
    14: "Primes et réserves",
    15: "Subventions, provisions réglementées et autres fonds propres",
    16: "Dettes financières, location-acquisition et provisions pour risques et charges",
    17: "Fournisseurs",
    18: "Dettes fiscales et sociales",
    19: "Autres dettes et provisions à court terme",
    20: "Banques, crédits d’escompte et de trésorerie",
    21: "Chiffre d’affaires et autres produits",
    22: "Achats",
    23: "Transports",
    24: "Services extérieurs",
    25: "Impôts et taxes",
    26: "Autres charges",
    27: "Personnel",
    28: "Provisions et dépréciations",
    29: "Résultat financier",
    30: "Résultat hors activités ordinaires",
    31: "Répartition du résultat et caractéristiques des cinq derniers exercices",
    32: "Production de l’exercice",
    33: "Achats destinés à la production",
    34: "Indicateurs financiers (SIG, CAFG, FR, BFE, TN)",
    35: "Informations sociales, environnementales et sociétales",
    36: "Tables de codes (forme juridique, régime fiscal, pays, activités)",
}

DEFAULT_CONFORMITY = DEFAULT_NOTE2_CONFORMITY


def _empty_item(number: int) -> dict[str, Any]:
    required = number == 2
    return {
        "number": number,
        "title": NOTE_TITLES[number],
        "status": "A" if required else "NA",
        "required": required,
        "body": "",
        "conformity": DEFAULT_CONFORMITY if required else "",
        "methods": "",
        "derogations": "",
        "extra": "",
    }


def default_notes() -> list[dict[str, Any]]:
    return [_empty_item(n) for n in range(1, 37)]


def parse_notes(raw: str | None) -> list[dict[str, Any]]:
    items = {item["number"]: item for item in default_notes()}
    text = (raw or "").strip()
    if not text:
        return [items[n] for n in range(1, 37)]
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        items[2]["extra"] = text
        items[2]["status"] = "A"
        return [items[n] for n in range(1, 37)]
    if not isinstance(payload, dict):
        return [items[n] for n in range(1, 37)]
    stored = payload.get("notes") or payload.get("items") or []
    if isinstance(stored, dict):
        stored = [{"number": int(key), **value} for key, value in stored.items()]
    for entry in stored:
        try:
            number = int(entry.get("number"))
        except (TypeError, ValueError):
            continue
        if number not in items:
            continue
        item = items[number]
        status = str(entry.get("status") or item["status"]).upper()
        item["status"] = "A" if status == "A" else "NA"
        item["body"] = str(entry.get("body") or "")
        item["conformity"] = str(entry.get("conformity") or item["conformity"])
        item["methods"] = str(entry.get("methods") or "")
        item["derogations"] = str(entry.get("derogations") or "")
        item["extra"] = str(entry.get("extra") or "")
    items[2]["status"] = "A"
    if not items[2]["conformity"].strip():
        items[2]["conformity"] = DEFAULT_CONFORMITY
    return [items[n] for n in range(1, 37)]


def serialize_notes(notes: list[dict[str, Any]]) -> str:
    payload = {"version": 1, "notes": []}
    for item in notes:
        number = int(item["number"])
        row = {
            "number": number,
            "status": "A" if number == 2 else ("A" if str(item.get("status", "")).upper() == "A" else "NA"),
            "body": item.get("body") or "",
        }
        if number == 2:
            row["conformity"] = item.get("conformity") or DEFAULT_CONFORMITY
            row["methods"] = item.get("methods") or ""
            row["derogations"] = item.get("derogations") or ""
            row["extra"] = item.get("extra") or ""
        payload["notes"].append(row)
    return json.dumps(payload, ensure_ascii=False)
