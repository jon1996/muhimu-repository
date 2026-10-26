"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { useTenant } from "@/components/tenant-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { localTodayIso } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import type { BankRecon, CashCount, CashPanel, LedgerAccount, OfxImport } from "@/lib/types";

const SELECT_CLASS = "h-10 w-full rounded-md border border-input bg-background px-3 text-sm";

export default function TreasuryPage() {
  const { orgSlug, companyId, activeCompany, membership } = useTenant();
  const canWrite = ["owner", "admin", "accountant"].includes(membership?.role ?? "");
  const currency = activeCompany?.currency_code ?? "XOF";
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"bank" | "cash">("bank");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [accountId, setAccountId] = useState("");
  const [cashAccountId, setCashAccountId] = useState("");
  const [countedOn, setCountedOn] = useState("");
  const [physicalAmount, setPhysicalAmount] = useState("");
  const [cashNotes, setCashNotes] = useState("");
  const [statementDate, setStatementDate] = useState("");
  const [bankBalance, setBankBalance] = useState("");
  const [lineDate, setLineDate] = useState("");
  const [lineLabel, setLineLabel] = useState("");
  const [lineDebit, setLineDebit] = useState("");
  const [lineCredit, setLineCredit] = useState("");
  const [selectedBooks, setSelectedBooks] = useState<string[]>([]);
  const [selectedBank, setSelectedBank] = useState<string[]>([]);
  const ofxRef = useRef<HTMLInputElement>(null);

  const accounts = useQuery({
    queryKey: ["accounts", orgSlug, companyId],
    queryFn: () => api<LedgerAccount[]>("/api/ledger/accounts?postable=true", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const recon = useQuery({
    queryKey: ["bank-recon", orgSlug, companyId, accountId],
    queryFn: () =>
      api<BankRecon>(
        `/api/ledger/bank/reconciliation${accountId ? `?account_id=${accountId}` : ""}`,
        { orgSlug, companyId },
      ),
    enabled: Boolean(orgSlug && companyId && tab === "bank"),
  });
  const cash = useQuery({
    queryKey: ["cash-panel", orgSlug, companyId, cashAccountId],
    queryFn: () =>
      api<CashPanel>(
        `/api/ledger/cash${cashAccountId ? `?account_id=${cashAccountId}` : ""}`,
        { orgSlug, companyId },
      ),
    enabled: Boolean(orgSlug && companyId && tab === "cash"),
  });

  const banks = useMemo(
    () =>
      (accounts.data ?? []).filter(
        (account) => account.code.startsWith("52") || account.code.startsWith("53"),
      ),
    [accounts.data],
  );
  const tills = useMemo(
    () => (accounts.data ?? []).filter((account) => account.code.startsWith("57")),
    [accounts.data],
  );

  const data = recon.data;
  const activeAccountId = accountId || data?.account_id || "";

  useEffect(() => {
    const today = localTodayIso();
    setStatementDate((current) => current || today);
    setLineDate((current) => current || today);
    setCountedOn((current) => current || today);
  }, []);

  useEffect(() => {
    const latest = cash.data?.count;
    if (!latest) {
      setPhysicalAmount(cash.data?.book_balance ?? "");
      setCashNotes("");
      return;
    }
    setCountedOn(latest.counted_on);
    setPhysicalAmount(latest.physical_amount);
    setCashNotes(latest.notes);
  }, [cash.data?.account_id, cash.data?.count?.id]);

  useEffect(() => {
    if (!data?.statement) return;
    setStatementDate(data.statement.statement_date);
    setBankBalance(data.statement.bank_balance);
    setLineDate(data.statement.statement_date);
  }, [data?.statement?.id]);
  const selectedBookLines = (data?.book_lines ?? []).filter((item) => selectedBooks.includes(item.id));
  const selectedBankLines = (data?.statement_lines ?? []).filter((item) => selectedBank.includes(item.id));
  const bookNet = selectedBookLines.reduce((sum, item) => sum + Number(item.debit) - Number(item.credit), 0);
  const bankAsBook = selectedBankLines.reduce(
    (sum, item) => sum + Number(item.bank_credit) - Number(item.bank_debit),
    0,
  );
  const canPoint =
    selectedBooks.length > 0 && selectedBank.length > 0 && Math.abs(bookNet - bankAsBook) < 0.5;
  const pointHint =
    selectedBooks.length === 0 || selectedBank.length === 0
      ? "Cochez une écriture 52 et la ligne correspondante du relevé."
      : !canPoint
        ? "Les montants ne correspondent pas. Un débit livre se pointe avec un crédit relevé."
        : "Sélection équilibrée — vous pouvez pointer.";

  const onError = (err: unknown) => {
    setInfo("");
    setError(err instanceof ApiError ? err.message : "Action impossible.");
  };

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["bank-recon"] });
    queryClient.invalidateQueries({ queryKey: ["cash-panel"] });
    queryClient.invalidateQueries({ queryKey: ["statements"] });
    setSelectedBooks([]);
    setSelectedBank([]);
    setError("");
  };

  const saveStatement = useMutation({
    mutationFn: () =>
      api("/api/ledger/bank/statements", {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({
          account_id: activeAccountId || null,
          statement_date: statementDate,
          bank_balance: bankBalance || "0",
        }),
      }),
    onSuccess: invalidate,
    onError,
  });

  const addLine = useMutation({
    mutationFn: () => {
      const statementId = data?.statement?.id;
      if (!statementId) {
        throw new ApiError("Enregistrez d’abord le relevé.", 400);
      }
      return api(`/api/ledger/bank/statements/${statementId}/lines`, {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({
          line_date: lineDate,
          label: lineLabel,
          bank_debit: lineDebit || "0",
          bank_credit: lineCredit || "0",
        }),
      });
    },
    onSuccess: () => {
      setLineLabel("");
      setLineDebit("");
      setLineCredit("");
      invalidate();
    },
    onError,
  });

  const ofx = useMutation({
    mutationFn: (file: File) => {
      const body = new FormData();
      body.append("file", file);
      const query = activeAccountId ? `?account_id=${activeAccountId}` : "";
      return api<OfxImport>(`/api/ledger/bank/ofx${query}`, {
        method: "POST",
        body,
        orgSlug,
        companyId,
      });
    },
    onSuccess: (result) => {
      invalidate();
      setError("");
      setInfo(
        `${result.created} ligne(s) importée(s)` +
          (result.skipped ? `, ${result.skipped} déjà présente(s)` : "") +
          ".",
      );
    },
    onError,
  });

  const point = useMutation({
    mutationFn: () =>
      api("/api/ledger/bank/pointage", {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({ book_ids: selectedBooks, statement_ids: selectedBank }),
      }),
    onSuccess: invalidate,
    onError,
  });

  const saveCount = useMutation({
    mutationFn: () =>
      api<CashCount>("/api/ledger/cash", {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({
          account_id: cashAccountId || cash.data?.account_id || null,
          counted_on: countedOn,
          physical_amount: physicalAmount || "0",
          notes: cashNotes,
        }),
      }),
    onSuccess: (result) => {
      invalidate();
      setInfo(
        result.variance_kind === "balanced"
          ? "Caisse conforme."
          : result.variance_kind === "shortage"
            ? `Manquant ${formatMoney(result.variance.replace("-", ""), currency)} — 6588.`
            : `Surplus ${formatMoney(result.variance, currency)} — 7588.`,
      );
    },
    onError,
  });

  const postGap = useMutation({
    mutationFn: () => {
      const countId = cash.data?.count?.id;
      if (!countId) {
        throw new ApiError("Enregistrez d’abord le contrôle.", 400);
      }
      return api<CashCount>(`/api/ledger/cash/${countId}/variance`, {
        method: "POST",
        orgSlug,
        companyId,
      });
    },
    onSuccess: (result) => {
      invalidate();
      setInfo(`Écart comptabilisé${result.entry_number ? ` (${result.entry_number})` : ""}.`);
    },
    onError,
  });

  const toggle = (id: string, list: string[], setList: (next: string[]) => void) => {
    setList(list.includes(id) ? list.filter((item) => item !== id) : [...list, id]);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl">Trésorerie</h1>
        <p className="text-sm text-muted-foreground">
          {tab === "bank"
            ? "Rapprochement du 52/53 avec le relevé (saisie ou OFX). Les écritures non pointées alimentent la note 11."
            : "Contrôle physique du 57. Un manquant passe en 6588, un surplus en 7588, journal CA."}
        </p>
        <div className="mt-4 flex gap-2">
          <Button
            type="button"
            variant={tab === "bank" ? "default" : "outline"}
            onClick={() => {
              setTab("bank");
              setError("");
              setInfo("");
            }}
          >
            Banque 52/53
          </Button>
          <Button
            type="button"
            variant={tab === "cash" ? "default" : "outline"}
            onClick={() => {
              setTab("cash");
              setError("");
              setInfo("");
            }}
          >
            Caisse 57
          </Button>
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {info && <p className="text-sm text-primary">{info}</p>}

      {tab === "bank" && (
      <>
      <Card>
        <CardHeader>
          <CardTitle>Relevé</CardTitle>
          <CardDescription>
            Solde du relevé en notre faveur (positif = argent disponible, comme un 52 débiteur).
            L’OFX crée le relevé et ses lignes ; un second import ignore les FITID déjà vus.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-1.5">
            <Label>Compte banque</Label>
            <select
              className={SELECT_CLASS}
              value={activeAccountId}
              onChange={(event) => {
                setAccountId(event.target.value);
                setSelectedBooks([]);
                setSelectedBank([]);
              }}
            >
              {banks.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.code} {account.label}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label>Date du relevé</Label>
            <Input type="date" value={statementDate} onChange={(event) => setStatementDate(event.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>Solde relevé</Label>
            <Input value={bankBalance} onChange={(event) => setBankBalance(event.target.value)} placeholder="0" />
          </div>
          {canWrite && (
            <div className="flex flex-wrap items-end gap-2 self-end">
              <Button onClick={() => saveStatement.mutate()} disabled={saveStatement.isPending}>
                {saveStatement.isPending ? "Enregistrement…" : "Enregistrer le relevé"}
              </Button>
              <input
                ref={ofxRef}
                type="file"
                accept=".ofx,.qfx,.OFX,.QFX"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) ofx.mutate(file);
                  event.target.value = "";
                }}
              />
              <Button
                type="button"
                variant="outline"
                disabled={ofx.isPending}
                onClick={() => ofxRef.current?.click()}
              >
                {ofx.isPending ? "Import OFX…" : "Importer un OFX"}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-3 sm:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Solde comptable</CardTitle>
          </CardHeader>
          <CardContent className="font-mono text-lg">
            {formatMoney(data?.book_balance ?? "0", currency)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Solde relevé</CardTitle>
          </CardHeader>
          <CardContent className="font-mono text-lg">
            {formatMoney(data?.bank_balance ?? "0", currency)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Contrôle</CardTitle>
            <CardDescription>Doit être 0 si tout ce qui reste explique l’écart.</CardDescription>
          </CardHeader>
          <CardContent className="font-mono text-lg">
            {formatMoney(data?.control ?? "0", currency)}
          </CardContent>
        </Card>
      </div>

      {canWrite && data?.statement && (
        <Card>
          <CardHeader>
            <CardTitle>Ligne du relevé</CardTitle>
            <CardDescription>
              Débit banque = sortie (crédit 52). Crédit banque = entrée (débit 52).
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <div className="space-y-1.5">
              <Label>Date</Label>
              <Input type="date" value={lineDate} onChange={(event) => setLineDate(event.target.value)} />
            </div>
            <div className="space-y-1.5 lg:col-span-2">
              <Label>Libellé</Label>
              <Input value={lineLabel} onChange={(event) => setLineLabel(event.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Débit banque</Label>
              <Input value={lineDebit} onChange={(event) => setLineDebit(event.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Crédit banque</Label>
              <Input value={lineCredit} onChange={(event) => setLineCredit(event.target.value)} />
            </div>
            <div className="self-end lg:col-span-5">
              <Button onClick={() => addLine.mutate()} disabled={addLine.isPending || !lineLabel}>
                {addLine.isPending ? "Ajout…" : "Ajouter la ligne"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Écritures non pointées</CardTitle>
            <CardDescription>Journal, compte {data?.account_code ?? "52"}.</CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-muted-foreground">
                <tr>
                  <th className="w-8 px-2 py-2" />
                  <th className="px-2 py-2">Date</th>
                  <th className="px-2 py-2">Pièce</th>
                  <th className="px-2 py-2">Libellé</th>
                  <th className="px-2 py-2 text-right">Débit</th>
                  <th className="px-2 py-2 text-right">Crédit</th>
                </tr>
              </thead>
              <tbody>
                {(data?.book_lines ?? []).map((item) => (
                  <tr key={item.id} className="border-t border-border">
                    <td className="px-2 py-2">
                      <input
                        type="checkbox"
                        checked={selectedBooks.includes(item.id)}
                        onChange={() => toggle(item.id, selectedBooks, setSelectedBooks)}
                      />
                    </td>
                    <td className="px-2 py-2 whitespace-nowrap">{item.accounting_date}</td>
                    <td className="px-2 py-2 font-mono text-xs">{item.entry_number}</td>
                    <td className="px-2 py-2">{item.label}</td>
                    <td className="px-2 py-2 text-right font-mono">{formatMoney(item.debit, currency)}</td>
                    <td className="px-2 py-2 text-right font-mono">{formatMoney(item.credit, currency)}</td>
                  </tr>
                ))}
                {(data?.book_lines ?? []).length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-2 py-6 text-center text-muted-foreground">
                      Aucune écriture 52 à pointer.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Relevé non pointé</CardTitle>
            <CardDescription>
              {data?.statement
                ? `Relevé du ${data.statement.statement_date}`
                : "Enregistrez un relevé pour saisir les lignes."}
            </CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-muted-foreground">
                <tr>
                  <th className="w-8 px-2 py-2" />
                  <th className="px-2 py-2">Date</th>
                  <th className="px-2 py-2">Libellé</th>
                  <th className="px-2 py-2 text-right">Débit BQ</th>
                  <th className="px-2 py-2 text-right">Crédit BQ</th>
                </tr>
              </thead>
              <tbody>
                {(data?.statement_lines ?? []).map((item) => (
                  <tr key={item.id} className="border-t border-border">
                    <td className="px-2 py-2">
                      <input
                        type="checkbox"
                        checked={selectedBank.includes(item.id)}
                        onChange={() => toggle(item.id, selectedBank, setSelectedBank)}
                      />
                    </td>
                    <td className="px-2 py-2 whitespace-nowrap">{item.line_date}</td>
                    <td className="px-2 py-2">{item.label}</td>
                    <td className="px-2 py-2 text-right font-mono">{formatMoney(item.bank_debit, currency)}</td>
                    <td className="px-2 py-2 text-right font-mono">{formatMoney(item.bank_credit, currency)}</td>
                  </tr>
                ))}
                {(data?.statement_lines ?? []).length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-2 py-6 text-center text-muted-foreground">
                      Aucune ligne de relevé ouverte.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>

      {canWrite && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className={`text-sm ${canPoint ? "text-primary" : "text-muted-foreground"}`}>{pointHint}</p>
          <Button disabled={!canPoint || point.isPending} onClick={() => point.mutate()}>
            {point.isPending ? "Pointage…" : "Pointer la sélection"}
          </Button>
        </div>
      )}
      </>
      )}

      {tab === "cash" && (
        <CashPanelView
          canWrite={canWrite}
          currency={currency}
          tills={tills}
          data={cash.data}
          cashAccountId={cashAccountId || cash.data?.account_id || ""}
          countedOn={countedOn}
          physicalAmount={physicalAmount}
          cashNotes={cashNotes}
          saving={saveCount.isPending}
          posting={postGap.isPending}
          onAccount={(value) => setCashAccountId(value)}
          onDate={setCountedOn}
          onPhysical={setPhysicalAmount}
          onNotes={setCashNotes}
          onSave={() => saveCount.mutate()}
          onPost={() => postGap.mutate()}
        />
      )}
    </div>
  );
}

function CashPanelView({
  canWrite,
  currency,
  tills,
  data,
  cashAccountId,
  countedOn,
  physicalAmount,
  cashNotes,
  saving,
  posting,
  onAccount,
  onDate,
  onPhysical,
  onNotes,
  onSave,
  onPost,
}: {
  canWrite: boolean;
  currency: string;
  tills: LedgerAccount[];
  data: CashPanel | undefined;
  cashAccountId: string;
  countedOn: string;
  physicalAmount: string;
  cashNotes: string;
  saving: boolean;
  posting: boolean;
  onAccount: (value: string) => void;
  onDate: (value: string) => void;
  onPhysical: (value: string) => void;
  onNotes: (value: string) => void;
  onSave: () => void;
  onPost: () => void;
}) {
  const count = data?.count;
  const kind = count?.variance_kind ?? "";
  const canPost = Boolean(canWrite && count && kind !== "balanced" && !count.entry_id);
  const gapLabel =
    kind === "shortage" ? "Manquant" : kind === "overage" ? "Surplus" : "Écart";

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Contrôle de caisse</CardTitle>
          <CardDescription>
            Comptez les espèces et comparez au solde du 57. Le manquant (6588) diminue la caisse ;
            le surplus (7588) l’augmente. Journal CA.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-1.5">
            <Label>Compte caisse</Label>
            <select
              className={SELECT_CLASS}
              value={cashAccountId}
              onChange={(event) => onAccount(event.target.value)}
            >
              {tills.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.code} {account.label}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label>Date du contrôle</Label>
            <Input type="date" value={countedOn} onChange={(event) => onDate(event.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>Espèces comptées</Label>
            <Input value={physicalAmount} onChange={(event) => onPhysical(event.target.value)} placeholder="0" />
          </div>
          <div className="space-y-1.5">
            <Label>Observation</Label>
            <Input value={cashNotes} onChange={(event) => onNotes(event.target.value)} />
          </div>
          {canWrite && (
            <div className="flex flex-wrap items-end gap-2 self-end lg:col-span-4">
              <Button onClick={onSave} disabled={saving}>
                {saving ? "Enregistrement…" : "Enregistrer le contrôle"}
              </Button>
              {canPost && (
                <Button type="button" variant="outline" onClick={onPost} disabled={posting}>
                  {posting ? "Comptabilisation…" : `Comptabiliser l’écart (${count?.contra_code})`}
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-3 sm:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Solde comptable</CardTitle>
          </CardHeader>
          <CardContent className="font-mono text-lg">
            {formatMoney(data?.book_balance ?? "0", currency)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Espèces</CardTitle>
          </CardHeader>
          <CardContent className="font-mono text-lg">
            {formatMoney(count?.physical_amount ?? "0", currency)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{gapLabel}</CardTitle>
            <CardDescription>
              {count?.entry_number
                ? `Comptabilisé ${count.entry_number}`
                : kind === "balanced"
                  ? "Doit être 0."
                  : count
                    ? `À passer en ${count.contra_code}`
                    : "Enregistrez un contrôle."}
            </CardDescription>
          </CardHeader>
          <CardContent className="font-mono text-lg">
            {formatMoney(count?.variance ?? "0", currency)}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Livre de caisse</CardTitle>
            <CardDescription>Dernières écritures {data?.account_code ?? "57"}.</CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-muted-foreground">
                <tr>
                  <th className="px-2 py-2">Date</th>
                  <th className="px-2 py-2">Pièce</th>
                  <th className="px-2 py-2">Libellé</th>
                  <th className="px-2 py-2 text-right">Débit</th>
                  <th className="px-2 py-2 text-right">Crédit</th>
                </tr>
              </thead>
              <tbody>
                {(data?.book_lines ?? []).map((item) => (
                  <tr key={item.id} className="border-t border-border">
                    <td className="px-2 py-2 whitespace-nowrap">{item.accounting_date}</td>
                    <td className="px-2 py-2 font-mono text-xs">{item.entry_number}</td>
                    <td className="px-2 py-2">{item.label}</td>
                    <td className="px-2 py-2 text-right font-mono">{formatMoney(item.debit, currency)}</td>
                    <td className="px-2 py-2 text-right font-mono">{formatMoney(item.credit, currency)}</td>
                  </tr>
                ))}
                {(data?.book_lines ?? []).length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-2 py-6 text-center text-muted-foreground">
                      Aucun mouvement de caisse.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Historique des contrôles</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-muted-foreground">
                <tr>
                  <th className="px-2 py-2">Date</th>
                  <th className="px-2 py-2 text-right">Espèces</th>
                  <th className="px-2 py-2 text-right">Livre</th>
                  <th className="px-2 py-2 text-right">Écart</th>
                  <th className="px-2 py-2">Pièce</th>
                </tr>
              </thead>
              <tbody>
                {(data?.counts ?? []).map((item) => (
                  <tr key={item.id} className="border-t border-border">
                    <td className="px-2 py-2 whitespace-nowrap">{item.counted_on}</td>
                    <td className="px-2 py-2 text-right font-mono">{formatMoney(item.physical_amount, currency)}</td>
                    <td className="px-2 py-2 text-right font-mono">{formatMoney(item.book_amount, currency)}</td>
                    <td className="px-2 py-2 text-right font-mono">{formatMoney(item.variance, currency)}</td>
                    <td className="px-2 py-2 font-mono text-xs">{item.entry_number || "—"}</td>
                  </tr>
                ))}
                {(data?.counts ?? []).length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-2 py-6 text-center text-muted-foreground">
                      Aucun contrôle enregistré.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
