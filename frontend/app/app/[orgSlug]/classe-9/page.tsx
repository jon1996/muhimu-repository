"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { BetaScopeGate } from "@/components/beta-scope-gate";
import { useTenant } from "@/components/tenant-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import type { BalanceRow, CagePanel, Class9Balance, LedgerPeriod } from "@/lib/types";

export default function Class9Page() {
  const { orgSlug, companyId, activeCompany, membership } = useTenant();
  const canWrite = ["owner", "admin", "accountant"].includes(membership?.role ?? "");
  const currency = activeCompany?.currency_code ?? "XOF";
  const queryClient = useQueryClient();
  const [periodId, setPeriodId] = useState("");
  const [code, setCode] = useState("");
  const [label, setLabel] = useState("");
  const [isDefault, setIsDefault] = useState(false);
  const [allocSection, setAllocSection] = useState("");
  const [allocKind, setAllocKind] = useState("stock_in");
  const [allocAmount, setAllocAmount] = useState("");
  const [error, setError] = useState("");

  const periods = useQuery({
    queryKey: ["periods", orgSlug, companyId],
    queryFn: () => api<LedgerPeriod[]>("/api/ledger/periods", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const data = useQuery({
    queryKey: ["class9", orgSlug, companyId, periodId],
    queryFn: () =>
      api<Class9Balance>(`/api/ledger/class9${periodId ? `?period_id=${periodId}` : ""}`, {
        orgSlug,
        companyId,
      }),
    enabled: Boolean(orgSlug && companyId),
  });
  const cageQuery = useQuery({
    queryKey: ["cage", orgSlug, companyId, periodId],
    queryFn: () =>
      api<CagePanel>(`/api/ledger/cage${periodId ? `?period_id=${periodId}` : ""}`, {
        orgSlug,
        companyId,
      }),
    enabled: Boolean(orgSlug && companyId),
  });

  const cageQs = periodId ? `?period_id=${periodId}` : "";
  const onError = (err: unknown) => {
    setError(err instanceof ApiError ? err.message : "Action impossible.");
  };
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["cage"] });
    queryClient.invalidateQueries({ queryKey: ["class9"] });
    queryClient.invalidateQueries({ queryKey: ["accounts-postable"] });
    queryClient.invalidateQueries({ queryKey: ["balance"] });
  };

  const createSection = useMutation({
    mutationFn: () =>
      api("/api/ledger/cage/sections", {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({ code, label, is_default: isDefault }),
      }),
    onSuccess: () => {
      setCode("");
      setLabel("");
      setIsDefault(false);
      setError("");
      invalidate();
    },
    onError,
  });

  const patchSection = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api(`/api/ledger/cage/sections/${id}`, {
        method: "PATCH",
        orgSlug,
        companyId,
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      setError("");
      invalidate();
    },
    onError,
  });

  const reflect = useMutation({
    mutationFn: () =>
      api<CagePanel>(`/api/ledger/cage/reflect${cageQs}`, {
        method: "POST",
        orgSlug,
        companyId,
      }),
    onSuccess: () => {
      setError("");
      invalidate();
    },
    onError,
  });

  const allocate = useMutation({
    mutationFn: () =>
      api<CagePanel>("/api/ledger/cage/allocate", {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({
          period_id: periodId || undefined,
          section_id:
            allocSection ||
            sections.find((item) => item.is_default && item.is_active)?.id ||
            sections.find((item) => item.is_active)?.id,
          kind: allocKind,
          amount: allocAmount,
        }),
      }),
    onSuccess: () => {
      setAllocAmount("");
      setError("");
      invalidate();
    },
    onError,
  });

  const closeCage = useMutation({
    mutationFn: () =>
      api<CagePanel>(`/api/ledger/cage/close${cageQs}`, {
        method: "POST",
        orgSlug,
        companyId,
      }),
    onSuccess: () => {
      setError("");
      invalidate();
    },
    onError,
  });

  const cage = cageQuery.data;
  const sections = cage?.sections ?? [];
  const results = cage?.results ?? [];

  return (
    <BetaScopeGate feature="class9_cage">
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl">Classe 9</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            Facultative. 90/91 = engagements hors bilan (notes d’abord). 92–99 = CAGE : les
            charges (classe 6) et produits (classe 7) se réfléchissent sur les sections 95
            (921/927), puis 93/94 stocks, 96 écarts, 97 incorporation, clôture 95 → 981. Jamais
            mélangé aux classes 1 à 8, hors bilan / CR / TFT.
          </p>
        </div>
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
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle>Sections CAGE</CardTitle>
          <CardDescription>
            Chaque section ouvre un compte 95-CODE. Sans section active, le réfléchissement
            reste inactif (CAGE facultative).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {canWrite && (
            <form
              className="grid gap-3 md:grid-cols-[140px_1fr_auto_auto] md:items-end"
              onSubmit={(event) => {
                event.preventDefault();
                createSection.mutate();
              }}
            >
              <div>
                <Label htmlFor="cage-code">Code</Label>
                <Input
                  id="cage-code"
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                  placeholder="PROD"
                  required
                />
              </div>
              <div>
                <Label htmlFor="cage-label">Intitulé</Label>
                <Input
                  id="cage-label"
                  value={label}
                  onChange={(event) => setLabel(event.target.value)}
                  placeholder="Production"
                  required
                />
              </div>
              <label className="flex h-10 items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={isDefault}
                  onChange={(event) => setIsDefault(event.target.checked)}
                />
                Par défaut
              </label>
              <Button type="submit" disabled={createSection.isPending}>
                {createSection.isPending ? "Création…" : "Ajouter"}
              </Button>
            </form>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-muted-foreground">
                <tr>
                  <th className="py-2 pr-3 font-medium">Code</th>
                  <th className="py-2 pr-3 font-medium">Intitulé</th>
                  <th className="py-2 pr-3 font-medium">Compte</th>
                  <th className="py-2 pr-3 font-medium">Statut</th>
                  {canWrite && <th className="py-2 font-medium" />}
                </tr>
              </thead>
              <tbody>
                {sections.map((section) => (
                  <tr key={section.id} className="border-b border-border/70">
                    <td className="py-1.5 pr-3 font-mono">{section.code}</td>
                    <td className="py-1.5 pr-3">{section.label}</td>
                    <td className="py-1.5 pr-3 font-mono">{section.account_code}</td>
                    <td className="py-1.5 pr-3 text-muted-foreground">
                      {section.is_active ? "Active" : "Inactive"}
                      {section.is_default ? " · défaut" : ""}
                    </td>
                    {canWrite && (
                      <td className="py-1.5 text-right">
                        <div className="flex justify-end gap-2">
                          {!section.is_default && section.is_active && (
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() =>
                                patchSection.mutate({ id: section.id, body: { is_default: true } })
                              }
                            >
                              Défaut
                            </Button>
                          )}
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              patchSection.mutate({
                                id: section.id,
                                body: { is_active: !section.is_active },
                              })
                            }
                          >
                            {section.is_active ? "Désactiver" : "Réactiver"}
                          </Button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
            {sections.length === 0 && (
              <p className="py-6 text-sm text-muted-foreground">Aucune section pour l’instant.</p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-4">
          <div>
            <CardTitle>Résultat par section</CardTitle>
            <CardDescription>
              Réfléchissement 921 (charges) et 927 (produits) sur le 95. {cage?.pending ?? 0}{" "}
              {(cage?.pending ?? 0) > 1 ? "écritures" : "écriture"} 6/7 en attente
              {cage?.last_entry_number ? ` · dernière ${cage.last_entry_number}` : ""}
              {cage?.closed
                ? ` · clôturée vers 981${cage.close_entry_number ? ` (${cage.close_entry_number})` : ""}`
                : ""}
              {cage?.analytical_result && cage.analytical_result !== "0"
                ? ` · 981 ${formatMoney(cage.analytical_result, currency)}`
                : ""}
              .
            </CardDescription>
          </div>
          {canWrite && (
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                disabled={reflect.isPending || (cage?.pending ?? 0) === 0 || Boolean(cage?.closed)}
                onClick={() => reflect.mutate()}
              >
                {reflect.isPending ? "Réflexion…" : "Réfléchir la période"}
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={
                  closeCage.isPending ||
                  Boolean(cage?.closed) ||
                  (cage?.pending ?? 0) > 0 ||
                  results.length === 0
                }
                onClick={() => closeCage.mutate()}
              >
                {closeCage.isPending ? "Clôture…" : cage?.closed ? "CAGE clôturée" : "Clôturer vers 981"}
              </Button>
            </div>
          )}
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-muted-foreground">
                <tr>
                  <th className="py-2 pr-3 font-medium">Section</th>
                  <th className="py-2 pr-3 font-medium text-right">Charges</th>
                  <th className="py-2 pr-3 font-medium text-right">Produits</th>
                  <th className="py-2 font-medium text-right">Résultat</th>
                </tr>
              </thead>
              <tbody>
                {results.map((row) => (
                  <tr key={row.section_id} className="border-b border-border/70">
                    <td className="py-1.5 pr-3">
                      <span className="font-mono">{row.code}</span> {row.label}
                    </td>
                    <td className="py-1.5 pr-3 text-right font-mono">
                      {formatMoney(row.charges, currency)}
                    </td>
                    <td className="py-1.5 pr-3 text-right font-mono">
                      {formatMoney(row.products, currency)}
                    </td>
                    <td className="py-1.5 text-right font-mono">
                      {formatMoney(row.result, currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {results.length === 0 && (
              <p className="py-6 text-sm text-muted-foreground">
                Créez une section, puis validez une charge ou un produit : le 95 est mouvementé à
                la validation, ou via « Réfléchir la période » pour l’existant.
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>93 / 94 / 96 / 97 — imputations</CardTitle>
          <CardDescription>
            Stocks (95 → 93 → 94), écarts sur coûts préétablis (96) et différences
            d’incorporation (97). Classe 9 uniquement. Impossible après clôture 981.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {canWrite && (
            <form
              className="grid gap-3 md:grid-cols-[1fr_1fr_160px_auto] md:items-end"
              onSubmit={(event) => {
                event.preventDefault();
                allocate.mutate();
              }}
            >
              <div>
                <Label htmlFor="cage-alloc-section">Section</Label>
                <select
                  id="cage-alloc-section"
                  className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                  value={allocSection || sections.find((item) => item.is_default && item.is_active)?.id || ""}
                  onChange={(event) => setAllocSection(event.target.value)}
                  required
                >
                  <option value="">Choisir…</option>
                  {sections
                    .filter((item) => item.is_active)
                    .map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.code} — {item.label}
                      </option>
                    ))}
                </select>
              </div>
              <div>
                <Label htmlFor="cage-alloc-kind">Nature</Label>
                <select
                  id="cage-alloc-kind"
                  className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                  value={allocKind}
                  onChange={(event) => setAllocKind(event.target.value)}
                >
                  <option value="stock_in">93/94 — entrée stock</option>
                  <option value="stock_out">93/94 — sortie stock</option>
                  <option value="variance">96 — écart (positif = défavorable)</option>
                  <option value="charge_ni">97 — charge non incorporable</option>
                  <option value="product_ni">97 — produit non incorporable</option>
                  <option value="suppletive">97 — charge supplétive</option>
                </select>
              </div>
              <div>
                <Label htmlFor="cage-alloc-amount">Montant</Label>
                <Input
                  id="cage-alloc-amount"
                  value={allocAmount}
                  onChange={(event) => setAllocAmount(event.target.value)}
                  placeholder="0"
                  required
                />
              </div>
              <Button type="submit" disabled={allocate.isPending || Boolean(cage?.closed) || sections.length === 0}>
                {allocate.isPending ? "Imputation…" : "Imputer"}
              </Button>
            </form>
          )}
          <p className="text-sm text-muted-foreground">
            Les soldes 93, 94, 96, 97 et 98 apparaissent dans la balance CAGE ci-dessous.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>90 / 91 — engagements hors bilan</CardTitle>
          <CardDescription>
            Comptabilisez depuis le registre{" "}
            <Link className="underline" href={`/app/${orgSlug}/engagements`}>
              Engagements
            </Link>
            . La note 1 reste obligatoire dès que c’est significatif.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <BalanceTable
            rows={data.data?.engagements ?? []}
            currency={currency}
            empty="Aucun mouvement 90/91 sur cette période."
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>92–99 — balances CAGE</CardTitle>
          <CardDescription>
            Soldes 921/927, 93/94, 95, 96, 97, 981 et 99 sur la période.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <BalanceTable
            rows={data.data?.cage ?? []}
            currency={currency}
            empty="Aucune section CAGE mouvementée."
          />
        </CardContent>
      </Card>
    </div>
    </BetaScopeGate>
  );
}

function BalanceTable({
  rows,
  currency,
  empty,
}: {
  rows: BalanceRow[];
  currency: string;
  empty: string;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-border text-muted-foreground">
          <tr>
            <th className="py-2 pr-3 font-medium">Compte</th>
            <th className="py-2 pr-3 font-medium">Intitulé</th>
            <th className="py-2 pr-3 font-medium text-right">Solde D</th>
            <th className="py-2 font-medium text-right">Solde C</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.account_id} className="border-b border-border/70">
              <td className="py-1.5 pr-3 font-mono">{row.code}</td>
              <td className="py-1.5 pr-3">{row.label}</td>
              <td className="py-1.5 pr-3 text-right font-mono">{formatMoney(row.close_debit, currency)}</td>
              <td className="py-1.5 text-right font-mono">{formatMoney(row.close_credit, currency)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && <p className="py-6 text-sm text-muted-foreground">{empty}</p>}
    </div>
  );
}
