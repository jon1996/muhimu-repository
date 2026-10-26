"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { useTenant } from "@/components/tenant-context";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError, downloadApi } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import type { JournalEntry } from "@/lib/types";

export default function JournalPage() {
  const { orgSlug, companyId, activeCompany } = useTenant();
  const [pdfBusy, setPdfBusy] = useState(false);
  const [pdfError, setPdfError] = useState("");
  const entries = useQuery({
    queryKey: ["entries", orgSlug, companyId],
    queryFn: () => api<JournalEntry[]>("/api/ledger/entries", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });

  async function downloadPdf() {
    setPdfError("");
    setPdfBusy(true);
    try {
      await downloadApi("/api/ledger/books/pdf?kind=journal", {
        orgSlug,
        companyId,
        filename: "livre-journal.pdf",
      });
    } catch (error) {
      setPdfError(error instanceof ApiError ? error.message : "Téléchargement PDF impossible.");
    } finally {
      setPdfBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl">Livre-journal</h1>
          <p className="mt-1 text-muted-foreground">
            Enregistrement chronologique — {activeCompany?.name ?? "société"}
          </p>
        </div>
        <div className="flex gap-2">
          <Button type="button" variant="outline" disabled={pdfBusy} onClick={downloadPdf}>
            {pdfBusy ? "PDF…" : "PDF journal"}
          </Button>
          <Link href={`/app/${orgSlug}/journal/nouveau`} className={buttonVariants()}>
            Nouvelle pièce
          </Link>
        </div>
      </div>
      {pdfError && <p className="text-sm text-destructive">{pdfError}</p>}
      <Card>
        <CardHeader>
          <CardTitle>Pièces</CardTitle>
          <CardDescription>Les écritures validées sont immuables (contrepassation uniquement).</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-muted-foreground">
              <tr>
                <th className="py-2 pr-4 font-medium">N°</th>
                <th className="py-2 pr-4 font-medium">Date</th>
                <th className="py-2 pr-4 font-medium">Journal</th>
                <th className="py-2 pr-4 font-medium">Libellé</th>
                <th className="py-2 pr-4 font-medium text-right">Débit</th>
                <th className="py-2 font-medium">Statut</th>
              </tr>
            </thead>
            <tbody>
              {(entries.data ?? []).map((entry) => (
                <tr key={entry.id} className="border-b border-border/70">
                  <td className="py-2 pr-4">
                    <Link href={`/app/${orgSlug}/journal/${entry.id}`} className="font-medium hover:underline">
                      {entry.number_display || "Brouillon"}
                    </Link>
                  </td>
                  <td className="py-2 pr-4 whitespace-nowrap">{entry.accounting_date}</td>
                  <td className="py-2 pr-4">{entry.journal_code}</td>
                  <td className="py-2 pr-4">{entry.description}</td>
                  <td className="py-2 pr-4 text-right font-mono">
                    {formatMoney(entry.total_debit, activeCompany?.currency_code)}
                  </td>
                  <td className="py-2">
                    <Badge>{entry.status === "posted" ? "Validée" : "Brouillon"}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {entries.isSuccess && entries.data.length === 0 && (
            <p className="py-6 text-sm text-muted-foreground">Aucune pièce. Saisissez une première écriture.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
