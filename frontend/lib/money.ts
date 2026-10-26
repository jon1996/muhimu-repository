import { currencyDecimals } from "@/lib/ohada";

export function formatMoney(value: string | number, currency = "XOF"): string {
  const amount = typeof value === "number" ? value : Number(value);
  const digits = currencyDecimals(currency);
  return new Intl.NumberFormat("fr-FR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(Number.isFinite(amount) ? amount : 0);
}
