"""Correspondance officielle Titre IX ch. 7 : PCGO → postes SN (AD–DZ, TA–XI, ZA–ZH)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

ZERO = Decimal("0")


def _d(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))


def matches(code: str, include: tuple[str, ...], exclude: tuple[str, ...] = ()) -> bool:
    if not any(code.startswith(prefix) for prefix in include):
        return False
    if exclude and any(code.startswith(prefix) for prefix in exclude):
        return False
    return True


def net_debit(row: dict) -> Decimal:
    return _d(row["close_debit"]) - _d(row["close_credit"])


def net_credit(row: dict) -> Decimal:
    return _d(row["close_credit"]) - _d(row["close_debit"])


def sum_net_debit(rows: list[dict], include: tuple[str, ...], exclude: tuple[str, ...] = ()) -> Decimal:
    return sum((net_debit(row) for row in rows if matches(row["code"], include, exclude)), ZERO)


def sum_net_credit(rows: list[dict], include: tuple[str, ...], exclude: tuple[str, ...] = ()) -> Decimal:
    return sum((net_credit(row) for row in rows if matches(row["code"], include, exclude)), ZERO)


def sum_debit_side(rows: list[dict], include: tuple[str, ...], exclude: tuple[str, ...] = ()) -> Decimal:
    total = ZERO
    for row in rows:
        if not matches(row["code"], include, exclude):
            continue
        value = net_debit(row)
        if value > 0:
            total += value
    return total


def sum_credit_side(rows: list[dict], include: tuple[str, ...], exclude: tuple[str, ...] = ()) -> Decimal:
    total = ZERO
    for row in rows:
        if not matches(row["code"], include, exclude):
            continue
        value = net_credit(row)
        if value > 0:
            total += value
    return total


def sum_mov(rows: list[dict], field: str, include: tuple[str, ...], exclude: tuple[str, ...] = ()) -> Decimal:
    return sum((_d(row.get(field, 0)) for row in rows if matches(row["code"], include, exclude)), ZERO)


def fmt(value: Decimal) -> str:
    return format(value, "f")


@dataclass(frozen=True)
class Amounts:
    gross: Decimal = ZERO
    amort: Decimal = ZERO

    @property
    def net(self) -> Decimal:
        return self.gross - self.amort


@dataclass
class Line:
    code: str
    label: str
    current: Decimal
    prior: Decimal
    bold: bool = False
    gross: Decimal | None = None
    amort: Decimal | None = None
    kind: str = "detail"

    def as_dict(self) -> dict:
        payload = {
            "code": self.code,
            "label": self.label,
            "current": fmt(self.current),
            "prior": fmt(self.prior),
            "bold": self.bold,
        }
        if self.gross is not None:
            payload["gross"] = fmt(self.gross)
        if self.amort is not None:
            payload["amort"] = fmt(self.amort)
        if self.kind:
            payload["kind"] = self.kind
        return payload


def _asset(rows: list[dict], include: tuple[str, ...], exclude: tuple[str, ...] = (), contra: tuple[str, ...] = (), contra_exclude: tuple[str, ...] = ()) -> Amounts:
    return Amounts(
        gross=sum_net_debit(rows, include, exclude),
        amort=sum_net_credit(rows, contra, contra_exclude) if contra else ZERO,
    )


def _asset_side(rows: list[dict], include: tuple[str, ...], exclude: tuple[str, ...] = (), contra: tuple[str, ...] = (), contra_exclude: tuple[str, ...] = ()) -> Amounts:
    return Amounts(
        gross=sum_debit_side(rows, include, exclude),
        amort=sum_net_credit(rows, contra, contra_exclude) if contra else ZERO,
    )


def _liability(rows: list[dict], include: tuple[str, ...], exclude: tuple[str, ...] = ()) -> Amounts:
    return Amounts(gross=sum_net_credit(rows, include, exclude))


def _liability_side(rows: list[dict], include: tuple[str, ...], exclude: tuple[str, ...] = ()) -> Amounts:
    return Amounts(gross=sum_credit_side(rows, include, exclude))


def _minus_debit(rows: list[dict], include: tuple[str, ...], exclude: tuple[str, ...] = ()) -> Amounts:
    return Amounts(gross=-sum_net_debit(rows, include, exclude))


def _income(rows: list[dict], include: tuple[str, ...], exclude: tuple[str, ...] = ()) -> Decimal:
    return sum_net_credit(rows, include, exclude)


def _expense(rows: list[dict], include: tuple[str, ...], exclude: tuple[str, ...] = ()) -> Decimal:
    return -sum_net_debit(rows, include, exclude)


# « p » = 5e chiffre du compte d’amortissement / dépréciation (Titre IX ch. 7).
_AE_CONTRA = ("2811", "28181", "2911", "29181", "29191")
_AF_CONTRA = ("2812", "2813", "2814", "2912", "2913", "2914", "29193")
_AG_CONTRA = ("2815", "2816", "2915", "2916")
_AH_CONTRA = ("2817", "2818", "2917", "2918", "2919")
_AH_CONTRA_EXC = ("28181", "29181", "29191", "29193")
_AK_CONTRA = ("2831", "2832", "2833", "2837", "2931", "2932", "2933", "2937")
_AL_CONTRA = ("2834", "2835", "2838", "2934", "2935", "2938", "2939")
_CJ_EXC = ("132", "133", "134", "135", "136", "137", "138")


def bilan_amounts(rows: list[dict]) -> dict[str, Amounts]:
    """Soldes nets (et brut / amort. pour l’actif immobilisé) par code officiel."""
    out: dict[str, Amounts] = {}
    out["AE"] = _asset(rows, ("211", "2181", "2191"), contra=_AE_CONTRA)
    out["AF"] = _asset(rows, ("212", "213", "214", "2193"), contra=_AF_CONTRA)
    out["AG"] = _asset(rows, ("215", "216"), contra=_AG_CONTRA)
    out["AH"] = _asset(rows, ("217", "218", "219"), ("2181", "2191", "2193"), _AH_CONTRA, _AH_CONTRA_EXC)
    out["AJ"] = _asset(rows, ("22",), contra=("282", "292"))
    out["AJ_P"] = _asset(rows, ("2281",), contra=("28281", "29281"))
    out["AK"] = _asset(rows, ("231", "232", "233", "237", "2391"), contra=_AK_CONTRA)
    out["AK_P"] = _asset(rows, ("2315", "2325"), contra=("28315", "28325", "29315", "29325"))
    out["AL"] = _asset(
        rows,
        ("234", "235", "238", "2392", "2393", "2394", "2395", "2398"),
        contra=_AL_CONTRA,
    )
    out["AM"] = _asset(rows, ("24",), ("245", "2495"), ("284", "294"), ("2845", "2945"))
    out["AN"] = _asset(rows, ("245", "2495"), contra=("2845", "2945"))
    out["AP"] = _asset(rows, ("251", "252", "25"), ("26",), ("2951", "2952", "295"))
    out["AR"] = _asset(rows, ("26",), contra=("296",))
    out["AS"] = _asset(rows, ("27",), contra=("297",))
    out["BA"] = _asset(rows, ("485", "488"), contra=("498",))
    out["BB"] = _asset(rows, ("31", "32", "33", "34", "35", "36", "37", "38"), contra=("39",))
    out["BH"] = _asset(rows, ("409",), contra=("490",))
    out["BI"] = _asset(rows, ("41",), ("419",), ("491",))
    out["BJ"] = _asset_side(rows, ("185", "42", "43", "44", "45", "46", "47"), ("478", "479"), ("492", "493", "494", "495", "496", "497"))
    out["BQ"] = _asset(rows, ("50",), contra=("590",))
    out["BR"] = _asset(rows, ("51",), contra=("591",))
    out["BS"] = _asset_side(rows, ("52", "53", "54", "55", "57", "581", "582"), contra=("592", "593", "594"))
    out["BU"] = _asset(rows, ("478",))

    out["CA"] = _liability(rows, ("101", "102", "103", "104"))
    out["CB"] = _minus_debit(rows, ("109",))
    out["CD"] = _liability(rows, ("105",))
    out["CE"] = _liability(rows, ("106",))
    out["CF"] = _liability(rows, ("111", "112", "113"))
    out["CG"] = _liability(rows, ("118",))
    out["CH"] = _liability(rows, ("12",))
    out["CJ"] = _liability(rows, ("13",), _CJ_EXC)
    out["CL"] = _liability(rows, ("14",))
    out["CM"] = _liability(rows, ("15",))
    out["DA"] = _liability(rows, ("16", "181", "182", "183", "184"))
    out["DB"] = _liability(rows, ("17",))
    out["DC"] = _liability(rows, ("19",))
    out["DH"] = _liability(rows, ("481", "482", "484", "4998"))
    out["DI"] = _liability(rows, ("419",))
    out["DJ"] = _liability(rows, ("40",), ("409",))
    out["DK"] = _liability_side(rows, ("42", "43", "44"))
    out["DM"] = _liability_side(rows, ("185", "45", "46", "47"), ("478", "479"))
    out["DN"] = _liability(rows, ("499", "599"), ("4998",))
    out["DQ"] = _liability(rows, ("564", "565"))
    out["DR"] = _liability_side(rows, ("52", "53", "561", "566"))
    out["DV"] = _liability(rows, ("479",))

    def add(*codes: str) -> Amounts:
        gross = sum((out[code].gross for code in codes), ZERO)
        amort = sum((out[code].amort for code in codes), ZERO)
        return Amounts(gross, amort)

    out["AD"] = add("AE", "AF", "AG", "AH")
    out["AI"] = add("AJ", "AK", "AL", "AM", "AN", "AP")
    out["AQ"] = add("AR", "AS")
    out["AZ"] = add("AD", "AI", "AQ")
    out["BG"] = add("BH", "BI", "BJ")
    out["BK"] = add("BA", "BB", "BG")
    out["BT"] = add("BQ", "BR", "BS")
    out["BZ"] = add("AZ", "BK", "BT", "BU")
    out["CP"] = add("CA", "CB", "CD", "CE", "CF", "CG", "CH", "CJ", "CL", "CM")
    out["DD"] = add("DA", "DB", "DC")
    out["DF"] = add("CP", "DD")
    out["DP"] = add("DH", "DI", "DJ", "DK", "DM", "DN")
    out["DT"] = add("DQ", "DR")
    out["DZ"] = add("DF", "DP", "DT", "DV")
    return out


_ACTIF_LAYOUT: tuple[tuple[str, str, str], ...] = (
    ("AD", "Immobilisations incorporelles", "heading"),
    ("AE", "Frais de développement et de prospection", "detail"),
    ("AF", "Brevets, licences, logiciels et droits similaires", "detail"),
    ("AG", "Fonds commercial et droit au bail", "detail"),
    ("AH", "Autres immobilisations incorporelles", "detail"),
    ("AI", "Immobilisations corporelles", "heading"),
    ("AJ", "Terrains", "detail"),
    ("AJ_P", "dont immeubles de placement", "dont"),
    ("AK", "Bâtiments", "detail"),
    ("AK_P", "dont immeubles de placement", "dont"),
    ("AL", "Aménagements, agencements et installations", "detail"),
    ("AM", "Matériel, mobilier et actifs biologiques", "detail"),
    ("AN", "Matériel de transport", "detail"),
    ("AP", "Avances et acomptes versés sur immobilisations", "detail"),
    ("AQ", "Immobilisations financières", "heading"),
    ("AR", "Titres de participation", "detail"),
    ("AS", "Autres immobilisations financières", "detail"),
    ("AZ", "Total actif immobilisé", "total"),
    ("BA", "Actif circulant HAO", "detail"),
    ("BB", "Stocks et encours", "detail"),
    ("BG", "Créances et emplois assimilés", "heading"),
    ("BH", "Fournisseurs avances versées", "detail"),
    ("BI", "Clients", "detail"),
    ("BJ", "Autres créances", "detail"),
    ("BK", "Total actif circulant", "total"),
    ("BQ", "Titres de placement", "detail"),
    ("BR", "Valeurs à encaisser", "detail"),
    ("BS", "Banques, établissements financiers et caisse", "detail"),
    ("BT", "Total trésorerie-actif", "total"),
    ("BU", "Écart de conversion-actif", "detail"),
    ("BZ", "Total général actif", "total"),
)

_PASSIF_LAYOUT: tuple[tuple[str, str, str], ...] = (
    ("CA", "Capital", "detail"),
    ("CB", "Apporteurs, capital souscrit non appelé", "detail"),
    ("CD", "Primes liées au capital social", "detail"),
    ("CE", "Écarts de réévaluation", "detail"),
    ("CF", "Réserves indisponibles", "detail"),
    ("CG", "Réserves libres", "detail"),
    ("CH", "Report à nouveau", "detail"),
    ("CJ", "Résultat net de l’exercice", "detail"),
    ("CL", "Subventions d’investissement", "detail"),
    ("CM", "Provisions réglementées et fonds assimilés", "detail"),
    ("CP", "Total capitaux propres", "total"),
    ("DA", "Emprunts et dettes financières", "detail"),
    ("DB", "Dettes de location-acquisition", "detail"),
    ("DC", "Provisions pour risques et charges", "detail"),
    ("DD", "Total dettes financières", "total"),
    ("DF", "Total ressources stables", "total"),
    ("DH", "Dettes circulantes HAO", "detail"),
    ("DI", "Clients, avances reçues", "detail"),
    ("DJ", "Fournisseurs d’exploitation", "detail"),
    ("DK", "Dettes fiscales et sociales", "detail"),
    ("DM", "Autres dettes", "detail"),
    ("DN", "Provisions pour risques à court terme", "detail"),
    ("DP", "Total passif circulant", "total"),
    ("DQ", "Banques, crédits d’escompte", "detail"),
    ("DR", "Banques, crédits de trésorerie", "detail"),
    ("DT", "Total trésorerie-passif", "total"),
    ("DV", "Écart de conversion-passif", "detail"),
    ("DZ", "Total général passif", "total"),
)


def _lines_from_layout(
    current: dict[str, Amounts],
    prior: dict[str, Amounts],
    layout: tuple[tuple[str, str, str], ...],
    *,
    with_gross: bool,
) -> list[Line]:
    lines: list[Line] = []
    for code, label, kind in layout:
        cur = current[code]
        prev = prior.get(code, Amounts())
        bold = kind in {"heading", "total"}
        lines.append(
            Line(
                code=code,
                label=label,
                current=cur.net,
                prior=prev.net,
                bold=bold,
                gross=cur.gross if with_gross else None,
                amort=cur.amort if with_gross else None,
                kind=kind,
            )
        )
    return lines


def build_bilan(current_rows: list[dict], prior_rows: list[dict]) -> tuple[dict, dict[str, Amounts], dict[str, Amounts]]:
    current = bilan_amounts(current_rows)
    prior = bilan_amounts(prior_rows) if prior_rows else {code: Amounts() for code in current}
    actif = _lines_from_layout(current, prior, _ACTIF_LAYOUT, with_gross=True)
    passif = _lines_from_layout(current, prior, _PASSIF_LAYOUT, with_gross=False)
    return (
        {
            "actif": [line.as_dict() for line in actif],
            "passif": [line.as_dict() for line in passif],
            "balanced": current["BZ"].net == current["DZ"].net,
        },
        current,
        prior,
    )


# Produits en +, charges en − (signes du modèle Titre IX ch. 4).
_CR_SPECS: tuple[tuple[str, str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("TA", "Ventes de marchandises", "income", ("701",), ()),
    ("RA", "Achats de marchandises", "expense", ("601",), ()),
    ("RB", "Variation des stocks de marchandises", "expense", ("6031",), ()),
    ("TB", "Ventes de produits fabriqués", "income", ("702", "703", "704"), ()),
    ("TC", "Travaux, services vendus", "income", ("705", "706"), ()),
    ("TD", "Produits accessoires", "income", ("707",), ()),
    ("TE", "Production stockée (ou déstockage)", "income", ("73",), ()),
    ("TF", "Production immobilisée", "income", ("72",), ()),
    ("TG", "Subventions d’exploitation", "income", ("71",), ()),
    ("TH", "Autres produits", "income", ("75",), ()),
    ("TI", "Transferts de charges d’exploitation", "income", ("781",), ()),
    ("RC", "Achats de matières premières et fournitures liées", "expense", ("602",), ()),
    ("RD", "Variation des stocks de matières premières", "expense", ("6032",), ()),
    ("RE", "Autres achats", "expense", ("604", "605", "608"), ()),
    ("RF", "Variation des stocks d’autres approvisionnements", "expense", ("6033",), ()),
    ("RG", "Transports", "expense", ("61",), ()),
    ("RH", "Services extérieurs", "expense", ("62", "63"), ()),
    ("RI", "Impôts et taxes", "expense", ("64",), ()),
    ("RJ", "Autres charges", "expense", ("65",), ()),
    ("RK", "Charges de personnel", "expense", ("66",), ()),
    ("TJ", "Reprises d’amortissements, provisions et dépréciations", "income", ("791", "798", "799"), ()),
    ("RL", "Dotations aux amortissements, provisions et dépréciations", "expense", ("681", "691"), ()),
    ("TK", "Revenus financiers", "income", ("77",), ()),
    ("TL", "Reprises financières", "income", ("797",), ()),
    ("TM", "Transferts de charges financières", "income", ("787",), ()),
    ("RM", "Frais financiers", "expense", ("67",), ()),
    ("RN", "Dotations financières", "expense", ("697",), ()),
    ("TN", "Produits des cessions d’immobilisations", "income", ("82",), ()),
    ("TO", "Autres produits HAO", "income", ("84", "86", "88"), ()),
    ("RO", "Valeurs comptables des cessions d’immobilisations", "expense", ("81",), ()),
    ("RP", "Autres charges HAO", "expense", ("83", "85"), ()),
    ("RQ", "Participation des travailleurs", "expense", ("87",), ()),
    ("RS", "Impôts sur le résultat", "expense", ("89",), ()),
)


def cr_amounts(rows: list[dict]) -> dict[str, Decimal]:
    values: dict[str, Decimal] = {}
    for code, _label, kind, include, exclude in _CR_SPECS:
        values[code] = _income(rows, include, exclude) if kind == "income" else _expense(rows, include, exclude)
    values["XA"] = values["TA"] + values["RA"] + values["RB"]
    values["XB"] = values["TA"] + values["TB"] + values["TC"] + values["TD"]
    values["XC"] = (
        values["XB"]
        + values["RA"]
        + values["RB"]
        + values["TE"]
        + values["TF"]
        + values["TG"]
        + values["TH"]
        + values["TI"]
        + values["RC"]
        + values["RD"]
        + values["RE"]
        + values["RF"]
        + values["RG"]
        + values["RH"]
        + values["RI"]
        + values["RJ"]
    )
    values["XD"] = values["XC"] + values["RK"]
    values["XE"] = values["XD"] + values["TJ"] + values["RL"]
    values["XF"] = values["TK"] + values["TL"] + values["TM"] + values["RM"] + values["RN"]
    values["XG"] = values["XE"] + values["XF"]
    values["XH"] = values["TN"] + values["TO"] + values["RO"] + values["RP"]
    values["XI"] = values["XG"] + values["XH"] + values["RQ"] + values["RS"]
    return values


_CR_LAYOUT: tuple[tuple[str, str, str], ...] = (
    ("TA", "Ventes de marchandises", "detail"),
    ("RA", "Achats de marchandises", "detail"),
    ("RB", "Variation des stocks de marchandises", "detail"),
    ("XA", "Marge commerciale", "sig"),
    ("TB", "Ventes de produits fabriqués", "detail"),
    ("TC", "Travaux, services vendus", "detail"),
    ("TD", "Produits accessoires", "detail"),
    ("XB", "Chiffre d’affaires", "sig"),
    ("TE", "Production stockée (ou déstockage)", "detail"),
    ("TF", "Production immobilisée", "detail"),
    ("TG", "Subventions d’exploitation", "detail"),
    ("TH", "Autres produits", "detail"),
    ("TI", "Transferts de charges d’exploitation", "detail"),
    ("RC", "Achats de matières premières et fournitures liées", "detail"),
    ("RD", "Variation des stocks de matières premières", "detail"),
    ("RE", "Autres achats", "detail"),
    ("RF", "Variation des stocks d’autres approvisionnements", "detail"),
    ("RG", "Transports", "detail"),
    ("RH", "Services extérieurs", "detail"),
    ("RI", "Impôts et taxes", "detail"),
    ("RJ", "Autres charges", "detail"),
    ("XC", "Valeur ajoutée", "sig"),
    ("RK", "Charges de personnel", "detail"),
    ("XD", "Excédent brut d’exploitation", "sig"),
    ("TJ", "Reprises d’amortissements, provisions et dépréciations", "detail"),
    ("RL", "Dotations aux amortissements, provisions et dépréciations", "detail"),
    ("XE", "Résultat d’exploitation", "sig"),
    ("TK", "Revenus financiers", "detail"),
    ("TL", "Reprises financières", "detail"),
    ("TM", "Transferts de charges financières", "detail"),
    ("RM", "Frais financiers", "detail"),
    ("RN", "Dotations financières", "detail"),
    ("XF", "Résultat financier", "sig"),
    ("XG", "Résultat des activités ordinaires", "sig"),
    ("TN", "Produits des cessions d’immobilisations", "detail"),
    ("TO", "Autres produits HAO", "detail"),
    ("RO", "Valeurs comptables des cessions d’immobilisations", "detail"),
    ("RP", "Autres charges HAO", "detail"),
    ("XH", "Résultat hors activités ordinaires", "sig"),
    ("RQ", "Participation des travailleurs", "detail"),
    ("RS", "Impôts sur le résultat", "detail"),
    ("XI", "Résultat net", "sig"),
)


def build_compte_resultat(current_rows: list[dict], prior_rows: list[dict]) -> tuple[dict, dict[str, Decimal], dict[str, Decimal]]:
    current = cr_amounts(current_rows)
    prior = cr_amounts(prior_rows) if prior_rows else {code: ZERO for code in current}
    lines: list[Line] = []
    for code, label, kind in _CR_LAYOUT:
        display = label
        if code == "XD" and current[code] < 0:
            display = "Insuffisance brute d’exploitation"
        lines.append(
            Line(
                code=code,
                label=display,
                current=current[code],
                prior=prior[code],
                bold=kind == "sig",
                kind=kind,
            )
        )
    return (
        {"lines": [line.as_dict() for line in lines], "net": fmt(current["XI"])},
        current,
        prior,
    )


def _delta(current: dict[str, Amounts], prior: dict[str, Amounts], code: str) -> Decimal:
    return current[code].net - prior.get(code, Amounts()).net


def _metrics(amounts: dict[str, Amounts]) -> dict[str, Decimal]:
    """Indicateurs hors liasse (Titre IX ch. 3). Le bilan publié n’est pas retraité."""
    bfe_passif = (
        amounts["DI"].net
        + amounts["DJ"].net
        + amounts["DK"].net
        + amounts["DM"].net
        + amounts["DN"].net
    )
    return {
        "fr": amounts["DF"].net - amounts["AZ"].net,
        "fr_bas": (amounts["BK"].net + amounts["BT"].net) - (amounts["DP"].net + amounts["DT"].net),
        "bfg": amounts["BK"].net - amounts["DP"].net,
        "bfe": (amounts["BB"].net + amounts["BG"].net) - bfe_passif,
        "bf_hao": amounts["BA"].net - amounts["DH"].net,
        "tn": amounts["BT"].net - amounts["DT"].net,
        "conversion": amounts["BU"].net - amounts["DV"].net,
    }


def financial_analysis(current: dict[str, Amounts], prior: dict[str, Amounts]) -> dict[str, dict[str, str]]:
    now = _metrics(current)
    prev = _metrics(prior)
    return {key: {"current": fmt(now[key]), "prior": fmt(prev[key])} for key in now}


def operating_receivables(rows: list[dict], amounts: dict[str, Amounts]) -> Decimal:
    """Δ créances d’exploitation : BG hors 414, plus intérêts courus sur immos financières (276)."""
    return amounts["BG"].net - sum_net_debit(rows, ("414",)) + sum_net_debit(rows, ("276",))


def operating_payables(rows: list[dict], amounts: dict[str, Amounts]) -> Decimal:
    """Passif circulant hors dettes d’immos (481, 482, 404), plus intérêts courus 166/176."""
    return (
        amounts["DP"].net
        - sum_net_credit(rows, ("481", "482", "404"))
        + sum_net_credit(rows, ("166", "176"))
    )


def cafg(cr: dict[str, Decimal], rows: list[dict]) -> Decimal:
    """CAFG = CAFE + revenus financiers + transferts financiers + HAO − frais − participation − impôt.

    CAFE = EBE (XD) + 654 − 754. Les reprises/dotations financières (TL, RN) restent hors CAFG.
    """
    cafe = cr["XD"] + sum_net_debit(rows, ("654",)) - sum_net_credit(rows, ("754",))
    return cafe + cr["TK"] + cr["TM"] + cr["TN"] + cr["TO"] + cr["RQ"] + cr["RS"] + cr["RM"]


def build_tft(
    current_rows: list[dict],
    prior_rows: list[dict],
    cr_n: dict[str, Decimal],
    cr_p: dict[str, Decimal],
    bilan_n: dict[str, Amounts],
    bilan_p: dict[str, Amounts],
    investment: dict[str, Decimal] | None = None,
    dividends: Decimal | None = None,
) -> dict:
    za = bilan_p["BT"].net - bilan_p["DT"].net
    fa = cafg(cr_n, current_rows)
    fb = -_delta(bilan_n, bilan_p, "BA")
    fc = -_delta(bilan_n, bilan_p, "BB")
    fd = -(operating_receivables(current_rows, bilan_n) - operating_receivables(prior_rows, bilan_p))
    fe = operating_payables(current_rows, bilan_n) - operating_payables(prior_rows, bilan_p)
    zb = fa + fb + fc + fd + fe

    delta_ff = sum_net_credit(current_rows, ("4811", "4041", "4046")) - sum_net_credit(
        prior_rows, ("4811", "4041", "4046")
    )
    delta_fg = sum_net_credit(
        current_rows, ("4812", "481", "482", "4042", "4047", "404"), ("4811", "4813", "4041", "4046")
    ) - sum_net_credit(
        prior_rows, ("4812", "481", "482", "4042", "4047", "404"), ("4811", "4813", "4041", "4046")
    )
    delta_fh = sum_net_credit(current_rows, ("4813",)) - sum_net_credit(prior_rows, ("4813",))
    if investment:
        ff = investment.get("ff", ZERO) + delta_ff
        fg = investment.get("fg", ZERO) + delta_fg
        fh = investment.get("fh", ZERO) + delta_fh
    else:
        ff = -sum_mov(current_rows, "mov_debit", ("21",)) + delta_ff
        fg = -sum_mov(current_rows, "mov_debit", ("22", "23", "24", "25")) + delta_fg
        fh = -sum_mov(current_rows, "mov_debit", ("26", "27")) + delta_fh
    fi = sum_mov(current_rows, "mov_credit", ("821", "822", "82"), ("826",)) - (
        sum_debit_side(current_rows, ("485",), ("4856",)) - sum_debit_side(prior_rows, ("485",), ("4856",))
    )
    fj = sum_mov(current_rows, "mov_credit", ("826",))
    zc = ff + fg + fh + fi + fj

    fk = sum_mov(current_rows, "mov_credit", ("101", "102", "103"))
    fl = sum_mov(current_rows, "mov_credit", ("14",))
    fm = -sum_mov(current_rows, "mov_debit", ("104",))
    fn = dividends if dividends is not None else ZERO
    zd = fk + fl + fm + fn
    fo = sum_mov(current_rows, "mov_credit", ("16",))
    fp = sum_mov(current_rows, "mov_credit", ("17", "181", "182", "183", "184"))
    fq = -(
        sum_mov(current_rows, "mov_debit", ("16",))
        + sum_mov(current_rows, "mov_debit", ("17", "181", "182", "183", "184"))
    )
    ze = fo + fp + fq
    zf = zd + ze
    zg = zb + zc + zf
    zh_formula = zg + za
    zh_control = bilan_n["BT"].net - bilan_n["DT"].net

    fa_p = cafg(cr_p, prior_rows) if prior_rows else ZERO

    def pair(n: Decimal, p: Decimal, code: str, label: str, bold: bool = False) -> Line:
        return Line(code=code, label=label, current=n, prior=p, bold=bold, kind="total" if bold else "detail")

    lines = [
        pair(za, ZERO, "ZA", "Trésorerie nette au 1er janvier", True),
        pair(fa, fa_p, "FA", "Capacité d’autofinancement globale (CAFG)"),
        pair(fb, ZERO, "FB", "Variation de l’actif circulant HAO"),
        pair(fc, ZERO, "FC", "Variation des stocks"),
        pair(fd, ZERO, "FD", "Variation des créances d’exploitation"),
        pair(fe, ZERO, "FE", "Variation du passif circulant d’exploitation"),
        pair(zb, ZERO, "ZB", "Flux de trésorerie des activités opérationnelles", True),
        pair(ff, ZERO, "FF", "Décaissements sur immobilisations incorporelles"),
        pair(fg, ZERO, "FG", "Décaissements sur immobilisations corporelles"),
        pair(fh, ZERO, "FH", "Décaissements sur immobilisations financières"),
        pair(fi, ZERO, "FI", "Encaissements sur cessions d’immobilisations"),
        pair(fj, ZERO, "FJ", "Encaissements sur cessions d’immobilisations financières"),
        pair(zc, ZERO, "ZC", "Flux de trésorerie des opérations d’investissement", True),
        pair(fk, ZERO, "FK", "Augmentations de capital"),
        pair(fl, ZERO, "FL", "Subventions d’investissement reçues"),
        pair(fm, ZERO, "FM", "Prélèvements sur le capital"),
        pair(fn, ZERO, "FN", "Dividendes versés"),
        pair(zd, ZERO, "ZD", "Flux de trésorerie provenant des capitaux propres", True),
        pair(fo, ZERO, "FO", "Emprunts"),
        pair(fp, ZERO, "FP", "Autres dettes financières"),
        pair(fq, ZERO, "FQ", "Remboursements d’emprunts et autres dettes financières"),
        pair(ze, ZERO, "ZE", "Flux de trésorerie provenant des capitaux étrangers", True),
        pair(zf, ZERO, "ZF", "Flux de trésorerie provenant du financement", True),
        pair(zg, ZERO, "ZG", "Variation de la trésorerie nette", True),
        pair(zh_formula, za, "ZH", "Trésorerie nette au 31 décembre", True),
    ]
    if zh_formula != zh_control:
        lines.append(
            pair(
                zh_control - zh_formula,
                ZERO,
                "",
                "Écart de contrôle (approximation sans journal d’immobilisations)",
            )
        )
    return {"lines": [line.as_dict() for line in lines]}
