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
import type { InventoryCampaign, LedgerAccount, LedgerExercise, LedgerPeriod, OpeningPreview, OpeningState, FxRevaluePreview } from "@/lib/types";

const PERIOD_LABEL: Record<string, string> = {
  open: "Ouverte",
  validated: "Validée",
  it_closed: "Clôture informatique",
};
const SELECT_CLASS = "h-10 w-full rounded-md border border-input bg-background px-3 text-sm";

export default function ClosingPage() {
  const { orgSlug, companyId, activeCompany, membership } = useTenant();
  const canWrite = ["owner", "admin", "accountant"].includes(membership?.role ?? "");
  const currency = activeCompany?.currency_code ?? "XOF";
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const [invDate, setInvDate] = useState("");
  const [lineDesc, setLineDesc] = useState("");
  const [lineQty, setLineQty] = useState("1");
  const [lineValue, setLineValue] = useState("0");
  const [lineAccount, setLineAccount] = useState("");
  const [lineUnit, setLineUnit] = useState("u");
  const [invMethod, setInvMethod] = useState("cump");
  const [closedOn, setClosedOn] = useState("");
  const [approvedOn, setApprovedOn] = useState("");
  const [legal, setLegal] = useState("0");
  const [free, setFree] = useState("0");
  const [retained, setRetained] = useState("0");
  const [dividends, setDividends] = useState("0");
  const [payDiv, setPayDiv] = useState(false);
  const [bankId, setBankId] = useState("");
  const [openingCsv, setOpeningCsv] = useState("");
  const [openingPreview, setOpeningPreview] = useState<OpeningPreview | null>(null);
  const [fxDate, setFxDate] = useState("");
  const [fxPreview, setFxPreview] = useState<FxRevaluePreview | null>(null);

  useEffect(() => {
    const today = localTodayIso();
    setInvDate((current) => current || today);
    setClosedOn((current) => current || today);
    setApprovedOn((current) => current || today);
    setFxDate((current) => current || today);
  }, []);

  const periods = useQuery({
    queryKey: ["periods", orgSlug, companyId],
    queryFn: () => api<LedgerPeriod[]>("/api/ledger/periods", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const exercises = useQuery({
    queryKey: ["exercises", orgSlug, companyId],
    queryFn: () => api<LedgerExercise[]>("/api/ledger/exercises", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const accounts = useQuery({
    queryKey: ["accounts", orgSlug, companyId],
    queryFn: () => api<LedgerAccount[]>("/api/ledger/accounts?postable=true", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const inventories = useQuery({
    queryKey: ["inventories", orgSlug, companyId],
    queryFn: () => api<InventoryCampaign[]>("/api/ledger/inventories", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const openingYear = (exercises.data ?? []).find((item) => item.status === "open")?.year;
  const opening = useQuery({
    queryKey: ["opening", orgSlug, companyId, openingYear],
    queryFn: () =>
      api<OpeningState>(`/api/ledger/opening?year=${openingYear}`, {
        orgSlug,
        companyId,
      }),
    enabled: Boolean(orgSlug && companyId && openingYear),
  });

  const onError = (err: unknown) => {
    setError(err instanceof ApiError ? err.message : "Action impossible.");
  };

  const validate = useMutation({
    mutationFn: (id: string) =>
      api<LedgerPeriod>(`/api/ledger/periods/${id}/validate`, { method: "POST", orgSlug, companyId }),
    onSuccess: () => {
      setError("");
      queryClient.invalidateQueries({ queryKey: ["periods"] });
    },
    onError,
  });
  const itClose = useMutation({
    mutationFn: (id: string) =>
      api<LedgerPeriod>(`/api/ledger/periods/${id}/it-close`, { method: "POST", orgSlug, companyId }),
    onSuccess: () => {
      setError("");
      queryClient.invalidateQueries({ queryKey: ["periods"] });
    },
    onError,
  });
  const createInv = useMutation({
    mutationFn: () =>
      api<InventoryCampaign>("/api/ledger/inventories", {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({ inventoried_on: invDate, method: invMethod }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["inventories"] }),
    onError,
  });
  const addLine = useMutation({
    mutationFn: (campaignId: string) =>
      api<InventoryCampaign>(`/api/ledger/inventories/${campaignId}/lines`, {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({
          description: lineDesc,
          quantity: lineQty,
          unit_value: lineValue,
          unit: lineUnit,
          account_id: lineAccount || null,
        }),
      }),
    onSuccess: () => {
      setLineDesc("");
      queryClient.invalidateQueries({ queryKey: ["inventories"] });
    },
    onError,
  });
  const closeInv = useMutation({
    mutationFn: (campaignId: string) =>
      api<InventoryCampaign>(`/api/ledger/inventories/${campaignId}/close`, {
        method: "POST",
        orgSlug,
        companyId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inventories"] });
      queryClient.invalidateQueries({ queryKey: ["statements"] });
      queryClient.invalidateQueries({ queryKey: ["entries"] });
    },
    onError,
  });
  const previewOpening = useMutation({
    mutationFn: () =>
      api<OpeningPreview>("/api/ledger/opening/preview", {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({ year: openingYear, csv: openingCsv }),
      }),
    onSuccess: (data) => {
      setOpeningPreview(data);
      setError(data.errors[0] || "");
    },
    onError,
  });
  const postOpening = useMutation({
    mutationFn: () =>
      api<OpeningPreview>("/api/ledger/opening", {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({ year: openingYear, csv: openingCsv }),
      }),
    onSuccess: (data) => {
      setOpeningPreview(data);
      setError("");
      queryClient.invalidateQueries({ queryKey: ["opening"] });
      queryClient.invalidateQueries({ queryKey: ["exercises"] });
      queryClient.invalidateQueries({ queryKey: ["entries"] });
      queryClient.invalidateQueries({ queryKey: ["balance"] });
      queryClient.invalidateQueries({ queryKey: ["statements"] });
    },
    onError,
  });
  const previewFx = useMutation({
    mutationFn: () =>
      api<FxRevaluePreview>(`/api/ledger/fx/revalue?as_of=${fxDate}`, { orgSlug, companyId }),
    onSuccess: (data) => {
      setFxPreview(data);
      setError(data.errors[0] || "");
    },
    onError,
  });
  const postFx = useMutation({
    mutationFn: () =>
      api<FxRevaluePreview>("/api/ledger/fx/revalue", {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({ as_of: fxDate }),
      }),
    onSuccess: (data) => {
      setFxPreview(data);
      setError("");
      queryClient.invalidateQueries({ queryKey: ["entries"] });
      queryClient.invalidateQueries({ queryKey: ["balance"] });
      queryClient.invalidateQueries({ queryKey: ["statements"] });
    },
    onError,
  });
  const exercise =
    (exercises.data ?? []).find((item) => item.can_allocate) ||
    (exercises.data ?? []).find((item) => item.status === "open") ||
    (exercises.data ?? [])[0];
  const banks = (accounts.data ?? []).filter((account) => account.account_class === "5");
  const stockAccounts = useMemo(
    () =>
      (accounts.data ?? []).filter(
        (account) => account.account_class === "3" && !account.code.startsWith("39"),
      ),
    [accounts.data],
  );
  const profit = Number(exercise?.net_result ?? 0);

  useEffect(() => {
    if (!exercise) return;
    setLegal(exercise.suggested_legal_reserve);
    setRetained(exercise.suggested_retained);
    setFree("0");
    setDividends("0");
    if (exercise.approved_on) setApprovedOn(exercise.approved_on);
    if (exercise.closed_on) setClosedOn(exercise.closed_on);
  }, [exercise?.id, exercise?.net_result, exercise?.suggested_legal_reserve, exercise?.suggested_retained]);

  const closeYear = useMutation({
    mutationFn: () =>
      api<LedgerExercise>("/api/ledger/exercise/close", {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({ year: exercise?.year, closed_on: closedOn }),
      }),
    onSuccess: () => {
      setError("");
      queryClient.invalidateQueries({ queryKey: ["exercises"] });
      queryClient.invalidateQueries({ queryKey: ["statements"] });
      queryClient.invalidateQueries({ queryKey: ["entries"] });
      queryClient.invalidateQueries({ queryKey: ["ledger-status"] });
    },
    onError,
  });
  const allocate = useMutation({
    mutationFn: () => {
      const net = Number(exercise?.net_result ?? 0);
      const isLoss = net < 0;
      return api<LedgerExercise>("/api/ledger/exercise/allocate", {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({
          year: exercise?.year,
          approved_on: approvedOn,
          legal_reserve: isLoss ? "0" : legal,
          free_reserve: isLoss ? "0" : free,
          retained: isLoss ? String(Math.abs(net)) : retained,
          dividends: isLoss ? "0" : dividends,
          pay_dividends: isLoss ? false : payDiv,
          bank_account_id: bankId || null,
        }),
      });
    },
    onSuccess: () => {
      setError("");
      queryClient.invalidateQueries({ queryKey: ["exercises"] });
      queryClient.invalidateQueries({ queryKey: ["statements"] });
      queryClient.invalidateQueries({ queryKey: ["entries"] });
    },
    onError,
  });

  const draftInv = (inventories.data ?? []).find((item) => item.status === "draft");
  const STATUS_EX: Record<string, string> = {
    open: "Ouvert",
    closing: "En clôture",
    closed: "Clôturé",
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl">Clôture</h1>
        <p className="mt-1 max-w-2xl text-muted-foreground">
          Arrêté d’exercice (6/7 → 13, bilan avant répartition), affectation AG (note 31, FN),
          soldes d’ouverture (reprise), réévaluation des devises (478/479), validation mensuelle
          (art. 22) et inventaire (art. 16, VIII.14). Les DAP se passent depuis Immobilisations.
        </p>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}

      {openingYear && (
        <Card>
          <CardHeader>
            <CardTitle>Soldes d’ouverture {openingYear}</CardTitle>
            <CardDescription>
              Reprise d’un dossier : à-nouveaux au 1er janvier (classes 1–5 + 13, journal AN). Les
              classes 6/7/8 du fichier alimentent uniquement la colonne N-1 du CR. Collez un CSV
              `code;debit;credit`.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {opening.data?.posted ? (
              <p className="text-sm">
                Validés :{" "}
                {opening.data.entry_id ? (
                  <Link className="underline" href={`/app/${orgSlug}/journal/${opening.data.entry_id}`}>
                    {opening.data.entry_number || "écriture AN"}
                  </Link>
                ) : (
                  opening.data.entry_number
                )}
                {opening.data.prior_seeded > 0
                  ? ` · ${opening.data.prior_seeded} comptes en colonne ${opening.data.prior_year}`
                  : ""}
                . Contrepasser l’écriture pour reprendre.
              </p>
            ) : (
              canWrite && (
                <>
                  <div className="space-y-1.5">
                    <Label htmlFor="opening-csv">Balance à reprendre</Label>
                    <textarea
                      id="opening-csv"
                      className="min-h-36 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm"
                      placeholder={opening.data?.template || "code;debit;credit"}
                      value={openingCsv}
                      onChange={(event) => {
                        setOpeningCsv(event.target.value);
                        setOpeningPreview(null);
                      }}
                    />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      disabled={!openingCsv.trim() || previewOpening.isPending}
                      onClick={() => previewOpening.mutate()}
                    >
                      {previewOpening.isPending ? "Contrôle…" : "Contrôler"}
                    </Button>
                    <Button
                      type="button"
                      disabled={!openingPreview?.ok || postOpening.isPending}
                      onClick={() => postOpening.mutate()}
                    >
                      {postOpening.isPending ? "Validation…" : "Valider les à-nouveaux"}
                    </Button>
                  </div>
                </>
              )
            )}
            {openingPreview && (
              <div className="space-y-2 text-sm">
                <p>
                  AN débit {formatMoney(openingPreview.an_debit, currency)} · crédit{" "}
                  {formatMoney(openingPreview.an_credit, currency)}
                  {openingPreview.pnl_count > 0
                    ? ` · CR N-1 : ${openingPreview.pnl_count} comptes · résultat ${formatMoney(openingPreview.net_result_prior, currency)}`
                    : ""}
                </p>
                {openingPreview.warnings.map((item) => (
                  <p key={item} className="text-muted-foreground">
                    {item}
                  </p>
                ))}
                {openingPreview.errors.map((item) => (
                  <p key={item} className="text-destructive">
                    {item}
                  </p>
                ))}
                {openingPreview.an_lines.length > 0 && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead className="border-b border-border text-muted-foreground">
                        <tr>
                          <th className="py-1.5 pr-3 font-medium">Compte</th>
                          <th className="py-1.5 pr-3 font-medium">Intitulé</th>
                          <th className="py-1.5 pr-3 font-medium text-right">Débit</th>
                          <th className="py-1.5 font-medium text-right">Crédit</th>
                        </tr>
                      </thead>
                      <tbody>
                        {openingPreview.an_lines.map((line) => (
                          <tr key={line.account_id || line.code} className="border-b border-border/70">
                            <td className="py-1 pr-3 font-mono">{line.code}</td>
                            <td className="py-1 pr-3">{line.label}</td>
                            <td className="py-1 pr-3 text-right font-mono">
                              {formatMoney(line.debit, currency)}
                            </td>
                            <td className="py-1 text-right font-mono">{formatMoney(line.credit, currency)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Réévaluation des devises</CardTitle>
          <CardDescription>
            Postes monétaires en devises (classes 4 et 5) au cours d’arrêté. Perte latente → 478
            (BU), gain latent → 479 (DV). Une seule écriture OD par date ; contrepasser pour
            reprendre. Les cours se saisissent dans{" "}
            <Link className="underline" href={`/app/${orgSlug}/devises`}>
              Devises
            </Link>
            .
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="fx-as-of">Date d’arrêté</Label>
              <Input
                id="fx-as-of"
                type="date"
                value={fxDate}
                onChange={(event) => {
                  setFxDate(event.target.value);
                  setFxPreview(null);
                }}
              />
            </div>
            {canWrite && (
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  disabled={!fxDate || previewFx.isPending}
                  onClick={() => previewFx.mutate()}
                >
                  {previewFx.isPending ? "Contrôle…" : "Contrôler"}
                </Button>
                <Button
                  type="button"
                  disabled={!fxPreview?.ok || !fxPreview.lines.length || fxPreview.posted || postFx.isPending}
                  onClick={() => postFx.mutate()}
                >
                  {postFx.isPending ? "Validation…" : "Constater les écarts 478/479"}
                </Button>
              </div>
            )}
          </div>
          {fxPreview && (
            <div className="space-y-2 text-sm">
              {fxPreview.posted && fxPreview.entry_id ? (
                <p>
                  Validée :{" "}
                  <Link className="underline" href={`/app/${orgSlug}/journal/${fxPreview.entry_id}`}>
                    {fxPreview.entry_number || "écriture FX"}
                  </Link>
                  .
                </p>
              ) : fxPreview.lines.length === 0 && fxPreview.ok ? (
                <p className="text-muted-foreground">Aucun écart de conversion à constater.</p>
              ) : (
                <p>
                  Gains {formatMoney(fxPreview.gain, currency)} · pertes{" "}
                  {formatMoney(fxPreview.loss, currency)}
                </p>
              )}
              {fxPreview.warnings.map((item) => (
                <p key={item} className="text-muted-foreground">
                  {item}
                </p>
              ))}
              {fxPreview.errors.map((item) => (
                <p key={item} className="text-destructive">
                  {item}
                </p>
              ))}
              {fxPreview.lines.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="border-b border-border text-muted-foreground">
                      <tr>
                        <th className="py-1.5 pr-3 font-medium">Compte</th>
                        <th className="py-1.5 pr-3 font-medium">Devise</th>
                        <th className="py-1.5 pr-3 font-medium text-right">Position</th>
                        <th className="py-1.5 pr-3 font-medium text-right">Cours</th>
                        <th className="py-1.5 pr-3 font-medium text-right">Écart</th>
                        <th className="py-1.5 font-medium">Écriture</th>
                      </tr>
                    </thead>
                    <tbody>
                      {fxPreview.lines.map((line) => (
                        <tr key={`${line.account_id}-${line.currency_code}`} className="border-b border-border/70">
                          <td className="py-1 pr-3 font-mono">
                            {line.account_code} {line.account_label}
                          </td>
                          <td className="py-1 pr-3 font-mono">{line.currency_code}</td>
                          <td className="py-1 pr-3 text-right font-mono">{line.foreign_net}</td>
                          <td className="py-1 pr-3 text-right font-mono">{line.closing_rate}</td>
                          <td className="py-1 pr-3 text-right font-mono">
                            {formatMoney(line.difference, currency)}
                          </td>
                          <td className="py-1 font-mono text-xs">
                            {line.debit_account_code} / {line.credit_account_code}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {exercise && (
        <Card>
          <CardHeader>
            <CardTitle>Exercice {exercise.year}</CardTitle>
            <CardDescription>
              Le bilan N reste avant répartition. L’affectation se comptabilise sur l’exercice
              suivant (AGO).
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <Badge>{STATUS_EX[exercise.status] ?? exercise.status}</Badge>
              <span>
                Résultat {formatMoney(exercise.net_result, currency)} {currency}
              </span>
              <span className="text-muted-foreground">
                CA {formatMoney(exercise.revenue, currency)}
              </span>
            </div>
            {exercise.blockers.length > 0 && (
              <ul className="list-disc pl-5 text-sm text-destructive">
                {exercise.blockers.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
            {canWrite && exercise.can_close && (
              <div className="flex flex-wrap items-end gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="closed-on">Date d’arrêté</Label>
                  <Input
                    id="closed-on"
                    type="date"
                    value={closedOn}
                    onChange={(event) => setClosedOn(event.target.value)}
                  />
                </div>
                <Button onClick={() => closeYear.mutate()} disabled={closeYear.isPending}>
                  {closeYear.isPending ? "Arrêté…" : "Arrêter l’exercice"}
                </Button>
              </div>
            )}
            {canWrite && exercise.can_allocate && profit > 0 && (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="space-y-1.5">
                  <Label>Date d’AGO</Label>
                  <Input type="date" value={approvedOn} onChange={(event) => setApprovedOn(event.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label>Réserve légale (10 %)</Label>
                  <Input value={legal} onChange={(event) => setLegal(event.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label>Réserves libres</Label>
                  <Input value={free} onChange={(event) => setFree(event.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label>Report à nouveau</Label>
                  <Input value={retained} onChange={(event) => setRetained(event.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label>Dividendes</Label>
                  <Input value={dividends} onChange={(event) => setDividends(event.target.value)} />
                </div>
                <label className="flex items-center gap-2 self-end text-sm">
                  <input type="checkbox" checked={payDiv} onChange={(event) => setPayDiv(event.target.checked)} />
                  Payer maintenant (FN)
                </label>
                {payDiv && (
                  <div className="space-y-1.5 sm:col-span-2">
                    <Label>Banque / caisse</Label>
                    <select
                      className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                      value={bankId}
                      onChange={(event) => setBankId(event.target.value)}
                    >
                      <option value="">521 (proposé)</option>
                      {banks.map((account) => (
                        <option key={account.id} value={account.id}>
                          {account.code} {account.label}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                <div className="self-end">
                  <Button onClick={() => allocate.mutate()} disabled={allocate.isPending}>
                    {allocate.isPending ? "Affectation…" : "Affecter le résultat"}
                  </Button>
                </div>
              </div>
            )}
            {canWrite && exercise.can_allocate && profit < 0 && (
              <div className="flex flex-wrap items-end gap-3">
                <div className="space-y-1.5">
                  <Label>Date d’AGO</Label>
                  <Input type="date" value={approvedOn} onChange={(event) => setApprovedOn(event.target.value)} />
                </div>
                <p className="text-sm text-muted-foreground">
                  Perte portée en report à nouveau débiteur (129).
                </p>
                <Button onClick={() => allocate.mutate()} disabled={allocate.isPending}>
                  Reporter la perte
                </Button>
              </div>
            )}
            {exercise.allocation_entry_id && (
              <p className="text-sm text-muted-foreground">
                Affecté : légale {formatMoney(exercise.legal_reserve_amount, currency)} · libres{" "}
                {formatMoney(exercise.free_reserve_amount, currency)} · RAN{" "}
                {formatMoney(exercise.retained_amount, currency)} · dividendes{" "}
                {formatMoney(exercise.dividends_amount, currency)}
                {exercise.approved_on ? ` · AGO ${exercise.approved_on}` : ""}.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Périodes</CardTitle>
          <CardDescription>Valider fige le mois. La clôture informatique pose un sceau.</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-muted-foreground">
              <tr>
                <th className="py-2 pr-3 font-medium">Mois</th>
                <th className="py-2 pr-3 font-medium">Statut</th>
                <th className="py-2 font-medium" />
              </tr>
            </thead>
            <tbody>
              {(periods.data ?? []).map((period) => (
                <tr key={period.id} className="border-b border-border/70">
                  <td className="py-2 pr-3 font-mono">
                    {period.year}-{String(period.month).padStart(2, "0")}
                  </td>
                  <td className="py-2 pr-3">
                    <Badge>{PERIOD_LABEL[period.status] ?? period.status}</Badge>
                    {period.seal ? (
                      <span className="ml-2 font-mono text-[10px] text-muted-foreground">
                        {period.seal.slice(0, 12)}…
                      </span>
                    ) : null}
                  </td>
                  <td className="py-2 text-right">
                    {canWrite && period.status === "open" && (
                      <Button size="sm" variant="outline" onClick={() => validate.mutate(period.id)}>
                        Valider
                      </Button>
                    )}
                    {canWrite && period.status === "validated" && (
                      <Button size="sm" onClick={() => itClose.mutate(period.id)}>
                        Clôture informatique
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Inventaire physique</CardTitle>
          <CardDescription>
            Comptage extra-comptable (art. 16). Les lignes classe 3 passent en OD de variation
            (3 / 603 ou 73) et alimentent la note 6. CUMP par défaut (inventaire intermittent,
            VIII.14) ; PEPS est enregistré pour la note, sans lots.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {canWrite && !draftInv && (
            <div className="flex flex-wrap items-end gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="inv-date">Date d’inventaire</Label>
                <Input id="inv-date" type="date" value={invDate} onChange={(event) => setInvDate(event.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Méthode</Label>
                <select
                  className={SELECT_CLASS}
                  value={invMethod}
                  onChange={(event) => setInvMethod(event.target.value)}
                >
                  <option value="cump">CUMP</option>
                  <option value="peps">PEPS</option>
                </select>
              </div>
              <Button onClick={() => createInv.mutate()}>Ouvrir un inventaire</Button>
            </div>
          )}
          {draftInv && canWrite && (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
              <div className="space-y-1.5 xl:col-span-2">
                <Label>Compte de stock</Label>
                <select
                  className={SELECT_CLASS}
                  value={lineAccount}
                  onChange={(event) => setLineAccount(event.target.value)}
                >
                  <option value="">—</option>
                  {stockAccounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.code} · {account.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5 xl:col-span-2">
                <Label>Désignation</Label>
                <Input value={lineDesc} onChange={(event) => setLineDesc(event.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Quantité</Label>
                <Input value={lineQty} onChange={(event) => setLineQty(event.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Unité</Label>
                <Input value={lineUnit} onChange={(event) => setLineUnit(event.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Coût unitaire (CUMP)</Label>
                <Input value={lineValue} onChange={(event) => setLineValue(event.target.value)} />
              </div>
              <Button
                className="self-end"
                disabled={!lineDesc}
                onClick={() => addLine.mutate(draftInv.id)}
              >
                Ajouter
              </Button>
            </div>
          )}
          {(inventories.data ?? []).map((campaign) => (
            <div key={campaign.id} className="rounded-lg border border-border p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="text-sm font-medium">
                  {campaign.inventoried_on} · {campaign.status === "closed" ? "Arrêté" : "En cours"} ·{" "}
                  {campaign.method_label ?? "CUMP"} · total {formatMoney(campaign.total, currency)}
                  {campaign.variation_entry_number
                    ? ` · OD ${campaign.variation_entry_number}`
                    : campaign.status === "closed"
                      ? " · pas d’OD de variation"
                      : ""}
                </p>
                {canWrite && campaign.status === "draft" && (
                  <Button size="sm" variant="outline" onClick={() => closeInv.mutate(campaign.id)}>
                    Arrêter et passer la variation
                  </Button>
                )}
              </div>
              <ul className="space-y-1 text-sm text-muted-foreground">
                {campaign.lines.map((line) => (
                  <li key={line.id}>
                    {line.account_code ? `${line.account_code} · ` : ""}
                    {line.description} · {line.quantity}
                    {line.unit ? ` ${line.unit}` : ""} × {formatMoney(line.unit_value, currency)} ={" "}
                    {formatMoney(line.amount, currency)}
                  </li>
                ))}
                {campaign.lines.length === 0 && <li>Aucun poste.</li>}
              </ul>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
