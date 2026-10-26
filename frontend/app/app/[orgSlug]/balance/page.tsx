"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { useTenant } from "@/components/tenant-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError, downloadApi } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import type { BalanceRow, LedgerPeriod } from "@/lib/types";

export default function BalancePage() {
  const { orgSlug, companyId, activeCompany } = useTenant();
  const currency = activeCompany?.currency_code ?? "XOF";
  const [periodId, setPeriodId] = useState("");
  const [pdfBusy, setPdfBusy] = useState(false);
  const [pdfError, setPdfError] = useState("");
  const periods = useQuery({
    queryKey: ["periods", orgSlug, companyId],
    queryFn: () => api<LedgerPeriod[]>("/api/ledger/periods", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const balance = useQuery({
    queryKey: ["balance", orgSlug, companyId, periodId],
    queryFn: () =>
      api<BalanceRow[]>(
        `/api/ledger/balance${periodId ? `?period_id=${periodId}` : ""}`,
        { orgSlug, companyId },
      ),
    enabled: Boolean(orgSlug && companyId),
  });

  const totals = (balance.data ?? []).reduce(
    (acc, row) => ({
      closeDebit: acc.closeDebit + Number(row.close_debit),
      closeCredit: acc.closeCredit + Number(row.close_credit),
    }),
    { closeDebit: 0, closeCredit: 0 },
  );

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl">Balance générale</h1>
          <p className="mt-1 text-muted-foreground">
            Soldes d’ouverture, mouvements et soldes — snapshots de période, pas un SUM de tout l’historique.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="h-10 rounded-md border border-input bg-background px-2 text-sm"
            value={periodId}
            onChange={(event) => setPeriodId(event.target.value)}
          >
            <option value="">Période courante</option>
            {(periods.data ?? []).map((period) => (
              <option key={period.id} value={period.id}>
                {period.year}-{String(period.month).padStart(2, "0")}
              </option>
            ))}
          </select>
          <Button
            type="button"
            variant="outline"
            disabled={pdfBusy}
            onClick={async () => {
              setPdfError("");
              setPdfBusy(true);
              const query = new URLSearchParams({ kind: "balance" });
              if (periodId) query.set("period_id", periodId);
              try {
                await downloadApi(`/api/ledger/books/pdf?${query}`, {
                  orgSlug,
                  companyId,
                  filename: "balance.pdf",
                });
              } catch (error) {
                setPdfError(error instanceof ApiError ? error.message : "Téléchargement PDF impossible.");
              } finally {
                setPdfBusy(false);
              }
            }}
          >
            {pdfBusy ? "PDF…" : "PDF balance"}
          </Button>
        </div>
      </div>
      {pdfError && <p className="text-sm text-destructive">{pdfError}</p>}
      <Card>
        <CardHeader>
          <CardTitle>{activeCompany?.name ?? "Société"}</CardTitle>
          <CardDescription>
            Clôture débit {formatMoney(totals.closeDebit, currency)} · crédit{" "}
            {formatMoney(totals.closeCredit, currency)}
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-muted-foreground">
              <tr>
                <th className="py-2 pr-3 font-medium">Compte</th>
                <th className="py-2 pr-3 font-medium">Intitulé</th>
                <th className="py-2 pr-3 font-medium text-right">Ouv. D</th>
                <th className="py-2 pr-3 font-medium text-right">Ouv. C</th>
                <th className="py-2 pr-3 font-medium text-right">Mvt D</th>
                <th className="py-2 pr-3 font-medium text-right">Mvt C</th>
                <th className="py-2 pr-3 font-medium text-right">Solde D</th>
                <th className="py-2 font-medium text-right">Solde C</th>
              </tr>
            </thead>
            <tbody>
              {(balance.data ?? []).map((row) => (
                <tr key={row.account_id} className="border-b border-border/70">
                  <td className="py-1.5 pr-3 font-mono">{row.code}</td>
                  <td className="py-1.5 pr-3">{row.label}</td>
                  <td className="py-1.5 pr-3 text-right font-mono">{formatMoney(row.open_debit, currency)}</td>
                  <td className="py-1.5 pr-3 text-right font-mono">{formatMoney(row.open_credit, currency)}</td>
                  <td className="py-1.5 pr-3 text-right font-mono">{formatMoney(row.mov_debit, currency)}</td>
                  <td className="py-1.5 pr-3 text-right font-mono">{formatMoney(row.mov_credit, currency)}</td>
                  <td className="py-1.5 pr-3 text-right font-mono">{formatMoney(row.close_debit, currency)}</td>
                  <td className="py-1.5 text-right font-mono">{formatMoney(row.close_credit, currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {balance.isSuccess && balance.data.length === 0 && (
            <p className="py-6 text-sm text-muted-foreground">Aucun mouvement sur cette période.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
