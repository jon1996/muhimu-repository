"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { useTenant } from "@/components/tenant-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import type { LedgerAccount, OpenItem, ThirdParty } from "@/lib/types";

const SELECT_CLASS = "h-10 w-full rounded-md border border-input bg-background px-3 text-sm";

const BUCKET_LABEL: Record<string, string> = {
  overdue: "échu",
  within_year: "≤ 1 an",
  beyond_year: "> 1 an",
};

export default function PartiesPage() {
  const { orgSlug, companyId, activeCompany, membership } = useTenant();
  const canWrite = ["owner", "admin", "accountant"].includes(membership?.role ?? "");
  const currency = activeCompany?.currency_code ?? "XOF";
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [kind, setKind] = useState("customer");
  const [taxId, setTaxId] = useState("");
  const [accountId, setAccountId] = useState("");
  const [partyId, setPartyId] = useState("");
  const [selected, setSelected] = useState<string[]>([]);

  const parties = useQuery({
    queryKey: ["parties", orgSlug, companyId],
    queryFn: () => api<ThirdParty[]>("/api/ledger/parties", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const accounts = useQuery({
    queryKey: ["accounts", orgSlug, companyId],
    queryFn: () => api<LedgerAccount[]>("/api/ledger/accounts?postable=true", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const openItems = useQuery({
    queryKey: ["open-items", orgSlug, companyId, partyId],
    queryFn: () =>
      api<OpenItem[]>(`/api/ledger/parties/open${partyId ? `?party_id=${partyId}` : ""}`, {
        orgSlug,
        companyId,
      }),
    enabled: Boolean(orgSlug && companyId),
  });

  const class4 = useMemo(
    () => (accounts.data ?? []).filter((account) => account.account_class === "4"),
    [accounts.data],
  );

  const selectedLines = (openItems.data ?? []).filter((item) => selected.includes(item.id));
  const selectedDebit = selectedLines.reduce((sum, item) => sum + Number(item.debit), 0);
  const selectedCredit = selectedLines.reduce((sum, item) => sum + Number(item.credit), 0);
  const selectedNet = selectedDebit - selectedCredit;
  const roots = new Set(selectedLines.map((item) => item.account_code.slice(0, 3)));
  const canLetter = selected.length >= 2 && roots.size === 1 && Math.abs(selectedNet) < 0.5;
  const letterHint =
    selected.length < 2
      ? "Cochez au moins la facture et le règlement."
      : roots.size > 1
        ? `Comptes incompatibles (${[...new Set(selectedLines.map((item) => item.account_code))].join(", ")}). Lettrez 411 avec 411x, ou 401 avec 401x.`
        : Math.abs(selectedNet) >= 0.5
          ? "Les montants ne s’annulent pas. Cochez un débit et un crédit du même montant (un crédit négatif n’annule pas un débit)."
          : "Sélection équilibrée — vous pouvez lettrer.";

  const onError = (err: unknown) => {
    setError(err instanceof ApiError ? err.message : "Action impossible.");
  };

  const create = useMutation({
    mutationFn: () =>
      api<ThirdParty>("/api/ledger/parties", {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({
          name,
          kind,
          tax_id: taxId,
          account_id: accountId || null,
        }),
      }),
    onSuccess: () => {
      setName("");
      setTaxId("");
      setError("");
      queryClient.invalidateQueries({ queryKey: ["parties"] });
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      queryClient.invalidateQueries({ queryKey: ["accounts-postable"] });
    },
    onError,
  });

  const saveDue = useMutation({
    mutationFn: ({ id, due_on }: { id: string; due_on: string }) =>
      api(`/api/ledger/lines/${id}/due`, {
        method: "PATCH",
        orgSlug,
        companyId,
        body: JSON.stringify({ due_on }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["open-items"] });
      queryClient.invalidateQueries({ queryKey: ["statements"] });
      queryClient.invalidateQueries({ queryKey: ["entry"] });
    },
    onError,
  });

  const letter = useMutation({
    mutationFn: () =>
      api("/api/ledger/lettering", {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({ line_ids: selected }),
      }),
    onSuccess: () => {
      setSelected([]);
      setError("");
      queryClient.invalidateQueries({ queryKey: ["open-items"] });
      queryClient.invalidateQueries({ queryKey: ["statements"] });
    },
    onError,
  });

  const toggle = (id: string) => {
    setSelected((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl">Tiers</h1>
        <p className="mt-1 max-w-2xl text-muted-foreground">
          Fiches clients / fournisseurs (classe 4) et lettrage des échéances. Chaque fiche
          ouvre un compte auxiliaire (411-… / 401-…). Les soldes non lettrés alimentent
          les notes 7 et 17.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {canWrite && (
        <Card>
          <CardHeader>
            <CardTitle>Nouvelle fiche</CardTitle>
            <CardDescription>
              Un compte 411-… (client) ou 401-… (fournisseur) est créé automatiquement.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2 lg:grid-cols-5">
            <div className="space-y-1.5 lg:col-span-2">
              <Label>Nom</Label>
              <Input value={name} onChange={(event) => setName(event.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Type</Label>
              <select className={SELECT_CLASS} value={kind} onChange={(event) => setKind(event.target.value)}>
                <option value="customer">Client</option>
                <option value="supplier">Fournisseur</option>
                <option value="both">Les deux</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>Compte</Label>
              <select className={SELECT_CLASS} value={accountId} onChange={(event) => setAccountId(event.target.value)}>
                <option value="">Défaut (411 / 401)</option>
                {class4.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.code} · {account.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>NIF</Label>
              <Input value={taxId} onChange={(event) => setTaxId(event.target.value)} />
            </div>
            <Button className="self-end" disabled={!name.trim() || create.isPending} onClick={() => create.mutate()}>
              {create.isPending ? "Enregistrement…" : "Ajouter"}
            </Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Fiches</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button size="sm" variant={partyId === "" ? "default" : "outline"} onClick={() => setPartyId("")}>
            Tous les non lettrés
          </Button>
          {(parties.data ?? []).map((party) => (
            <Button
              key={party.id}
              size="sm"
              variant={partyId === party.id ? "default" : "outline"}
              onClick={() => {
                setPartyId(party.id);
                setSelected([]);
              }}
            >
              {party.reference} · {party.name}
              <Badge className="ml-2">{party.kind_label}</Badge>
            </Button>
          ))}
          {(parties.data ?? []).length === 0 && (
            <p className="text-sm text-muted-foreground">Aucun tiers. Créez une fiche ci-dessus.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Échéances non lettrées</CardTitle>
          <CardDescription>
            Cochez une facture et son règlement (même famille 411/401, montants qui s’annulent).
            Le tiers se choisit dans la colonne Tiers de la pièce. L’échéance (échu / ≤ 1 an /
            &gt; 1 an) alimente les notes 7 et 17 ; sans date, le cycle d’exploitation (≤ 1 an)
            est retenu.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-left text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 w-10" />
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2">Échéance</th>
                  <th className="px-3 py-2">Pièce</th>
                  <th className="px-3 py-2">Compte</th>
                  <th className="px-3 py-2">Tiers</th>
                  <th className="px-3 py-2">Libellé</th>
                  <th className="px-3 py-2 text-right">Débit</th>
                  <th className="px-3 py-2 text-right">Crédit</th>
                </tr>
              </thead>
              <tbody>
                {(openItems.data ?? []).map((item) => (
                  <tr
                    key={item.id}
                    className={`border-t border-border ${item.bucket === "overdue" ? "bg-destructive/5" : ""}`}
                  >
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={selected.includes(item.id)}
                        onChange={() => toggle(item.id)}
                      />
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">{item.accounting_date}</td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      {canWrite ? (
                        <Input
                          type="date"
                          className="h-8 w-[148px]"
                          defaultValue={item.due_on}
                          onBlur={(event) => {
                            const next = event.target.value;
                            if (next === (item.due_on || "")) return;
                            saveDue.mutate({ id: item.id, due_on: next });
                          }}
                        />
                      ) : (
                        <span className={item.bucket === "overdue" ? "font-medium text-destructive" : ""}>
                          {item.due_on || "—"}
                        </span>
                      )}
                      {item.bucket ? (
                        <span className="ml-1 text-xs text-muted-foreground">
                          {BUCKET_LABEL[item.bucket] ?? item.bucket}
                        </span>
                      ) : null}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{item.entry_number}</td>
                    <td className="px-3 py-2">{item.account_code}</td>
                    <td className="px-3 py-2">{item.third_party_name || "—"}</td>
                    <td className="px-3 py-2">{item.label}</td>
                    <td className="px-3 py-2 text-right font-mono">{formatMoney(item.debit, currency)}</td>
                    <td className="px-3 py-2 text-right font-mono">{formatMoney(item.credit, currency)}</td>
                  </tr>
                ))}
                {(openItems.data ?? []).length === 0 && (
                  <tr>
                    <td colSpan={9} className="px-3 py-6 text-center text-muted-foreground">
                      Aucune échéance ouverte. Imputez un tiers sur une écriture validée du journal.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {canWrite && (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className={`text-sm ${canLetter ? "text-primary" : "text-muted-foreground"}`}>
                {selected.length
                  ? `${letterHint} · débit ${formatMoney(selectedDebit, currency)} · crédit ${formatMoney(selectedCredit, currency)}`
                  : letterHint}
              </p>
              <Button disabled={!canLetter || letter.isPending} onClick={() => letter.mutate()}>
                {letter.isPending ? "Lettrage…" : "Lettrer la sélection"}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
