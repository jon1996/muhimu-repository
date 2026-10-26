"""Fiches officielles Titre VII (contenu, fonctionnement, exclusions)."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from apps.ledger.taxonomy import code_digits, infer_parent_code, normalize_code

FOOTER_NOISE = re.compile(r"COMPTE\s+\d+\s*:\s*[^.•]{0,80}")
ALIASES = {"62": "63"}


@lru_cache(maxsize=1)
def load_fiches() -> dict[str, dict]:
    path = Path(__file__).parent / "data" / "pcgo_fiches.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _tidy(text: str) -> str:
    text = FOOTER_NOISE.sub(" ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def resolve_fiche(code: str) -> dict | None:
    cleaned = normalize_code(code)
    digits = code_digits(cleaned)
    fiches = load_fiches()
    candidates: list[str] = []
    current = digits or cleaned
    while current:
        candidates.append(ALIASES.get(current, current))
        parent = infer_parent_code(current)
        if not parent or parent == current:
            break
        current = parent
    if digits:
        candidates.append(digits[0])
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        raw = fiches.get(candidate)
        if not raw:
            continue
        return {
            "code": cleaned or digits,
            "fiche_code": raw["code"],
            "title": raw.get("title") or "",
            "contenu": _tidy(raw.get("contenu", "")),
            "subdivisions": _tidy(raw.get("subdivisions", "")),
            "commentaires": _tidy(raw.get("commentaires", "")),
            "fonctionnement": _tidy(raw.get("fonctionnement", "")),
            "exclusions": _tidy(raw.get("exclusions", "")),
            "controles": _tidy(raw.get("controles", "")),
            "debit": [_tidy(item) for item in raw.get("debit", []) if _tidy(item)],
            "credit": [_tidy(item) for item in raw.get("credit", []) if _tidy(item)],
        }
    return None
