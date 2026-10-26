"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { useTenant } from "@/components/tenant-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { localTodayIso } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import type { AssetSuggest, DepreciateResult, FixedAsset, LedgerAccount, LedgerPeriod } from "@/lib/types";

const SELECT_CLASS = "h-10 w-full rounded-md border border-input bg-background px-3 text-sm";
const KIND_LABEL: Record<string, string> = {
  standalone: "Bien unique",
  structure: "Structure",
  component: "Composant",
};
const STATUS_LABEL: Record<string, string> = {
  in_service: "En service",
  disposed: "Sorti",
};

export default function AssetsPage() {
  const { orgSlug, companyId, activeCompany, membership } = useTenant();
  const canWrite = ["owner", "admin", "accountant"].includes(membership?.role ?? "");
  const currency = activeCompany?.currency_code ?? "XOF";
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const [periodId, setPeriodId] = useState("");
  const [label, setLabel] = useState("");
  const [kind, setKind] = useState("standalone");
  const [parentId, setParentId] = useState("");
  const [cost, setCost] = useState("");
  const [residual, setResidual] = useState("0");
  const [life, setLife] = useState("60");
  const [acquiredOn, setAcquiredOn] = useState("");
  const [inServiceOn, setInServiceOn] = useState("");
  const [accountId, setAccountId] = useState("");
  const [amortId, setAmortId] = useState("");
  const [expenseId, setExpenseId] = useState("");
  const [notes, setNotes] = useState("");
  const [dapMessage, setDapMessage] = useState("");

  useEffect(() => {
    const today = localTodayIso();
    setAcquiredOn((current) => current || today);
    setInServiceOn((current) => current || today);
  }, []);

  const periods = useQuery({
    queryKey: ["periods", orgSlug, companyId],
    queryFn: () => api<LedgerPeriod[]>("/api/ledger/periods", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const accounts = useQuery({
    queryKey: ["accounts", orgSlug, companyId],
    queryFn: () => api<LedgerAccount[]>("/api/ledger/accounts?postable=true", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const assets = useQuery({
    queryKey: ["assets", orgSlug, companyId, periodId],
    queryFn: () =>
      api<FixedAsset[]>(`/api/ledger/assets${periodId ? `?period_id=${periodId}` : ""}`, {
        orgSlug,
        companyId,
      }),
    enabled: Boolean(orgSlug && companyId),
  });

  const class2 = useMemo(
    () =>
      (accounts.data ?? []).filter(
        (account) =>
          account.account_class === "2" &&
          !account.code.startsWith("28") &&
          !account.code.startsWith("29"),
      ),
    [accounts.data],
  );
  const class28 = useMemo(
    () => (accounts.data ?? []).filter((account) => account.code.startsWith("28")),
    [accounts.data],
  );
  const class68 = useMemo(
    () =>
      (accounts.data ?? []).filter(
        (account) =>
          account.code.startsWith("681") ||
          account.code.startsWith("691") ||
          account.code.startsWith("697"),
      ),
    [accounts.data],
  );
  const parents = (assets.data ?? []).filter((asset) => asset.kind !== "component");
  const needsLife = Number(life) > 0;

  useEffect(() => {
    if (!periodId && periods.data?.length) {
      const open = periods.data.find((period) => period.status === "open");
      setPeriodId((open ?? periods.data[periods.data.length - 1]).id);
    }
  }, [periodId, periods.data]);

  useEffect(() => {
    if (!accountId || !orgSlug || !companyId) return;
    let cancelled = false;
    api<AssetSuggest>(`/api/ledger/assets/suggest?account_id=${accountId}`, { orgSlug, companyId })
      .then((suggest) => {
        if (cancelled) return;
        if (suggest.amort_account_id) setAmortId(suggest.amort_account_id);
        if (suggest.expense_account_id) setExpenseId(suggest.expense_account_id);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [accountId, orgSlug, companyId]);

  const onError = (err: unknown) => {
    setError(err instanceof ApiError ? err.message : "Action impossible.");
  };

  const createAsset = useMutation({
    mutationFn: () =>
      api<FixedAsset>("/api/ledger/assets", {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({
          label,
          kind,
          parent_id: kind === "component" ? parentId || null : null,
          acquired_on: acquiredOn,
          in_service_on: inServiceOn,
          cost,
          residual_value: residual,
          useful_life_months: Number(life),
          asset_account_id: accountId,
          amort_account_id: needsLife ? amortId || null : null,
          expense_account_id: needsLife ? expenseId || null : null,
          notes,
        }),
      }),
    onSuccess: () => {
      setError("");
      setLabel("");
      setCost("");
      setNotes("");
      queryClient.invalidateQueries({ queryKey: ["assets"] });
    },
    onError,
  });

  const depreciate = useMutation({
    mutationFn: () =>
      api<DepreciateResult>("/api/ledger/assets/depreciate", {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({ period_id: periodId }),
      }),
    onSuccess: (result) => {
      setError("");
      setDapMessage(
        result.posted
          ? `Dotation ${result.number_display} — ${result.count} bien(s), ${formatMoney(result.total, currency)} ${currency}.`
          : "Aucune dotation à passer pour cette période.",
      );
      queryClient.invalidateQueries({ queryKey: ["assets"] });
      queryClient.invalidateQueries({ queryKey: ["entries"] });
      queryClient.invalidateQueries({ queryKey: ["statements"] });
    },
    onError,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl">Immobilisations</h1>
        <p className="mt-1 max-w-2xl text-muted-foreground">
          Journal des biens, plan linéaire et prorata dès la mise en service (SYSCOHADA SN).
          La dotation de la période passe en OD (681 / 28) et alimente le TFT (FF–FH) et la note 3.
        </p>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {dapMessage && <p className="text-sm text-muted-foreground">{dapMessage}</p>}

      <Card>
        <CardHeader>
          <CardTitle>Dotation de la période</CardTitle>
          <CardDescription>
            Une écriture par période, idempotente. Terrains (durée 0) exclus.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3">
          <div className="min-w-[180px] space-y-1">
            <Label htmlFor="dap-period">Période</Label>
            <select
              id="dap-period"
              className={SELECT_CLASS}
              value={periodId}
              onChange={(event) => setPeriodId(event.target.value)}
            >
              {(periods.data ?? []).map((period) => (
                <option key={period.id} value={period.id}>
                  {period.year}-{String(period.month).padStart(2, "0")}
                </option>
              ))}
            </select>
          </div>
          {canWrite && (
            <Button onClick={() => depreciate.mutate()} disabled={!periodId || depreciate.isPending}>
              {depreciate.isPending ? "Comptabilisation…" : "Passer la dotation"}
            </Button>
          )}
        </CardContent>
      </Card>

      {canWrite && (
        <Card>
          <CardHeader>
            <CardTitle>Nouveau bien</CardTitle>
            <CardDescription>
              Compte de classe 2 hors 28/29. Un composant de moins de 12 mois est une charge, pas un
              bien.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="space-y-1 sm:col-span-2">
              <Label htmlFor="asset-label">Libellé</Label>
              <Input id="asset-label" value={label} onChange={(event) => setLabel(event.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="asset-cost">Coût d’entrée</Label>
              <Input id="asset-cost" value={cost} onChange={(event) => setCost(event.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="asset-residual">Valeur résiduelle</Label>
              <Input
                id="asset-residual"
                value={residual}
                onChange={(event) => setResidual(event.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="asset-life">Durée (mois, 0 = non amortissable)</Label>
              <Input id="asset-life" value={life} onChange={(event) => setLife(event.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="asset-kind">Nature</Label>
              <select
                id="asset-kind"
                className={SELECT_CLASS}
                value={kind}
                onChange={(event) => setKind(event.target.value)}
              >
                <option value="standalone">Bien unique</option>
                <option value="structure">Structure</option>
                <option value="component">Composant</option>
              </select>
            </div>
            {kind === "component" && (
              <div className="space-y-1">
                <Label htmlFor="asset-parent">Rattaché à</Label>
                <select
                  id="asset-parent"
                  className={SELECT_CLASS}
                  value={parentId}
                  onChange={(event) => setParentId(event.target.value)}
                >
                  <option value="">Choisir…</option>
                  {parents.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {asset.reference} {asset.label}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div className="space-y-1">
              <Label htmlFor="asset-acquired">Acquisition</Label>
              <Input
                id="asset-acquired"
                type="date"
                value={acquiredOn}
                onChange={(event) => setAcquiredOn(event.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="asset-service">Mise en service</Label>
              <Input
                id="asset-service"
                type="date"
                value={inServiceOn}
                onChange={(event) => setInServiceOn(event.target.value)}
              />
            </div>
            <div className="space-y-1 sm:col-span-2">
              <Label htmlFor="asset-account">Compte d’immobilisation</Label>
              <select
                id="asset-account"
                className={SELECT_CLASS}
                value={accountId}
                onChange={(event) => setAccountId(event.target.value)}
              >
                <option value="">Choisir…</option>
                {class2.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.code} {account.label}
                  </option>
                ))}
              </select>
            </div>
            {needsLife && (
              <>
                <div className="space-y-1">
                  <Label htmlFor="asset-amort">Compte d’amortissement (28)</Label>
                  <select
                    id="asset-amort"
                    className={SELECT_CLASS}
                    value={amortId}
                    onChange={(event) => setAmortId(event.target.value)}
                  >
                    <option value="">Proposé automatiquement</option>
                    {class28.map((account) => (
                      <option key={account.id} value={account.id}>
                        {account.code} {account.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="asset-expense">Dotation (681 / 691 / 697)</Label>
                  <select
                    id="asset-expense"
                    className={SELECT_CLASS}
                    value={expenseId}
                    onChange={(event) => setExpenseId(event.target.value)}
                  >
                    <option value="">Proposé automatiquement</option>
                    {class68.map((account) => (
                      <option key={account.id} value={account.id}>
                        {account.code} {account.label}
                      </option>
                    ))}
                  </select>
                </div>
              </>
            )}
            <div className="space-y-1 sm:col-span-2 lg:col-span-3">
              <Label htmlFor="asset-notes">Note</Label>
              <Input id="asset-notes" value={notes} onChange={(event) => setNotes(event.target.value)} />
            </div>
            <div>
              <Button
                onClick={() => createAsset.mutate()}
                disabled={!label || !cost || !accountId || createAsset.isPending}
              >
                {createAsset.isPending ? "Enregistrement…" : "Enregistrer le bien"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Journal des biens</CardTitle>
          <CardDescription>
            VNC = coût − cumul des dotations. Aperçu = charge de la période sélectionnée.
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-muted-foreground">
              <tr>
                <th className="py-2 pr-3 font-medium">Réf.</th>
                <th className="py-2 pr-3 font-medium">Libellé</th>
                <th className="py-2 pr-3 font-medium">Compte</th>
                <th className="py-2 pr-3 font-medium text-right">Coût</th>
                <th className="py-2 pr-3 font-medium text-right">Cumul</th>
                <th className="py-2 pr-3 font-medium text-right">VNC</th>
                <th className="py-2 pr-3 font-medium text-right">DAP</th>
                <th className="py-2 font-medium">Statut</th>
              </tr>
            </thead>
            <tbody>
              {(assets.data ?? []).map((asset) => (
                <tr key={asset.id} className="border-b border-border/70">
                  <td className="py-2 pr-3 font-mono">{asset.reference}</td>
                  <td className="py-2 pr-3">
                    {asset.label}
                    <span className="ml-2 text-xs text-muted-foreground">
                      {KIND_LABEL[asset.kind] ?? asset.kind}
                      {asset.useful_life_months > 0 ? ` · ${asset.useful_life_months} mois` : " · non amort."}
                    </span>
                  </td>
                  <td className="py-2 pr-3 font-mono">{asset.asset_account_code}</td>
                  <td className="py-2 pr-3 text-right font-mono">{formatMoney(asset.cost, currency)}</td>
                  <td className="py-2 pr-3 text-right font-mono">
                    {formatMoney(asset.accumulated, currency)}
                  </td>
                  <td className="py-2 pr-3 text-right font-mono">{formatMoney(asset.net, currency)}</td>
                  <td className="py-2 pr-3 text-right font-mono">
                    {asset.charge_preview != null ? formatMoney(asset.charge_preview, currency) : "—"}
                  </td>
                  <td className="py-2">
                    <Badge>{STATUS_LABEL[asset.status] ?? asset.status}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {assets.isSuccess && assets.data.length === 0 && (
            <p className="py-6 text-sm text-muted-foreground">Aucun bien enregistré.</p>
          )}
          <p className="mt-4 text-xs text-muted-foreground">
            L’acquisition elle-même se saisit au{" "}
            <Link href={`/app/${orgSlug}/journal/nouveau`} className="underline">
              livre-journal
            </Link>
            . Ici : plan d’amortissement et DAP.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
