"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { useTenant } from "@/components/tenant-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError, downloadApi } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import type { LegalBooks, LedgerPeriod } from "@/lib/types";

const SELECT_CLASS = "h-10 rounded-md border border-input bg-background px-3 text-sm";

const PDF_KINDS = [
  ["all", "Tous les livres"],
  ["journal", "Journal"],
  ["ledger", "Grand-livre"],
  ["balance", "Balance"],
  ["inventory", "Inventaire"],
] as const;

export default function LegalBooksPage() {
  const { orgSlug, companyId, activeCompany } = useTenant();
  const currency = activeCompany?.currency_code ?? "XOF";
  const [periodId, setPeriodId] = useState("");
  const [pdfKind, setPdfKind] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState("");

  const periods = useQuery({
    queryKey: ["periods", orgSlug, companyId],
    queryFn: () => api<LedgerPeriod[]>("/api/ledger/periods", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const books = useQuery({
    queryKey: ["legal-books", orgSlug, companyId],
    queryFn: () => api<LegalBooks>("/api/ledger/books", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const data = books.data;
  const period = (periods.data ?? []).find((item) => item.id === periodId) ?? (periods.data ?? [])[0];

  async function downloadPdf(kind: (typeof PDF_KINDS)[number][0]) {
    setPdfError("");
    setPdfKind(kind);
    const query = new URLSearchParams({ kind });
    if (periodId) query.set("period_id", periodId);
    const names: Record<string, string> = {
      all: "livres-legaux",
      journal: "livre-journal",
      ledger: "grand-livre",
      balance: "balance",
      inventory: "livre-inventaire",
    };
    const stamp = period ? `${period.year}-${String(period.month).padStart(2, "0")}` : "periode";
    try {
      await downloadApi(`/api/ledger/books/pdf?${query}`, {
        orgSlug,
        companyId,
        filename: `${names[kind]}-${stamp}.pdf`,
      });
    } catch (error) {
      setPdfError(error instanceof ApiError ? error.message : "Téléchargement PDF impossible.");
    } finally {
      setPdfKind(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl">Livres légaux</h1>
          <p className="mt-1 max-w-2xl text-muted-foreground">
            Livre-journal, grand-livre, balance et livre d’inventaire, numérotés et datés (art. 19,
            22, 66–67). Conservation des pièces : 10 ans (art. 24).
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select className={SELECT_CLASS} value={periodId} onChange={(event) => setPeriodId(event.target.value)}>
            <option value="">Période courante</option>
            {(periods.data ?? []).map((item) => (
              <option key={item.id} value={item.id}>
                {item.year}-{String(item.month).padStart(2, "0")}
              </option>
            ))}
          </select>
          {PDF_KINDS.map(([kind, label]) => (
            <Button
              key={kind}
              type="button"
              variant={kind === "all" ? "default" : "outline"}
              disabled={pdfKind !== null}
              onClick={() => downloadPdf(kind)}
            >
              {pdfKind === kind ? "PDF…" : `PDF ${label}`}
            </Button>
          ))}
        </div>
      </div>
      {pdfError && <p className="text-sm text-destructive">{pdfError}</p>}
      <Card>
        <CardHeader>
          <CardTitle>Livre-journal</CardTitle>
          <CardDescription>
            {data ? `Établi le ${data.dated} · ${data.journal.length} écriture(s) validée(s)` : "Chargement…"}
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-muted-foreground">
              <tr>
                <th className="py-2 pr-3 font-medium">N°</th>
                <th className="py-2 pr-3 font-medium">Date</th>
                <th className="py-2 pr-3 font-medium">Journal</th>
                <th className="py-2 pr-3 font-medium">Libellé</th>
                <th className="py-2 font-medium text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {(data?.journal ?? []).map((row) => (
                <tr key={row.id} className="border-b border-border/70">
                  <td className="py-1.5 pr-3">
                    <Link href={`/app/${orgSlug}/journal/${row.id}`} className="font-mono hover:underline">
                      {row.number_display}
                    </Link>
                  </td>
                  <td className="py-1.5 pr-3">{row.accounting_date}</td>
                  <td className="py-1.5 pr-3">{row.journal_code}</td>
                  <td className="py-1.5 pr-3">{row.description}</td>
                  <td className="py-1.5 text-right font-mono">{formatMoney(row.total, currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Livre d’inventaire</CardTitle>
          <CardDescription>
            Transcription de l’inventaire physique et des soldes de clôture. Bilan / CR / TFT : page
            États financiers.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {data?.inventory_summary || "Aucun inventaire arrêté. Ouvrez-en un dans Clôture."}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
