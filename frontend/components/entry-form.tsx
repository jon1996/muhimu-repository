"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { useBetaScope } from "@/components/beta-scope-context";
import { useTenant } from "@/components/tenant-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { localTodayIso } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { FX_CURRENCY_CHOICES } from "@/lib/ohada";
import type { CagePanel, EscomptePreview, FxRate, JournalEntry, LedgerAccount, LedgerJournal, ThirdParty } from "@/lib/types";

type LineDraft = {
  id: string;
  account_id: string;
  debit: string;
  credit: string;
  label: string;
  third_party_id: string;
  due_on: string;
  cage_section_id: string;
  currency_code: string;
  fx_rate: string;
};

const emptyLine = (currency = ""): LineDraft => ({
  id: "",
  account_id: "",
  debit: "",
  credit: "",
  label: "",
  third_party_id: "",
  due_on: "",
  cage_section_id: "",
  currency_code: currency,
  fx_rate: "",
});

type Props = {
  initial?: JournalEntry;
};

export function EntryForm({ initial }: Props) {
  const { orgSlug, companyId, activeCompany } = useTenant();
  const betaScope = useBetaScope();
  const router = useRouter();
  const queryClient = useQueryClient();
  const currency = activeCompany?.currency_code ?? "XOF";

  const journals = useQuery({
    queryKey: ["journals", orgSlug, companyId],
    queryFn: () => api<LedgerJournal[]>("/api/ledger/journals", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const accounts = useQuery({
    queryKey: ["accounts-postable", orgSlug, companyId],
    queryFn: () => api<LedgerAccount[]>("/api/ledger/accounts?postable=true", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const parties = useQuery({
    queryKey: ["parties", orgSlug, companyId],
    queryFn: () => api<ThirdParty[]>("/api/ledger/parties", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const cage = useQuery({
    queryKey: ["cage", orgSlug, companyId],
    queryFn: () => api<CagePanel>("/api/ledger/cage", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId && betaScope.class9_cage),
  });
  const fxRates = useQuery({
    queryKey: ["fx-rates", orgSlug, companyId],
    queryFn: () => api<FxRate[]>("/api/ledger/fx-rates", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });

  const [journalId, setJournalId] = useState(initial?.journal_id ?? "");
  const [accountingDate, setAccountingDate] = useState(initial?.accounting_date ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [documentRef, setDocumentRef] = useState(initial?.document_ref ?? "");
  const [showDiscount, setShowDiscount] = useState(false);
  const [nominal, setNominal] = useState("");
  const [agios, setAgios] = useState("");
  const [effectDue, setEffectDue] = useState("");
  const [campaign, setCampaign] = useState(false);
  const [bankAccountId, setBankAccountId] = useState("");
  const [sourceAccountId, setSourceAccountId] = useState("");
  const [discountPartyId, setDiscountPartyId] = useState("");
  const [lines, setLines] = useState<LineDraft[]>(
    initial?.lines.map((line) => {
      const fx = Boolean(
        line.currency_code && line.currency_code !== currency && Number(line.foreign_amount),
      );
      const useForeign = fx && initial.status !== "posted";
      const debitSide = Number(line.debit) !== 0;
      return {
        id: line.id,
        account_id: line.account_id,
        debit: useForeign
          ? debitSide
            ? String(Math.abs(Number(line.foreign_amount)))
            : ""
          : line.debit === "0.00" || line.debit === "0"
            ? ""
            : line.debit,
        credit: useForeign
          ? !debitSide
            ? String(Math.abs(Number(line.foreign_amount)))
            : ""
          : line.credit === "0.00" || line.credit === "0"
            ? ""
            : line.credit,
        label: line.label,
        third_party_id: line.third_party_id ?? "",
        due_on: line.due_on ?? "",
        cage_section_id: line.cage_section_id ?? "",
        currency_code: line.currency_code || currency,
        fx_rate:
          fx && line.fx_rate && line.fx_rate !== "1" && Number(line.fx_rate) !== 1
            ? line.fx_rate
            : "",
      };
    }) ?? [emptyLine(currency), emptyLine(currency)],
  );

  useEffect(() => {
    if (initial?.accounting_date) return;
    setAccountingDate((current) => current || localTodayIso());
  }, [initial?.accounting_date]);

  const lookupRate = (ccy: string, on: string) => {
    const rows = (fxRates.data ?? [])
      .filter((row) => row.currency_code === ccy && (!on || row.rate_date <= on))
      .sort((a, b) => b.rate_date.localeCompare(a.rate_date));
    return rows[0]?.rate ?? "";
  };

  const totals = useMemo(() => {
    const convert = (line: LineDraft, amount: number) => {
      const code = (line.currency_code || currency).toUpperCase();
      if (!amount || code === currency.toUpperCase()) return amount;
      const rate = Number(String(line.fx_rate || lookupRate(code, accountingDate)).replace(",", "."));
      return rate ? amount * rate : amount;
    };
    const debit = lines.reduce((sum, line) => sum + convert(line, Number(line.debit || 0)), 0);
    const credit = lines.reduce((sum, line) => sum + convert(line, Number(line.credit || 0)), 0);
    const rounded = currency === "XOF" || currency === "XAF";
    const d = rounded ? Math.round(debit) : Math.round(debit * 100) / 100;
    const c = rounded ? Math.round(credit) : Math.round(credit * 100) / 100;
    return { debit: d, credit: c, balanced: d === c && d > 0 };
  }, [lines, currency, accountingDate, fxRates.data]);

  const payload = () => ({
    journal_id: journalId || journals.data?.[0]?.id,
    accounting_date: accountingDate,
    value_date: accountingDate,
    description,
    document_ref: documentRef,
    lines: lines
      .filter((line) => line.account_id && (line.debit || line.credit))
      .map((line) => ({
        account_id: line.account_id,
        debit: line.debit || "0",
        credit: line.credit || "0",
        label: line.label,
        third_party_id: line.third_party_id || null,
        due_on: line.due_on || "",
        cage_section_id: line.cage_section_id || null,
        currency_code: line.currency_code || currency,
        fx_rate: line.fx_rate || "",
      })),
  });

  const save = useMutation({
    mutationFn: () => {
      const body = JSON.stringify(payload());
      if (initial) {
        return api<JournalEntry>(`/api/ledger/entries/${initial.id}`, {
          method: "PUT",
          body,
          orgSlug,
          companyId,
        });
      }
      return api<JournalEntry>("/api/ledger/entries", {
        method: "POST",
        body,
        orgSlug,
        companyId,
      });
    },
    onSuccess: (entry) => {
      queryClient.invalidateQueries({ queryKey: ["entries"] });
      router.replace(`/app/${orgSlug}/journal/${entry.id}`);
    },
  });

  const post = useMutation({
    mutationFn: async () => {
      let entry = initial;
      if (!entry || entry.status === "draft") {
        const body = JSON.stringify(payload());
        entry = initial
          ? await api<JournalEntry>(`/api/ledger/entries/${initial.id}`, {
              method: "PUT",
              body,
              orgSlug,
              companyId,
            })
          : await api<JournalEntry>("/api/ledger/entries", {
              method: "POST",
              body,
              orgSlug,
              companyId,
            });
      }
      return api<JournalEntry>(`/api/ledger/entries/${entry.id}/post`, {
        method: "POST",
        orgSlug,
        companyId,
      });
    },
    onSuccess: (entry) => {
      queryClient.invalidateQueries({ queryKey: ["entries"] });
      queryClient.invalidateQueries({ queryKey: ["balance"] });
      queryClient.invalidateQueries({ queryKey: ["commitments"] });
      queryClient.invalidateQueries({ queryKey: ["statements"] });
      queryClient.invalidateQueries({ queryKey: ["cage"] });
      queryClient.invalidateQueries({ queryKey: ["class9"] });
      router.replace(`/app/${orgSlug}/journal/${entry.id}`);
    },
  });

  const saveDues = useMutation({
    mutationFn: async () => {
      const targets = lines.filter((line) => line.id);
      for (const line of targets) {
        await api(`/api/ledger/lines/${line.id}/due`, {
          method: "PATCH",
          orgSlug,
          companyId,
          body: JSON.stringify({ due_on: line.due_on || "" }),
        });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entry"] });
      queryClient.invalidateQueries({ queryKey: ["open-items"] });
      queryClient.invalidateQueries({ queryKey: ["statements"] });
    },
  });

  const locked = initial?.status === "posted";
  const error = (save.error || post.error || saveDues.error) as ApiError | undefined;
  const banks = useMemo(
    () => (accounts.data ?? []).filter((account) => account.code.startsWith("52") || account.code.startsWith("53")),
    [accounts.data],
  );
  const sources = useMemo(
    () => (accounts.data ?? []).filter((account) => account.code.startsWith("411") || account.code.startsWith("412")),
    [accounts.data],
  );
  const customers = useMemo(
    () => (parties.data ?? []).filter((party) => party.kind !== "supplier"),
    [parties.data],
  );
  const cageSections = useMemo(
    () => (cage.data?.sections ?? []).filter((section) => section.is_active),
    [cage.data],
  );

  const fillDiscount = useMutation({
    mutationFn: () =>
      api<EscomptePreview>("/api/ledger/escompte/preview", {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({
          nominal,
          agios: agios || "0",
          due_on: effectDue,
          campaign,
          bank_account_id: bankAccountId || null,
          source_account_id: sourceAccountId || null,
          third_party_id: discountPartyId || null,
          label: description || "Escompte d’effet",
        }),
      }),
    onSuccess: (preview) => {
      if (preview.journal_id) setJournalId(preview.journal_id);
      if (preview.description && !description) setDescription(preview.description);
      setLines(
        preview.lines.map((line) => ({
          id: "",
          account_id: line.account_id,
          debit: line.debit === "0" ? "" : line.debit,
          credit: line.credit === "0" ? "" : line.credit,
          label: line.label,
          third_party_id: line.third_party_id ?? "",
          due_on: line.due_on,
          cage_section_id: "",
          currency_code: "",
          fx_rate: "",
        })),
      );
    },
  });
  const helperError = fillDiscount.error instanceof ApiError ? fillDiscount.error : undefined;

  return (
    <form
      className="space-y-6"
      onSubmit={(event) => {
        event.preventDefault();
        save.mutate();
      }}
    >
      <div className="grid gap-4 md:grid-cols-4">
        <div className="space-y-2">
          <Label>Journal</Label>
          <select
            className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
            value={journalId || journals.data?.[0]?.id || ""}
            disabled={locked}
            onChange={(event) => setJournalId(event.target.value)}
          >
            {(journals.data ?? []).map((journal) => (
              <option key={journal.id} value={journal.id}>
                {journal.code} — {journal.name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <Label>Date comptable</Label>
          <Input
            type="date"
            value={accountingDate}
            disabled={locked}
            onChange={(event) => setAccountingDate(event.target.value)}
          />
        </div>
        <div className="space-y-2 md:col-span-2">
          <Label>Libellé</Label>
          <Input
            value={description}
            disabled={locked}
            onChange={(event) => setDescription(event.target.value)}
            required
          />
        </div>
        <div className="space-y-2 md:col-span-2">
          <Label>Pièce justificative</Label>
          <Input
            value={documentRef}
            disabled={locked}
            onChange={(event) => setDocumentRef(event.target.value)}
            placeholder="N° facture, reçu…"
          />
        </div>
      </div>

      {!locked && betaScope.escompte && (
        <div className="rounded-xl border border-border p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-sm font-medium">Escompte d’effet</p>
              <p className="text-xs text-muted-foreground">
                415 + banque + 6745 + 564/565. L’engagement (note 1) est créé à la validation.
              </p>
            </div>
            <Button type="button" variant="outline" size="sm" onClick={() => setShowDiscount((open) => !open)}>
              {showDiscount ? "Masquer" : "Préparer"}
            </Button>
          </div>
          {showDiscount && (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="space-y-1.5">
                <Label>Nominal</Label>
                <Input value={nominal} onChange={(event) => setNominal(event.target.value)} placeholder="0" />
              </div>
              <div className="space-y-1.5">
                <Label>Agios (6745)</Label>
                <Input value={agios} onChange={(event) => setAgios(event.target.value)} placeholder="0" />
              </div>
              <div className="space-y-1.5">
                <Label>Échéance de l’effet</Label>
                <Input type="date" value={effectDue} onChange={(event) => setEffectDue(event.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Client</Label>
                <select
                  className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                  value={discountPartyId}
                  onChange={(event) => setDiscountPartyId(event.target.value)}
                >
                  <option value="">—</option>
                  {customers.map((party) => (
                    <option key={party.id} value={party.id}>
                      {party.reference} {party.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label>Banque</Label>
                <select
                  className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                  value={bankAccountId}
                  onChange={(event) => setBankAccountId(event.target.value)}
                >
                  <option value="">52 / 53 automatique</option>
                  {banks.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.code} {account.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label>Origine (411/412)</Label>
                <select
                  className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                  value={sourceAccountId}
                  onChange={(event) => setSourceAccountId(event.target.value)}
                >
                  <option value="">412 puis 411</option>
                  {sources.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.code} {account.label}
                    </option>
                  ))}
                </select>
              </div>
              <label className="flex items-center gap-2 self-end pb-2 text-sm">
                <input type="checkbox" checked={campaign} onChange={(event) => setCampaign(event.target.checked)} />
                Crédit de campagne (564)
              </label>
              <div className="self-end">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={fillDiscount.isPending || !nominal}
                  onClick={() => fillDiscount.mutate()}
                >
                  {fillDiscount.isPending ? "Préparation…" : "Remplir les lignes"}
                </Button>
              </div>
              {helperError && <p className="sm:col-span-2 lg:col-span-4 text-sm text-destructive">{helperError.message}</p>}
            </div>
          )}
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-left text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">Compte</th>
              <th className="px-3 py-2 font-medium">Tiers</th>
              {cageSections.length > 0 && <th className="px-3 py-2 font-medium">Section CAGE</th>}
              <th className="px-3 py-2 font-medium">Libellé ligne</th>
              <th className="px-3 py-2 font-medium">Échéance</th>
              <th className="px-3 py-2 font-medium">Devise</th>
              <th className="px-3 py-2 font-medium">Cours</th>
              <th className="px-3 py-2 font-medium text-right">Débit</th>
              <th className="px-3 py-2 font-medium text-right">Crédit</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {lines.map((line, index) => (
              <tr key={index} className="border-t border-border">
                <td className="px-3 py-2">
                  <select
                    className="h-9 w-full min-w-[220px] rounded-md border border-input bg-background px-2"
                    value={line.account_id}
                    disabled={locked}
                    onChange={(event) =>
                      setLines((current) =>
                        current.map((item, i) =>
                          i === index ? { ...item, account_id: event.target.value } : item,
                        ),
                      )
                    }
                  >
                    <option value="">Choisir…</option>
                    {(accounts.data ?? []).map((account) => (
                      <option key={account.id} value={account.id}>
                        {account.code} {account.label}
                      </option>
                    ))}
                    </select>
                </td>
                <td className="px-3 py-2">
                  <select
                    className="h-9 w-full min-w-[160px] rounded-md border border-input bg-background px-2"
                    value={line.third_party_id}
                    disabled={locked}
                    onChange={(event) =>
                      setLines((current) =>
                        current.map((item, i) =>
                          i === index ? { ...item, third_party_id: event.target.value } : item,
                        ),
                      )
                    }
                  >
                    <option value="">—</option>
                    {(parties.data ?? [])
                      .filter((party) => {
                        const account = (accounts.data ?? []).find((item) => item.id === line.account_id);
                        const code = account?.code ?? "";
                        if (code.startsWith("41")) return party.kind !== "supplier";
                        if (code.startsWith("40")) return party.kind !== "customer";
                        return true;
                      })
                      .map((party) => (
                        <option key={party.id} value={party.id}>
                          {party.reference} {party.name}
                        </option>
                      ))}
                  </select>
                </td>
                {cageSections.length > 0 && (
                  <td className="px-3 py-2">
                    <select
                      className="h-9 w-full min-w-[140px] rounded-md border border-input bg-background px-2"
                      value={line.cage_section_id}
                      disabled={locked}
                      onChange={(event) =>
                        setLines((current) =>
                          current.map((item, i) =>
                            i === index ? { ...item, cage_section_id: event.target.value } : item,
                          ),
                        )
                      }
                    >
                      <option value="">Défaut</option>
                      {cageSections.map((section) => (
                        <option key={section.id} value={section.id}>
                          {section.code} {section.label}
                        </option>
                      ))}
                    </select>
                  </td>
                )}
                <td className="px-3 py-2">
                  <Input
                    value={line.label}
                    disabled={locked}
                    onChange={(event) =>
                      setLines((current) =>
                        current.map((item, i) =>
                          i === index ? { ...item, label: event.target.value } : item,
                        ),
                      )
                    }
                  />
                </td>
                <td className="px-3 py-2">
                  <Input
                    type="date"
                    className="min-w-[140px]"
                    value={line.due_on}
                    onChange={(event) =>
                      setLines((current) =>
                        current.map((item, i) =>
                          i === index ? { ...item, due_on: event.target.value } : item,
                        ),
                      )
                    }
                  />
                </td>
                <td className="px-3 py-2">
                  <select
                    className="h-9 w-[88px] rounded-md border border-input bg-background px-2"
                    value={line.currency_code || currency}
                    disabled={locked}
                    onChange={(event) => {
                      const next = event.target.value;
                      setLines((current) =>
                        current.map((item, i) =>
                          i === index
                            ? {
                                ...item,
                                currency_code: next,
                                fx_rate:
                                  next === currency
                                    ? ""
                                    : item.fx_rate || lookupRate(next, accountingDate),
                              }
                            : item,
                        ),
                      );
                    }}
                  >
                    <option value={currency}>{currency}</option>
                    {FX_CURRENCY_CHOICES.filter((code) => code !== currency).map((code) => (
                      <option key={code} value={code}>
                        {code}
                      </option>
                    ))}
                    {line.currency_code &&
                      line.currency_code !== currency &&
                      !FX_CURRENCY_CHOICES.includes(
                        line.currency_code as (typeof FX_CURRENCY_CHOICES)[number],
                      ) && (
                        <option value={line.currency_code}>{line.currency_code}</option>
                      )}
                  </select>
                </td>
                <td className="px-3 py-2">
                  <Input
                    className="w-[96px] text-right"
                    inputMode="decimal"
                    placeholder={line.currency_code && line.currency_code !== currency ? "1 ×" : "—"}
                    value={line.currency_code && line.currency_code !== currency ? line.fx_rate : ""}
                    disabled={locked || !line.currency_code || line.currency_code === currency}
                    onChange={(event) =>
                      setLines((current) =>
                        current.map((item, i) =>
                          i === index ? { ...item, fx_rate: event.target.value } : item,
                        ),
                      )
                    }
                  />
                </td>
                <td className="px-3 py-2">
                  <Input
                    className="text-right"
                    inputMode="decimal"
                    value={line.debit}
                    disabled={locked}
                    onChange={(event) =>
                      setLines((current) =>
                        current.map((item, i) =>
                          i === index ? { ...item, debit: event.target.value, credit: "" } : item,
                        ),
                      )
                    }
                  />
                </td>
                <td className="px-3 py-2">
                  <Input
                    className="text-right"
                    inputMode="decimal"
                    value={line.credit}
                    disabled={locked}
                    onChange={(event) =>
                      setLines((current) =>
                        current.map((item, i) =>
                          i === index ? { ...item, credit: event.target.value, debit: "" } : item,
                        ),
                      )
                    }
                  />
                </td>
                <td className="px-3 py-2">
                  {!locked && lines.length > 2 && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setLines((current) => current.filter((_, i) => i !== index))}
                    >
                      ×
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!locked && (
        <Button type="button" variant="outline" onClick={() => setLines((current) => [...current, emptyLine(currency)])}>
          Ajouter une ligne
        </Button>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className={`text-sm ${totals.balanced ? "text-primary" : "text-destructive"}`}>
          Débit {formatMoney(totals.debit, currency)} · Crédit {formatMoney(totals.credit, currency)}
          {totals.balanced ? " · équilibrée" : " · non équilibrée"}
          <span className="text-muted-foreground"> ({currency})</span>
        </p>
        <div className="flex gap-2">
          {locked && (
            <Button
              type="button"
              variant="outline"
              disabled={saveDues.isPending}
              onClick={() => saveDues.mutate()}
            >
              {saveDues.isPending ? "Enregistrement…" : "Enregistrer les échéances"}
            </Button>
          )}
          {!locked && (
            <>
              <Button type="submit" variant="outline" disabled={save.isPending}>
                Enregistrer brouillon
              </Button>
              <Button type="button" onClick={() => post.mutate()} disabled={post.isPending || !totals.balanced}>
                Valider
              </Button>
            </>
          )}
        </div>
      </div>
      {error && <p className="text-sm text-destructive">{error.message}</p>}
    </form>
  );
}
