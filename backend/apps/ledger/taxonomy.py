"""Taxonomie SYSCOHADA du plan de comptes.

Titre VII : classe → compte à 2 chiffres → principal → divisionnaire (4) →
subdivision d'entité (5+ ou suffixe).
"""

from __future__ import annotations

CLASS_META: dict[str, dict] = {
    "1": {
        "family": "resource",
        "family_label": "Ressources durables",
        "sense": "credit",
        "statement": "bilan",
        "short": "Capitaux",
    },
    "2": {
        "family": "fixed_asset",
        "family_label": "Actif immobilisé",
        "sense": "debit",
        "statement": "bilan",
        "short": "Immos",
    },
    "3": {
        "family": "stock",
        "family_label": "Stocks",
        "sense": "debit",
        "statement": "bilan",
        "short": "Stocks",
    },
    "4": {
        "family": "third_party",
        "family_label": "Tiers",
        "sense": "either",
        "statement": "bilan",
        "short": "Tiers",
    },
    "5": {
        "family": "treasury",
        "family_label": "Trésorerie",
        "sense": "debit",
        "statement": "bilan",
        "short": "Tréso",
    },
    "6": {
        "family": "expense",
        "family_label": "Charges AO",
        "sense": "debit",
        "statement": "result",
        "short": "Charges",
    },
    "7": {
        "family": "income",
        "family_label": "Produits AO",
        "sense": "credit",
        "statement": "result",
        "short": "Produits",
    },
    "8": {
        "family": "other",
        "family_label": "Autres charges / produits",
        "sense": "either",
        "statement": "result",
        "short": "HAO",
    },
    "9": {
        "family": "off_balance",
        "family_label": "Engagements / CAGE",
        "sense": "either",
        "statement": "hors_bilan",
        "short": "Classe 9",
    },
}

COLLECTIVE_CODES = {
    "40",
    "401",
    "41",
    "411",
    "42",
    "421",
    "52",
    "521",
    "57",
    "571",
}

LEVEL_LABELS = {
    "class": "Classe",
    "subclass": "Compte à 2 chiffres",
    "principal": "Compte principal",
    "secondary": "Divisionnaire",
    "auxiliary": "Subdivision d'entité",
}

SENSE_LABELS = {
    "debit": "Débiteur",
    "credit": "Créditeur",
    "either": "Mixte",
}

FAMILY_LABELS = {meta["family"]: meta["family_label"] for meta in CLASS_META.values()}


def normalize_code(raw: str) -> str:
    return str(raw or "").strip().replace(" ", "").upper()


def code_digits(code: str) -> str:
    return "".join(ch for ch in normalize_code(code) if ch.isdigit())


def infer_level(code: str) -> str:
    cleaned = normalize_code(code)
    if "-" in cleaned or "_" in cleaned:
        return "auxiliary"
    digits = code_digits(cleaned)
    n = len(digits)
    if n <= 1:
        return "class"
    if n == 2:
        return "subclass"
    if n == 3:
        return "principal"
    if n == 4:
        return "secondary"
    return "auxiliary"


def infer_family(code: str) -> str:
    digits = code_digits(code)
    meta = CLASS_META.get(digits[:1] if digits else "")
    return meta["family"] if meta else "other"


def infer_sense(code: str) -> str:
    digits = code_digits(code)
    if not digits:
        return "either"
    klass = digits[0]
    if klass == "9" and len(digits) >= 2:
        if digits[1] == "0":
            return "debit"
        if digits[1] == "1":
            return "credit"
        return "either"
    if klass == "8" and len(digits) >= 2:
        # Impair = charge (débit), pair = produit (crédit) — PCGO.
        return "debit" if int(digits[1]) % 2 == 1 else "credit"
    meta = CLASS_META.get(klass)
    return meta["sense"] if meta else "either"


def infer_parent_code(code: str) -> str | None:
    cleaned = normalize_code(code)
    for sep in ("-", "_"):
        if sep in cleaned:
            return cleaned.split(sep, 1)[0]
    digits = code_digits(cleaned)
    if len(digits) <= 1:
        return None
    return digits[:-1]


def ancestor_codes(code: str) -> list[str]:
    codes: list[str] = []
    seen: set[str] = set()
    current = infer_parent_code(code)
    while current and current not in seen:
        codes.append(current)
        seen.add(current)
        current = infer_parent_code(current)
    return codes


def code_anatomy(code: str) -> dict[str, str | None]:
    cleaned = normalize_code(code)
    digits = code_digits(cleaned)
    suffix = None
    for sep in ("-", "_"):
        if sep in cleaned:
            suffix = cleaned.split(sep, 1)[1]
            break
    entity = digits[4:] if len(digits) >= 5 else None
    if suffix:
        entity = suffix
    return {
        "class": digits[:1] or None,
        "two_digit": digits[:2] if len(digits) >= 2 else None,
        "principal": digits[:3] if len(digits) >= 3 else None,
        "divisionary": digits[:4] if len(digits) >= 4 else None,
        "entity": entity,
        "subclass": digits[:2] if len(digits) >= 2 else None,
        "secondary": digits[:4] if len(digits) >= 4 else None,
        "auxiliary": entity,
    }


def infer_parallel(code: str) -> dict[str, str] | None:
    digits = code_digits(code)
    if not digits:
        return None
    klass = digits[0]
    rest = digits[1:]
    if klass == "6":
        return {
            "code": f"7{rest}",
            "kind": "charge_produit",
            "label": "Produit parallèle (classe 7)",
        }
    if klass == "7":
        return {
            "code": f"6{rest}",
            "kind": "charge_produit",
            "label": "Charge parallèle (classe 6)",
        }
    if klass == "8" and len(digits) >= 2:
        second = int(digits[1])
        if second % 2 == 1:
            return {
                "code": f"8{second + 1}{digits[2:]}",
                "kind": "hao_pair",
                "label": "Produit HAO pair",
            }
        return {
            "code": f"8{second - 1}{digits[2:]}",
            "kind": "hao_pair",
            "label": "Charge HAO impaire",
        }
    return None


def account_reading(code: str) -> dict:
    """Constantes de lecture du code — Titre VII, section 1.2."""
    digits = code_digits(code)
    klass = digits[:1]
    n = len(digits)
    constants: list[dict] = []

    if n >= 2 and digits[1] == "9":
        if klass in "12345":
            constants.append(
                {
                    "kind": "nine_class",
                    "title": "Terminaison 9 à 2 chiffres",
                    "detail": "Identifie les dépréciations ou provisions de la classe (19, 29, 39, 49, 59).",
                }
            )
        elif klass in "67":
            constants.append(
                {
                    "kind": "nine_management",
                    "title": "Terminaison 9 — classes 6 et 7",
                    "detail": "Se rapporte aux opérations concernant les provisions (69 / 79).",
                }
            )

    pos3 = n >= 3 and digits[2] == "9"
    pos4 = n >= 4 and digits[3] == "9"
    if pos3 or pos4:
        if klass == "2":
            constants.append(
                {
                    "kind": "nine_class2_exception",
                    "title": "Exception classe 2",
                    "detail": "En classe 2, le 9 en 3e ou 4e position n’annonce pas un solde inversé (immos en cours, etc.).",
                }
            )
        else:
            constants.append(
                {
                    "kind": "nine_inverted",
                    "title": "Chiffre 9 en 3e ou 4e position",
                    "detail": "Solde inversé par rapport au parent : 409 fournisseurs débiteurs, 419 clients créditeurs, RRR (6019…).",
                }
            )

    if n >= 3 and digits[-1] == "8":
        if klass in "678":
            constants.append(
                {
                    "kind": "eight_other",
                    "title": "Terminaison 8",
                    "detail": "Regroupe les autres opérations du même niveau, hors comptes 1 à 7 (ex. 758, 668).",
                }
            )
        else:
            constants.append(
                {
                    "kind": "eight_other",
                    "title": "Terminaison 8",
                    "detail": "Regroupe en général les autres / divers du même niveau.",
                }
            )

    if n >= 3 and "0" in digits[2:4]:
        constants.append(
            {
                "kind": "zero_neutral",
                "title": "Zéro en 3e ou 4e position",
                "detail": "Aucune signification particulière dans la codification OHADA.",
            }
        )

    parallel = infer_parallel(code)
    return {
        "constants": constants,
        "parallel_code": parallel["code"] if parallel else None,
        "parallel_label": parallel["label"] if parallel else None,
        "parallel_kind": parallel["kind"] if parallel else None,
    }


def is_collective_code(code: str) -> bool:
    cleaned = normalize_code(code)
    if "-" in cleaned or "_" in cleaned:
        return False
    return code_digits(cleaned) in COLLECTIVE_CODES


def classify(code: str) -> dict:
    cleaned = normalize_code(code)
    digits = code_digits(cleaned)
    klass = digits[:1] if digits else ""
    meta = CLASS_META.get(klass, {})
    level = infer_level(cleaned)
    return {
        "code": cleaned,
        "digits": digits,
        "account_class": klass,
        "level": level,
        "family": infer_family(cleaned),
        "sense": infer_sense(cleaned),
        "statement": meta.get("statement", "bilan"),
        "is_collective": is_collective_code(cleaned),
        "is_postable": level != "class",
        "parent_code": infer_parent_code(cleaned),
        "anatomy": code_anatomy(cleaned),
        "reading": account_reading(cleaned),
    }
