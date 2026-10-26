from decimal import Decimal, ROUND_HALF_UP

from apps.tenancy.ohada import ZERO_DECIMAL_CURRENCIES


def currency_decimals(currency_code: str) -> int:
    return 0 if currency_code.upper() in ZERO_DECIMAL_CURRENCIES else 2


def quantize_amount(amount: Decimal, currency_code: str) -> Decimal:
    decimals = currency_decimals(currency_code)
    quant = Decimal("1") if decimals == 0 else Decimal("0.01")
    return amount.quantize(quant, rounding=ROUND_HALF_UP)


def parse_amount(raw: str | Decimal | int | float, currency_code: str) -> Decimal:
    if raw is None or raw == "":
        value = Decimal("0")
    else:
        value = Decimal(str(raw))
    return quantize_amount(value, currency_code)


def parse_rate(raw: str | Decimal | int | float | None) -> Decimal:
    """Cours : unités de devise de tenue pour 1 unité de devise étrangère."""
    if raw is None or raw == "":
        raise ValueError("Cours requis.")
    value = Decimal(str(raw).replace(",", ".").strip())
    if value <= 0:
        raise ValueError("Cours invalide.")
    return value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def format_amount_fr(raw: str | Decimal | int | float | None, currency_code: str) -> str:
    """Montant SYSCOHADA : espaces milliers, virgule décimale, 0 décimale XOF/XAF/KMF/GNF."""
    value = parse_amount("0" if raw is None or raw == "" else raw, currency_code)
    decimals = currency_decimals(currency_code)
    negative = value < 0
    absolute = abs(value)
    if decimals == 0:
        body = f"{int(absolute):,}".replace(",", " ")
    else:
        whole, frac = f"{absolute:.{decimals}f}".split(".")
        body = f"{int(whole):,}".replace(",", " ") + "," + frac
    return f"-{body}" if negative else body
