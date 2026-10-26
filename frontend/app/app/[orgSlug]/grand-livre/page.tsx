"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { useTenant } from "@/components/tenant-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError, downloadApi } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import type { GeneralLedger, LedgerAccount, LedgerPeriod } from "@/lib/types";

export default function GeneralLedgerPage() {
  const { orgSlug, companyId, activeCompany } = useTenant();
  const currency = activeCompany?.currency_code ?? "XOF";
  const [accountId, setAccountId] = useState("");
  const [periodId, setPeriodId] = useState("");
  const [pdfBusy, setPdfBusy] = useState(false);
  const [pdfError, setPdfError] = useState("");

  const accounts = useQuery({
    queryKey: ["accounts-postable", orgSlug, companyId],
    queryFn: () => api<LedgerAccount[]>("/api/ledger/accounts?postable=true", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const periods = useQuery({
    queryKey: ["periods", orgSlug, companyId],
    queryFn: () => api<LedgerPeriod[]>("/api/ledger/periods", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const ledger = useQuery({
    queryKey: ["general-ledger", orgSlug, companyId, accountId, periodId],
    queryFn: () =>
      api<GeneralLedger>(
        `/api/ledger/general-ledger/${accountId}${periodId ? `?period_id=${periodId}` : ""}`,
        { orgSlug, companyId },
      ),
    enabled: Boolean(orgSlug && companyId && accountId),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl">Grand-livre</h1>
        <p className="mt-1 text-muted-foreground">Mouvements d’un compte sur la période, avec solde courant.</p>
      </div>
      <div className="flex flex-wrap gap-3">
        <select
          className="h-10 min-w-[280px] rounded-md border border-input bg-background px-2 text-sm"
          value={accountId}
          onChange={(event) => setAccountId(event.target.value)}
        >
          <option value="">Choisir un compte</option>
          {(accounts.data ?? []).map((account) => (
            <option key={account.id} value={account.id}>
              {account.code} {account.label}
            </option>
          ))}
        </select>
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
            const query = new URLSearchParams({ kind: "ledger" });
            if (periodId) query.set("period_id", periodId);
            try {
              await downloadApi(`/api/ledger/books/pdf?${query}`, {
                orgSlug,
                companyId,
                filename: "grand-livre.pdf",
              });
            } catch (error) {
              setPdfError(error instanceof ApiError ? error.message : "Téléchargement PDF impossible.");
            } finally {
              setPdfBusy(false);
            }
          }}
        >
          {pdfBusy ? "PDF…" : "PDF grand-livre"}
        </Button>
      </div>
      {pdfError && <p className="text-sm text-destructive">{pdfError}</p>}
      {ledger.data && (
        <Card>
          <CardHeader>
            <CardTitle>
              {ledger.data.code} {ledger.data.label}
            </CardTitle>
            <CardDescription>
              Solde de clôture {formatMoney(ledger.data.close_balance, currency)} (débit − crédit)
            </CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-muted-foreground">
                <tr>
                  <th className="py-2 pr-3 font-medium">Date</th>
                  <th className="py-2 pr-3 font-medium">N°</th>
                  <th className="py-2 pr-3 font-medium">Libellé</th>
                  <th className="py-2 pr-3 font-medium text-right">Débit</th>
                  <th className="py-2 pr-3 font-medium text-right">Crédit</th>
                  <th className="py-2 font-medium text-right">Solde</th>
                </tr>
              </thead>
              <tbody>
                {ledger.data.lines.map((line) => (
                  <tr key={line.id} className="border-b border-border/70">
                    <td className="py-1.5 pr-3 whitespace-nowrap">{line.accounting_date}</td>
                    <td className="py-1.5 pr-3">{line.number_display}</td>
                    <td className="py-1.5 pr-3">{line.label}</td>
                    <td className="py-1.5 pr-3 text-right font-mono">{formatMoney(line.debit, currency)}</td>
                    <td className="py-1.5 pr-3 text-right font-mono">{formatMoney(line.credit, currency)}</td>
                    <td className="py-1.5 text-right font-mono">{formatMoney(line.balance, currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {ledger.data.lines.length === 0 && (
              <p className="py-6 text-sm text-muted-foreground">Aucun mouvement sur cette période.</p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
