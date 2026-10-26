/** 17 États membres OHADA et devise légale de tenue. À garder aligné avec apps/tenancy/ohada.py. */

export type OhadaCountry = {
  code: string;
  label: string;
  currency: string;
};

export const OHADA_COUNTRIES: OhadaCountry[] = [
  { code: "BJ", label: "Bénin", currency: "XOF" },
  { code: "BF", label: "Burkina Faso", currency: "XOF" },
  { code: "CM", label: "Cameroun", currency: "XAF" },
  { code: "CF", label: "Centrafrique", currency: "XAF" },
  { code: "TD", label: "Tchad", currency: "XAF" },
  { code: "KM", label: "Comores", currency: "KMF" },
  { code: "CG", label: "Congo", currency: "XAF" },
  { code: "CD", label: "RDC", currency: "CDF" },
  { code: "CI", label: "Côte d’Ivoire", currency: "XOF" },
  { code: "GQ", label: "Guinée équatoriale", currency: "XAF" },
  { code: "GA", label: "Gabon", currency: "XAF" },
  { code: "GN", label: "Guinée", currency: "GNF" },
  { code: "GW", label: "Guinée-Bissau", currency: "XOF" },
  { code: "ML", label: "Mali", currency: "XOF" },
  { code: "NE", label: "Niger", currency: "XOF" },
  { code: "SN", label: "Sénégal", currency: "XOF" },
  { code: "TG", label: "Togo", currency: "XOF" },
];

export const ZERO_DECIMAL_CURRENCIES = new Set(["XOF", "XAF", "KMF", "GNF"]);

export const FX_CURRENCY_CHOICES = [
  "EUR",
  "USD",
  "GBP",
  "CHF",
  "MAD",
  "XOF",
  "XAF",
  "KMF",
  "CDF",
  "GNF",
] as const;

export function currencyForCountry(code: string): string {
  return OHADA_COUNTRIES.find((item) => item.code === code)?.currency ?? "XOF";
}

export function currencyDecimals(code: string): number {
  return ZERO_DECIMAL_CURRENCIES.has((code || "").toUpperCase()) ? 0 : 2;
}
