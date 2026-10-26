"""Notes annexes SN calculées depuis la balance (Titre IX ch. 6–7)."""

from __future__ import annotations

from decimal import Decimal

from apps.ledger.services.sn_map import bilan_amounts, cr_amounts, sum_credit_side, sum_debit_side


def _join(parts: list[str]) -> str:
    return " · ".join(part for part in parts if part)


def _amt(label: str, value: Decimal) -> str:
    if not value:
        return ""
    return f"{label} : {value}"


def note4_text(rows: list[dict]) -> str:
    amounts = bilan_amounts(rows)
    return _join(
        [
            _amt("Participations 26 (AR)", amounts["AR"].net),
            _amt("Autres immobilisations financières 27 (AS)", amounts["AS"].net),
        ]
    )


def note5_text(rows: list[dict]) -> str:
    amounts = bilan_amounts(rows)
    return _amt("Actif circulant HAO 485/488 (BA)", amounts["BA"].net)


def note8_text(rows: list[dict]) -> str:
    """Autres créances — poste BJ (soldes débiteurs 185, 42–47 hors 478)."""
    return _join(
        [
            _amt("Personnel 42", sum_debit_side(rows, ("42",))),
            _amt("Organismes sociaux 43", sum_debit_side(rows, ("43",))),
            _amt("État 44", sum_debit_side(rows, ("44",))),
            _amt("Groupe 45", sum_debit_side(rows, ("45",))),
            _amt("Associés 46", sum_debit_side(rows, ("46",))),
            _amt("Débiteurs divers 47", sum_debit_side(rows, ("47",), ("478", "479"))),
            _amt("Comptes de liaison 185", sum_debit_side(rows, ("185",))),
        ]
    )


def note9_text(rows: list[dict]) -> str:
    amounts = bilan_amounts(rows)
    return _amt("Titres de placement 50 (BQ)", amounts["BQ"].net)


def note10_text(rows: list[dict]) -> str:
    amounts = bilan_amounts(rows)
    return _amt("Valeurs à encaisser 51 (BR)", amounts["BR"].net)


def note11_text(rows: list[dict]) -> str:
    """Disponibilités — poste BS (soldes débiteurs 52–55, 57, 581/582)."""
    return _join(
        [
            _amt("Banques 52", sum_debit_side(rows, ("52",))),
            _amt("Établissements financiers 53", sum_debit_side(rows, ("53",))),
            _amt("Instruments de trésorerie 54", sum_debit_side(rows, ("54",))),
            _amt("Monnaie électronique 55", sum_debit_side(rows, ("55",))),
            _amt("Caisse 57", sum_debit_side(rows, ("57",))),
            _amt("Virements de fonds 581/582", sum_debit_side(rows, ("581", "582"))),
        ]
    )


def note12_text(rows: list[dict]) -> str:
    amounts = bilan_amounts(rows)
    return _join(
        [
            _amt("Écart de conversion-actif 478 (BU)", amounts["BU"].net),
            _amt("Écart de conversion-passif 479 (DV)", amounts["DV"].net),
        ]
    )


def note16_text(rows: list[dict]) -> str:
    amounts = bilan_amounts(rows)
    return _join(
        [
            _amt("Emprunts et dettes financières 16 (DA)", amounts["DA"].net),
            _amt("Dettes de location-acquisition 17 (DB)", amounts["DB"].net),
            _amt("Provisions pour risques et charges 19 (DC)", amounts["DC"].net),
        ]
    )


def note18_text(rows: list[dict]) -> str:
    """Dettes fiscales et sociales — poste DK (soldes créditeurs 42–44)."""
    return _join(
        [
            _amt("Personnel 42", sum_credit_side(rows, ("42",))),
            _amt("Organismes sociaux 43", sum_credit_side(rows, ("43",))),
            _amt("État 44", sum_credit_side(rows, ("44",))),
        ]
    )


def note19_text(rows: list[dict]) -> str:
    amounts = bilan_amounts(rows)
    return _join(
        [
            _amt("Autres dettes 185/45–47 (DM)", amounts["DM"].net),
            _amt("Provisions à court terme 499/599 (DN)", amounts["DN"].net),
        ]
    )


def note20_text(rows: list[dict]) -> str:
    amounts = bilan_amounts(rows)
    return _join(
        [
            _amt("Crédits d’escompte 564/565 (DQ)", amounts["DQ"].net),
            _amt("Crédits de trésorerie 52/53/561/566 (DR)", amounts["DR"].net),
        ]
    )


NOTE_BUILDERS = {
    4: note4_text,
    5: note5_text,
    8: note8_text,
    9: note9_text,
    10: note10_text,
    11: note11_text,
    12: note12_text,
    16: note16_text,
    18: note18_text,
    19: note19_text,
    20: note20_text,
}


def _cr_join(values: dict, items: list[tuple[str, str]]) -> str:
    return _join([_amt(f"{label} ({code})", values[code]) for code, label in items])


def note21_text(rows: list[dict]) -> str:
    v = cr_amounts(rows)
    return _cr_join(
        v,
        [
            ("TA", "Ventes de marchandises"),
            ("TB", "Ventes de produits fabriqués"),
            ("TC", "Travaux et services vendus"),
            ("TD", "Produits accessoires"),
            ("XB", "Chiffre d’affaires"),
            ("TE", "Production stockée"),
            ("TF", "Production immobilisée"),
            ("TG", "Subventions d’exploitation"),
            ("TH", "Autres produits"),
            ("TI", "Transferts de charges d’exploitation"),
        ],
    )


def note22_text(rows: list[dict]) -> str:
    v = cr_amounts(rows)
    return _cr_join(
        v,
        [
            ("RA", "Achats de marchandises"),
            ("RB", "Variation stocks marchandises"),
            ("RC", "Achats de matières"),
            ("RD", "Variation stocks matières"),
            ("RE", "Autres achats"),
            ("RF", "Variation autres approvisionnements"),
        ],
    )


def note23_text(rows: list[dict]) -> str:
    return _cr_join(cr_amounts(rows), [("RG", "Transports")])


def note24_text(rows: list[dict]) -> str:
    return _cr_join(cr_amounts(rows), [("RH", "Services extérieurs")])


def note25_text(rows: list[dict]) -> str:
    return _cr_join(cr_amounts(rows), [("RI", "Impôts et taxes")])


def note26_text(rows: list[dict]) -> str:
    return _cr_join(cr_amounts(rows), [("RJ", "Autres charges")])


def note27_text(rows: list[dict]) -> str:
    return _cr_join(cr_amounts(rows), [("RK", "Charges de personnel")])


def note28_text(rows: list[dict]) -> str:
    v = cr_amounts(rows)
    return _cr_join(
        v,
        [
            ("RL", "Dotations d’exploitation"),
            ("TJ", "Reprises d’exploitation"),
            ("RN", "Dotations financières"),
            ("TL", "Reprises financières"),
        ],
    )


def note29_text(rows: list[dict]) -> str:
    v = cr_amounts(rows)
    return _cr_join(
        v,
        [
            ("TK", "Revenus financiers"),
            ("TL", "Reprises financières"),
            ("TM", "Transferts de charges financières"),
            ("RM", "Frais financiers"),
            ("RN", "Dotations financières"),
            ("XF", "Résultat financier"),
        ],
    )


def note30_text(rows: list[dict]) -> str:
    v = cr_amounts(rows)
    return _cr_join(
        v,
        [
            ("TN", "Produits des cessions d’immobilisations"),
            ("TO", "Autres produits HAO"),
            ("RO", "Valeurs comptables des cessions"),
            ("RP", "Autres charges HAO"),
            ("XH", "Résultat HAO"),
            ("RQ", "Participation des travailleurs"),
            ("RS", "Impôts sur le résultat"),
        ],
    )


def note32_text(rows: list[dict]) -> str:
    v = cr_amounts(rows)
    production = v["TB"] + v["TC"] + v["TE"] + v["TF"]
    return _join(
        [
            _amt("Production de l’exercice (TB+TC+TE+TF)", production),
            _amt("Ventes de produits fabriqués (TB)", v["TB"]),
            _amt("Travaux et services vendus (TC)", v["TC"]),
            _amt("Production stockée (TE)", v["TE"]),
            _amt("Production immobilisée (TF)", v["TF"]),
        ]
    )


def note33_text(rows: list[dict]) -> str:
    v = cr_amounts(rows)
    return _cr_join(
        v,
        [
            ("RC", "Achats de matières"),
            ("RD", "Variation stocks matières"),
            ("RE", "Autres achats"),
            ("RF", "Variation autres approvisionnements"),
        ],
    )


CR_NOTE_BUILDERS = {
    21: note21_text,
    22: note22_text,
    23: note23_text,
    24: note24_text,
    25: note25_text,
    26: note26_text,
    27: note27_text,
    28: note28_text,
    29: note29_text,
    30: note30_text,
    32: note32_text,
    33: note33_text,
}


def computed_balance_notes(rows: list[dict]) -> dict[int, str]:
    out: dict[int, str] = {}
    for number, builder in NOTE_BUILDERS.items():
        text = builder(rows)
        if text:
            out[number] = text
    return out


def computed_cr_notes(rows: list[dict]) -> dict[int, str]:
    out: dict[int, str] = {}
    for number, builder in CR_NOTE_BUILDERS.items():
        text = builder(rows)
        if text:
            out[number] = text
    return out
