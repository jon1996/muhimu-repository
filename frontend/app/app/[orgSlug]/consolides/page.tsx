"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { BetaScopeGate } from "@/components/beta-scope-gate";
import { StatementTable } from "@/components/statement-table";
import { useTenant } from "@/components/tenant-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError, downloadApi } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import type { ConsolidationGroup } from "@/lib/types";

const TABS = [
  ["bilan", "Bilan"],
  ["result", "Compte de résultat"],
  ["tft", "TFT"],
  ["notes", "Notes"],
] as const;

export default function ConsolidesPage() {
  const { orgSlug, companyId, companies, membership } = useTenant();
  const canWrite = ["owner", "admin", "accountant"].includes(membership?.role ?? "");
  const queryClient = useQueryClient();
  const [groupId, setGroupId] = useState("");
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("bilan");
  const [error, setError] = useState("");
  const [pdfKind, setPdfKind] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("consolidated");
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [parentId, setParentId] = useState("");
  const [memberCompany, setMemberCompany] = useState("");
  const [memberMethod, setMemberMethod] = useState("full");
  const [memberPct, setMemberPct] = useState("100");
  const [elimCode, setElimCode] = useState("TA");
  const [elimLabel, setElimLabel] = useState("");
  const [elimAmount, setElimAmount] = useState("");
  const [elimKind, setElimKind] = useState("sales");

  const list = useQuery({
    queryKey: ["consolidation", orgSlug],
    queryFn: () => api<ConsolidationGroup[]>("/api/ledger/consolidation", { orgSlug, companyId }),
    enabled: Boolean(orgSlug),
  });
  const selectedId = groupId || list.data?.[0]?.id || "";
  const detail = useQuery({
    queryKey: ["consolidation", orgSlug, selectedId],
    queryFn: () =>
      api<ConsolidationGroup>(`/api/ledger/consolidation/${selectedId}`, { orgSlug, companyId }),
    enabled: Boolean(orgSlug && selectedId),
  });

  const onError = (err: unknown) => {
    setError(err instanceof ApiError ? err.message : "Action impossible.");
  };
  const invalidate = (panel?: ConsolidationGroup) => {
    setError("");
    queryClient.invalidateQueries({ queryKey: ["consolidation"] });
    if (panel?.id) setGroupId(panel.id);
  };

  const create = useMutation({
    mutationFn: () =>
      api<ConsolidationGroup>("/api/ledger/consolidation", {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({
          name,
          kind,
          year: Number(year),
          parent_id: kind === "consolidated" ? parentId || companyId : parentId || undefined,
          currency_code: companies.find((item) => item.id === (parentId || companyId))?.currency_code,
        }),
      }),
    onSuccess: (panel) => {
      setName("");
      invalidate(panel);
    },
    onError,
  });

  const addMember = useMutation({
    mutationFn: () =>
      api<ConsolidationGroup>(`/api/ledger/consolidation/${selectedId}/members`, {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({
          company_id: memberCompany,
          method: memberMethod,
          ownership_pct: memberPct,
        }),
      }),
    onSuccess: () => {
      setMemberCompany("");
      invalidate();
    },
    onError,
  });

  const addElim = useMutation({
    mutationFn: () =>
      api<ConsolidationGroup>(`/api/ledger/consolidation/${selectedId}/eliminations`, {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({
          code: elimCode,
          label: elimLabel || elimCode,
          amount: elimAmount,
          kind: elimKind,
        }),
      }),
    onSuccess: () => {
      setElimAmount("");
      invalidate();
    },
    onError,
  });

  const removeMember = useMutation({
    mutationFn: (id: string) =>
      api(`/api/ledger/consolidation/${selectedId}/members/${id}`, {
        method: "DELETE",
        orgSlug,
        companyId,
      }),
    onSuccess: () => invalidate(),
    onError,
  });

  const removeElim = useMutation({
    mutationFn: (id: string) =>
      api(`/api/ledger/consolidation/${selectedId}/eliminations/${id}`, {
        method: "DELETE",
        orgSlug,
        companyId,
      }),
    onSuccess: () => invalidate(),
    onError,
  });

  const group = detail.data;
  const statements = group?.statements;
  const currency = group?.currency_code ?? "XOF";
  const prior = statements?.comparative_year ?? null;
  const used = useMemo(() => new Set((group?.members ?? []).map((item) => item.company_id)), [group]);

  async function downloadPdf(kindPdf: "liasse" | "bilan" | "result" | "tft" | "notes") {
    if (!selectedId || !statements) return;
    setPdfKind(kindPdf);
    setError("");
    try {
      await downloadApi(`/api/ledger/consolidation/${selectedId}/pdf?kind=${kindPdf}`, {
        orgSlug,
        companyId,
        filename: `${kindPdf}-${group?.kind ?? "groupe"}-${group?.year ?? ""}.pdf`,
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Téléchargement PDF impossible.");
    } finally {
      setPdfKind(null);
    }
  }

  return (
    <BetaScopeGate feature="consolidation">
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl">États consolidés / combinés</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            AUDCIF art. 5. Consolidé = société mère + filiales (intégration globale, minoritaires,
            éliminations). Combiné = entités sous contrôle commun, sans mère juridique. Liasse SN
            agrégée, jamais mélangée aux comptes individuels.
          </p>
        </div>
        <select
          className="h-10 rounded-md border border-input bg-background px-2 text-sm"
          value={selectedId}
          onChange={(event) => setGroupId(event.target.value)}
        >
          {(list.data ?? []).length === 0 && <option value="">Aucun périmètre</option>}
          {(list.data ?? []).map((item) => (
            <option key={item.id} value={item.id}>
              {item.name} · {item.year} · {item.kind === "combined" ? "combiné" : "consolidé"}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {(group?.warnings ?? []).map((item) => (
        <p key={item} className="text-sm text-amber-800">
          {item}
        </p>
      ))}

      {canWrite && (
        <Card>
          <CardHeader>
            <CardTitle>Nouveau périmètre</CardTitle>
            <CardDescription>Un dossier par exercice. La mère est obligatoire pour un consolidé.</CardDescription>
          </CardHeader>
          <CardContent>
            <form
              className="grid gap-3 md:grid-cols-[1fr_160px_110px_1fr_auto] md:items-end"
              onSubmit={(event) => {
                event.preventDefault();
                create.mutate();
              }}
            >
              <div>
                <Label htmlFor="cons-name">Intitulé</Label>
                <Input
                  id="cons-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Groupe Horizon"
                  required
                />
              </div>
              <div>
                <Label htmlFor="cons-kind">Type</Label>
                <select
                  id="cons-kind"
                  className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                  value={kind}
                  onChange={(event) => setKind(event.target.value)}
                >
                  <option value="consolidated">Consolidé</option>
                  <option value="combined">Combiné</option>
                </select>
              </div>
              <div>
                <Label htmlFor="cons-year">Exercice</Label>
                <Input id="cons-year" value={year} onChange={(event) => setYear(event.target.value)} required />
              </div>
              <div>
                <Label htmlFor="cons-parent">{kind === "combined" ? "Société de référence" : "Société mère"}</Label>
                <select
                  id="cons-parent"
                  className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                  value={parentId || companyId}
                  onChange={(event) => setParentId(event.target.value)}
                >
                  {companies.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </div>
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? "Création…" : "Créer"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {group && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Sociétés du périmètre</CardTitle>
              <CardDescription>
                Intégration globale (100 % + minoritaires), proportionnelle, combinaison, ou mise en
                équivalence (hors agrégation v1).
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {canWrite && (
                <form
                  className="grid gap-3 md:grid-cols-[1fr_1fr_120px_auto] md:items-end"
                  onSubmit={(event) => {
                    event.preventDefault();
                    addMember.mutate();
                  }}
                >
                  <div>
                    <Label htmlFor="cons-member">Société</Label>
                    <select
                      id="cons-member"
                      className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                      value={memberCompany}
                      onChange={(event) => setMemberCompany(event.target.value)}
                      required
                    >
                      <option value="">Choisir…</option>
                      {companies
                        .filter((item) => !used.has(item.id))
                        .map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.name}
                          </option>
                        ))}
                    </select>
                  </div>
                  <div>
                    <Label htmlFor="cons-method">Méthode</Label>
                    <select
                      id="cons-method"
                      className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                      value={memberMethod}
                      onChange={(event) => setMemberMethod(event.target.value)}
                    >
                      <option value="full">Intégration globale</option>
                      <option value="proportional">Intégration proportionnelle</option>
                      <option value="combined">Combinaison</option>
                      <option value="equity">Mise en équivalence</option>
                    </select>
                  </div>
                  <div>
                    <Label htmlFor="cons-pct">% intérêt</Label>
                    <Input
                      id="cons-pct"
                      value={memberPct}
                      onChange={(event) => setMemberPct(event.target.value)}
                      required
                    />
                  </div>
                  <Button type="submit" disabled={addMember.isPending || !memberCompany}>
                    {addMember.isPending ? "Ajout…" : "Ajouter"}
                  </Button>
                </form>
              )}
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-3 font-medium">Société</th>
                    <th className="py-2 pr-3 font-medium">Méthode</th>
                    <th className="py-2 pr-3 font-medium text-right">%</th>
                    <th className="py-2 pr-3 font-medium text-right">CA</th>
                    <th className="py-2 pr-3 font-medium text-right">Résultat</th>
                    {canWrite && <th className="py-2 font-medium" />}
                  </tr>
                </thead>
                <tbody>
                  {(group.summaries ?? group.members).map((row) => (
                    <tr key={row.id} className="border-b border-border/70">
                      <td className="py-1.5 pr-3">
                        {row.company_name}
                        {row.is_parent ? " · mère" : ""}
                      </td>
                      <td className="py-1.5 pr-3 text-muted-foreground">{row.method}</td>
                      <td className="py-1.5 pr-3 text-right font-mono">{row.ownership_pct}</td>
                      <td className="py-1.5 pr-3 text-right font-mono">
                        {"sales" in row
                          ? formatMoney(String(row.sales), currency)
                          : "—"}
                      </td>
                      <td className="py-1.5 pr-3 text-right font-mono">
                        {"net" in row ? formatMoney(String(row.net), currency) : "—"}
                      </td>
                      {canWrite && (
                        <td className="py-1.5 text-right">
                          {!row.is_parent && (
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={() => removeMember.mutate(row.id)}
                            >
                              Retirer
                            </Button>
                          )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Éliminations intra-groupe</CardTitle>
              <CardDescription>
                Montant soustrait du poste SN (TA ventes, RA achats, BI clients, DJ fournisseurs, AR
                titres…). Signe négatif pour annuler une charge (RA).
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {canWrite && (
                <form
                  className="grid gap-3 md:grid-cols-[100px_1fr_140px_160px_auto] md:items-end"
                  onSubmit={(event) => {
                    event.preventDefault();
                    addElim.mutate();
                  }}
                >
                  <div>
                    <Label htmlFor="elim-code">Poste</Label>
                    <Input id="elim-code" value={elimCode} onChange={(event) => setElimCode(event.target.value)} required />
                  </div>
                  <div>
                    <Label htmlFor="elim-label">Libellé</Label>
                    <Input
                      id="elim-label"
                      value={elimLabel}
                      onChange={(event) => setElimLabel(event.target.value)}
                      placeholder="CA intra-groupe"
                    />
                  </div>
                  <div>
                    <Label htmlFor="elim-amount">Montant</Label>
                    <Input
                      id="elim-amount"
                      value={elimAmount}
                      onChange={(event) => setElimAmount(event.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor="elim-kind">Nature</Label>
                    <select
                      id="elim-kind"
                      className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                      value={elimKind}
                      onChange={(event) => setElimKind(event.target.value)}
                    >
                      <option value="sales">CA / achats</option>
                      <option value="rec_pay">Créances / dettes</option>
                      <option value="investment">Titres / capitaux</option>
                      <option value="dividend">Dividendes</option>
                      <option value="other">Autre</option>
                    </select>
                  </div>
                  <Button type="submit" disabled={addElim.isPending}>
                    {addElim.isPending ? "Enregistrement…" : "Éliminer"}
                  </Button>
                </form>
              )}
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-3 font-medium">Poste</th>
                    <th className="py-2 pr-3 font-medium">Libellé</th>
                    <th className="py-2 pr-3 font-medium text-right">Montant</th>
                    {canWrite && <th className="py-2 font-medium" />}
                  </tr>
                </thead>
                <tbody>
                  {group.eliminations.map((item) => (
                    <tr key={item.id} className="border-b border-border/70">
                      <td className="py-1.5 pr-3 font-mono">{item.code}</td>
                      <td className="py-1.5 pr-3">{item.label}</td>
                      <td className="py-1.5 pr-3 text-right font-mono">{formatMoney(item.amount, currency)}</td>
                      {canWrite && (
                        <td className="py-1.5 text-right">
                          <Button type="button" variant="ghost" size="sm" onClick={() => removeElim.mutate(item.id)}>
                            Retirer
                          </Button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
              {group.eliminations.length === 0 && (
                <p className="text-sm text-muted-foreground">Aucune élimination pour l’instant.</p>
              )}
            </CardContent>
          </Card>

          {statements && (
            <Card>
              <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-4">
                <div>
                  <CardTitle>
                    {group.kind === "combined" ? "Liasse combinée" : "Liasse consolidée"} {group.year}
                  </CardTitle>
                  <CardDescription>
                    {statements.entity?.regime_label} · {currency}
                    {group.minorities && group.minorities !== "0"
                      ? ` · intérêts minoritaires ${formatMoney(group.minorities, currency)}`
                      : ""}
                    .
                  </CardDescription>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" onClick={() => downloadPdf("liasse")} disabled={pdfKind !== null}>
                    {pdfKind === "liasse" ? "Préparation…" : "PDF liasse"}
                  </Button>
                  <Button type="button" variant="outline" onClick={() => downloadPdf(tab)} disabled={pdfKind !== null}>
                    PDF {tab}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {TABS.map(([id, label]) => (
                    <Button key={id} type="button" variant={tab === id ? "default" : "outline"} onClick={() => setTab(id)}>
                      {label}
                    </Button>
                  ))}
                </div>
                {tab === "bilan" && (
                  <div className="grid gap-8 lg:grid-cols-2">
                    <div>
                      <h3 className="mb-2 font-medium">Actif</h3>
                      <StatementTable
                        lines={statements.bilan.actif}
                        currency={currency}
                        priorYear={prior}
                        showGross
                      />
                    </div>
                    <div>
                      <h3 className="mb-2 font-medium">Passif</h3>
                      <StatementTable lines={statements.bilan.passif} currency={currency} priorYear={prior} />
                    </div>
                  </div>
                )}
                {tab === "result" && (
                  <StatementTable lines={statements.result.lines} currency={currency} priorYear={prior} />
                )}
                {tab === "tft" && (
                  <StatementTable lines={statements.tft.lines} currency={currency} priorYear={prior} />
                )}
                {tab === "notes" && (
                  <ul className="space-y-3 text-sm">
                    {(statements.notes ?? []).map((note) => (
                      <li key={note.number}>
                        <p className="font-medium">
                          Note {note.number} — {note.title}
                        </p>
                        <p className="text-muted-foreground">{note.computed || note.body || "—"}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
    </BetaScopeGate>
  );
}
