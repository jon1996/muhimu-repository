"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { useTenant } from "@/components/tenant-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import {
  CLASS_PILLARS,
  IMPORT_TEMPLATE,
  LEVEL_DEPTH,
  LEVEL_LABELS,
  LEVEL_ORDER,
  buildChildrenMap,
  classColor,
  downloadTextFile,
  lineage,
  matchingIds,
} from "@/lib/chart-taxonomy";
import type { AccountFiche, AccountImportReport, LedgerAccount } from "@/lib/types";

export function ChartOfAccounts() {
  const { orgSlug, companyId, activeCompany, membership } = useTenant();
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const canWrite = ["owner", "admin", "accountant"].includes(membership?.role ?? "");

  const [query, setQuery] = useState("");
  const [classFilter, setClassFilter] = useState("");
  const [levelFilter, setLevelFilter] = useState("");
  const [kindFilter, setKindFilter] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [importOpen, setImportOpen] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [createCode, setCreateCode] = useState("");
  const [createLabel, setCreateLabel] = useState("");
  const [formError, setFormError] = useState("");
  const [detailsId, setDetailsId] = useState<string | null>(null);
  const [personalizeId, setPersonalizeId] = useState<string | null>(null);
  const [actionError, setActionError] = useState("");

  const accounts = useQuery({
    queryKey: ["accounts", orgSlug, companyId],
    queryFn: () => api<LedgerAccount[]>("/api/ledger/accounts", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });

  const list = accounts.data ?? [];
  const byId = useMemo(() => new Map(list.map((item) => [item.id, item])), [list]);
  const byCode = useMemo(() => new Map(list.map((item) => [item.code, item])), [list]);
  const children = useMemo(() => buildChildrenMap(list), [list]);
  const visible = useMemo(
    () => matchingIds(list, query, classFilter, levelFilter, kindFilter),
    [list, query, classFilter, levelFilter, kindFilter],
  );

  const roots = useMemo(() => {
    const top = children.get(null) ?? [];
    if (!visible) return top;
    return top.filter((item) => visible.has(item.id));
  }, [children, visible]);

  const selected = selectedId ? byId.get(selectedId) : undefined;

  useEffect(() => {
    if (!list.length) return;
    setExpanded((current) => {
      if (current.size > 0) return current;
      return new Set(list.filter((account) => account.level === "class").map((account) => account.id));
    });
  }, [list]);

  const stats = useMemo(() => {
    const byClass = Object.fromEntries(CLASS_PILLARS.map((pillar) => [pillar.code, 0]));
    let postable = 0;
    let collective = 0;
    let custom = 0;
    for (const account of list) {
      byClass[account.account_class] = (byClass[account.account_class] ?? 0) + 1;
      if (account.is_postable) postable += 1;
      if (account.is_collective) collective += 1;
      if (!account.is_syscohada) custom += 1;
    }
    return { byClass, postable, collective, custom };
  }, [list]);

  const preview = useMutation({
    mutationFn: (file: File) => {
      const body = new FormData();
      body.append("file", file);
      return api<AccountImportReport>("/api/ledger/accounts/import/preview", {
        method: "POST",
        body,
        orgSlug,
        companyId,
      });
    },
  });

  const commit = useMutation({
    mutationFn: (file: File) => {
      const body = new FormData();
      body.append("file", file);
      return api<AccountImportReport>("/api/ledger/accounts/import", {
        method: "POST",
        body,
        orgSlug,
        companyId,
      });
    },
    onSuccess: (report) => {
      if (report.applied) {
        queryClient.invalidateQueries({ queryKey: ["accounts", orgSlug, companyId] });
        queryClient.invalidateQueries({ queryKey: ["ledger-status"] });
      }
    },
  });

  const deleteAccount = useMutation({
    mutationFn: (account: LedgerAccount) =>
      api<{ ok: boolean }>(`/api/ledger/accounts/${account.id}`, {
        method: "DELETE",
        orgSlug,
        companyId,
      }),
    onSuccess: (_data, account) => {
      setActionError("");
      if (selectedId === account.id) setSelectedId(null);
      if (detailsId === account.id) setDetailsId(null);
      queryClient.invalidateQueries({ queryKey: ["accounts", orgSlug, companyId] });
      queryClient.invalidateQueries({ queryKey: ["ledger-status"] });
    },
    onError: (error) => {
      setActionError(error instanceof ApiError ? error.message : "Suppression impossible.");
    },
  });

  const createAccount = useMutation({
    mutationFn: () =>
      api<LedgerAccount>("/api/ledger/accounts", {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({
          code: createCode,
          label: createLabel,
        }),
      }),
    onSuccess: (account) => {
      setFormError("");
      setCreateCode("");
      setCreateLabel("");
      setPersonalizeId(null);
      queryClient.invalidateQueries({ queryKey: ["accounts", orgSlug, companyId] });
      setSelectedId(account.id);
      setExpanded((current) => new Set([...current, account.parent_id ?? "", account.id].filter(Boolean)));
    },
    onError: (error) => {
      setFormError(error instanceof ApiError ? error.message : "Création impossible.");
    },
  });

  const toggle = (id: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAccount = (account: LedgerAccount) => {
    setSelectedId(account.id);
    setCreateCode(account.level === "class" ? `${account.code}` : `${account.code}`);
    setCreateLabel("");
    setFormError("");
    setActionError("");
    if (account.children_count > 0) {
      setExpanded((current) => new Set(current).add(account.id));
    }
  };

  const openDetails = (account: LedgerAccount) => {
    selectAccount(account);
    setDetailsId(account.id);
  };

  const openPersonalize = (account: LedgerAccount) => {
    selectAccount(account);
    setDetailsId(null);
    setCreateCode(suggestedChildCode(account));
    setCreateLabel("");
    setFormError("");
    setPersonalizeId(account.id);
  };

  const requestDelete = (account: LedgerAccount) => {
    selectAccount(account);
    if (
      !window.confirm(
        `Supprimer le compte ${account.code} « ${account.label} » ? Cette action est définitive.`,
      )
    ) {
      return;
    }
    deleteAccount.mutate(account);
  };

  const onPickFile = (file: File | null) => {
    setImportFile(file);
    preview.reset();
    commit.reset();
    if (file) preview.mutate(file);
  };

  const importReport = commit.data ?? preview.data;
  const isFiltering = visible !== null;
  const detailsAccount = detailsId ? byId.get(detailsId) : undefined;
  const personalizeAccount = personalizeId ? byId.get(personalizeId) : undefined;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
            Particularité Muhimu
          </p>
          <h1 className="font-serif text-3xl">Plan de comptes vivant</h1>
          <p className="mt-1 max-w-2xl text-muted-foreground">
            {activeCompany?.name ?? "Société"} — PCGO officiel jusqu’au divisionnaire (4 chiffres),
            pages 223–273. Classe, compte à 2 chiffres, principal, divisionnaire, subdivision d’entité.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={() => downloadTextFile("plan-comptable-muhimu.csv", IMPORT_TEMPLATE)}
          >
            Modèle CSV
          </Button>
          <Button onClick={() => setImportOpen(true)} disabled={!canWrite} title={canWrite ? undefined : "Réservé au comptable"}>
            Importer un plan
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-8">
        {CLASS_PILLARS.map((pillar) => {
          const count = stats.byClass[pillar.code] ?? 0;
          const active = classFilter === pillar.code;
          return (
            <button
              key={pillar.code}
              type="button"
              onClick={() => setClassFilter(active ? "" : pillar.code)}
              className="group relative overflow-hidden rounded-xl border border-border bg-card p-3 text-left transition hover:-translate-y-0.5"
              style={{ boxShadow: active ? `inset 0 0 0 2px ${pillar.color}` : undefined }}
            >
              <span
                className="absolute inset-x-0 top-0 h-1.5"
                style={{ background: pillar.color }}
              />
              <p className="font-mono text-lg font-semibold" style={{ color: pillar.color }}>
                {pillar.code}
              </p>
              <p className="text-sm font-medium">{pillar.short}</p>
              <p className="text-xs text-muted-foreground">{count} comptes</p>
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap gap-3 text-sm">
        <Badge className="bg-card">{list.length} comptes</Badge>
        <Badge>{stats.postable} imputables</Badge>
        <Badge>{stats.collective} collectifs</Badge>
        <Badge className={stats.custom ? "bg-accent/30" : ""}>{stats.custom} personnalisés</Badge>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Card>
          <CardContent className="space-y-4 pt-5">
            <div className="flex flex-col gap-3 md:flex-row">
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Rechercher un code ou un intitulé…"
                className="md:flex-1"
              />
              <select
                className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                value={levelFilter}
                onChange={(event) => setLevelFilter(event.target.value)}
              >
                <option value="">Tous les niveaux</option>
                {LEVEL_ORDER.map((level) => (
                  <option key={level} value={level}>
                    {LEVEL_LABELS[level]}
                  </option>
                ))}
              </select>
              <select
                className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                value={kindFilter}
                onChange={(event) => setKindFilter(event.target.value)}
              >
                <option value="">Tous les types</option>
                <option value="postable">Imputables</option>
                <option value="collective">Collectifs</option>
                <option value="auxiliary">Subdivisions d’entité</option>
                <option value="custom">Personnalisés</option>
              </select>
            </div>

            {accounts.isLoading ? (
              <p className="text-sm text-muted-foreground">Chargement du plan…</p>
            ) : (
              <div className="max-h-[640px] overflow-auto rounded-lg border border-border/70">
                {roots.map((account) => (
                  <AccountBranch
                    key={account.id}
                    account={account}
                    childrenMap={children}
                    visible={visible}
                    expanded={isFiltering ? null : expanded}
                    selectedId={selectedId}
                    canWrite={canWrite}
                    deletingId={deleteAccount.isPending ? deleteAccount.variables?.id : undefined}
                    onToggle={toggle}
                    onSelect={selectAccount}
                    onDetails={openDetails}
                    onPersonalize={canWrite ? openPersonalize : undefined}
                    onDelete={requestDelete}
                  />
                ))}
                {roots.length === 0 && (
                  <p className="p-4 text-sm text-muted-foreground">Aucun compte ne correspond.</p>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <Inspector
          account={selected}
          canWrite={canWrite}
          onDetails={openDetails}
          onPersonalize={openPersonalize}
          onDelete={requestDelete}
          actionError={actionError}
          deleting={deleteAccount.isPending}
        />
      </div>

      {detailsAccount && (
        <AccountDetails
          account={detailsAccount}
          byId={byId}
          byCode={byCode}
          canWrite={canWrite}
          deleting={deleteAccount.isPending}
          onClose={() => setDetailsId(null)}
          onSelect={(account) => {
            selectAccount(account);
            setDetailsId(account.id);
          }}
          onPersonalize={openPersonalize}
          onDelete={requestDelete}
        />
      )}

      {personalizeAccount && canWrite && (
        <PersonalizeAccount
          account={personalizeAccount}
          code={createCode}
          label={createLabel}
          error={formError}
          pending={createAccount.isPending}
          onCodeChange={setCreateCode}
          onLabelChange={setCreateLabel}
          onClose={() => {
            setPersonalizeId(null);
            setFormError("");
          }}
          onSubmit={() => createAccount.mutate()}
        />
      )}

      {importOpen && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-foreground/40 p-4">
          <Card className="max-h-[90vh] w-full max-w-3xl overflow-auto">
            <CardContent className="space-y-4 pt-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="font-serif text-2xl">Importer un plan</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Fusion uniquement : création et mise à jour. Les comptes déjà mouvementés ne sont
                    pas supprimés. Séparateur `;` ou `,`.
                  </p>
                </div>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setImportOpen(false);
                    onPickFile(null);
                  }}
                >
                  Fermer
                </Button>
              </div>

              <label
                className="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-accent bg-muted/40 px-6 py-10 text-center"
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  onPickFile(event.dataTransfer.files?.[0] ?? null);
                }}
              >
                <p className="font-medium">Déposer un CSV ou cliquer pour choisir</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Colonnes : code, intitulé, imputable, collectif, notes
                </p>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".csv,text/csv"
                  className="hidden"
                  onChange={(event) => onPickFile(event.target.files?.[0] ?? null)}
                />
              </label>

              {importFile && (
                <p className="text-sm text-muted-foreground">
                  Fichier : {importFile.name} · {Math.round(importFile.size / 1024)} Ko
                </p>
              )}
              {preview.isError && (
                <p className="text-sm text-destructive">
                  {preview.error instanceof ApiError
                    ? preview.error.message
                    : "Prévisualisation impossible."}
                </p>
              )}

              {importReport && (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2 text-sm">
                    <Badge>{importReport.created} à créer</Badge>
                    <Badge>{importReport.updated} à mettre à jour</Badge>
                    <Badge className={importReport.errors ? "bg-destructive/10 text-destructive" : ""}>
                      {importReport.errors} erreur(s)
                    </Badge>
                  </div>
                  <div className="max-h-64 overflow-auto rounded-lg border border-border">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-muted text-muted-foreground">
                        <tr>
                          <th className="px-3 py-2 font-medium">Ligne</th>
                          <th className="px-3 py-2 font-medium">Code</th>
                          <th className="px-3 py-2 font-medium">Intitulé</th>
                          <th className="px-3 py-2 font-medium">Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {importReport.rows.map((row) => (
                          <tr key={`${row.line}-${row.code}`} className="border-t border-border/70">
                            <td className="px-3 py-1.5 font-mono text-xs">{row.line}</td>
                            <td className="px-3 py-1.5 font-mono">{row.code}</td>
                            <td className="px-3 py-1.5">
                              {row.label}
                              {row.errors.length > 0 && (
                                <p className="text-xs text-destructive">{row.errors.join(" ")}</p>
                              )}
                            </td>
                            <td className="px-3 py-1.5 text-muted-foreground">
                              {row.errors.length ? "erreur" : row.action === "update" ? "maj" : "création"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <Button
                    disabled={!importFile || importReport.errors > 0 || commit.isPending}
                    onClick={() => importFile && commit.mutate(importFile)}
                  >
                    {commit.isPending ? "Import…" : "Confirmer la fusion"}
                  </Button>
                  {commit.data?.applied && (
                    <p className="text-sm text-muted-foreground">
                      Import terminé : {commit.data.created} créé(s), {commit.data.updated} mis à jour.
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

function canDeleteAccount(account: LedgerAccount, canWrite: boolean) {
  return canWrite && !account.is_syscohada && account.level !== "class";
}

function suggestedChildCode(account: LedgerAccount) {
  return `${account.code}-`;
}

function AccountBranch({
  account,
  childrenMap,
  visible,
  expanded,
  selectedId,
  canWrite,
  deletingId,
  onToggle,
  onSelect,
  onDetails,
  onPersonalize,
  onDelete,
}: {
  account: LedgerAccount;
  childrenMap: Map<string | null, LedgerAccount[]>;
  visible: Set<string> | null;
  expanded: Set<string> | null;
  selectedId: string | null;
  canWrite: boolean;
  deletingId?: string;
  onToggle: (id: string) => void;
  onSelect: (account: LedgerAccount) => void;
  onDetails: (account: LedgerAccount) => void;
  onPersonalize?: (account: LedgerAccount) => void;
  onDelete: (account: LedgerAccount) => void;
}) {
  const kids = (childrenMap.get(account.id) ?? []).filter((child) => !visible || visible.has(child.id));
  const open = expanded === null ? kids.length > 0 : expanded.has(account.id);
  const depth = LEVEL_DEPTH[account.level] ?? 0;
  const selected = selectedId === account.id;
  const color = classColor(account.account_class);

  return (
    <div>
      <div
        className={`flex items-center gap-2 border-b border-border/50 px-2 py-1.5 text-sm ${
          selected ? "bg-muted" : "hover:bg-muted/50"
        }`}
        style={{ paddingLeft: 8 + depth * 18 }}
      >
        {kids.length > 0 ? (
          <button
            type="button"
            className="flex size-6 items-center justify-center rounded text-muted-foreground"
            onClick={() => onToggle(account.id)}
            aria-label={open ? "Replier" : "Déplier"}
          >
            {open ? "▾" : "▸"}
          </button>
        ) : (
          <span className="size-6" />
        )}
        <button type="button" className="flex min-w-0 flex-1 items-center gap-2 text-left" onClick={() => onSelect(account)}>
          <span className="h-5 w-1.5 shrink-0 rounded-full" style={{ background: color }} />
          <span className="w-24 shrink-0 font-mono text-[13px]" style={{ color }}>
            {account.code}
          </span>
          <span className={`min-w-0 truncate ${account.level === "class" ? "font-semibold" : ""}`}>
            {account.label}
          </span>
          <span className="ml-auto hidden shrink-0 gap-1 lg:flex">
            {account.is_collective && <MiniChip>collectif</MiniChip>}
            {account.level === "auxiliary" && <MiniChip>subdivision</MiniChip>}
            {!account.is_syscohada && <MiniChip>perso</MiniChip>}
            {!account.is_postable && <MiniChip>non imputable</MiniChip>}
          </span>
        </button>
        <div className="flex shrink-0 gap-1">
          <Button
            type="button"
            size="xs"
            variant="outline"
            onClick={(event) => {
              event.stopPropagation();
              onDetails(account);
            }}
          >
            Détails
          </Button>
          {onPersonalize && (
            <Button
              type="button"
              size="xs"
              variant="secondary"
              onClick={(event) => {
                event.stopPropagation();
                onPersonalize(account);
              }}
            >
              Personnaliser
            </Button>
          )}
          {canWrite && (
            <Button
              type="button"
              size="xs"
              variant="destructive"
              disabled={!canDeleteAccount(account, canWrite) || deletingId === account.id}
              title={
                canDeleteAccount(account, canWrite)
                  ? undefined
                  : "Les comptes officiels du PCGO ne peuvent pas être supprimés."
              }
              onClick={(event) => {
                event.stopPropagation();
                onDelete(account);
              }}
            >
              Supprimer
            </Button>
          )}
        </div>
      </div>
      {open &&
        kids.map((child) => (
          <AccountBranch
            key={child.id}
            account={child}
            childrenMap={childrenMap}
            visible={visible}
            expanded={expanded}
            selectedId={selectedId}
            canWrite={canWrite}
            deletingId={deletingId}
            onToggle={onToggle}
            onSelect={onSelect}
            onDetails={onDetails}
            onPersonalize={onPersonalize}
            onDelete={onDelete}
          />
        ))}
    </div>
  );
}

function MiniChip({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
      {children}
    </span>
  );
}

function Inspector({
  account,
  canWrite,
  onDetails,
  onPersonalize,
  onDelete,
  actionError,
  deleting,
}: {
  account?: LedgerAccount;
  canWrite: boolean;
  onDetails: (account: LedgerAccount) => void;
  onPersonalize: (account: LedgerAccount) => void;
  onDelete: (account: LedgerAccount) => void;
  actionError: string;
  deleting: boolean;
}) {
  if (!account) {
    return (
      <Card>
        <CardContent className="space-y-4 pt-6">
          <p className="font-serif text-xl">Lecture SYSCOHADA</p>
          <p className="text-sm text-muted-foreground">
            Choisissez un compte, puis Personnaliser pour ajouter une subdivision d’entité
            (411-SOCOCIM, 521-BNDE). Le PCGO officiel ne se modifie pas.
          </p>
          <ul className="space-y-1.5 text-sm text-muted-foreground">
            <li>
              <span className="font-medium text-foreground">9</span> à 2 chiffres : provisions /
              dépréciations de la classe.
            </li>
            <li>
              <span className="font-medium text-foreground">9</span> en 3e ou 4e position : solde
              inversé — sauf classe 2.
            </li>
            <li>
              <span className="font-medium text-foreground">8</span> : les « autres » du même
              niveau.
            </li>
            <li>
              <span className="font-medium text-foreground">6 ↔ 7</span> et impair / pair en classe
              8 : parallèles charge / produit.
            </li>
          </ul>
        </CardContent>
      </Card>
    );
  }

  const color = classColor(account.account_class);

  return (
    <Card className="xl:sticky xl:top-4">
      <CardContent className="space-y-5 pt-5">
        <div>
          <p className="font-mono text-sm" style={{ color }}>
            {account.code}
          </p>
          <h2 className="font-serif text-2xl leading-tight">{account.label}</h2>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Badge>{account.level_label}</Badge>
            <Badge>{account.family_label}</Badge>
            <Badge>{account.sense_label}</Badge>
            {account.is_collective && <Badge>Collectif</Badge>}
            {account.is_postable ? <Badge>Imputable</Badge> : <Badge>Non imputable</Badge>}
            {!account.is_syscohada && <Badge className="bg-accent/30">Personnalisé</Badge>}
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button type="button" onClick={() => onDetails(account)}>
            Détails
          </Button>
          {canWrite && (
            <Button type="button" variant="secondary" onClick={() => onPersonalize(account)}>
              Personnaliser
            </Button>
          )}
          {canWrite && (
            <Button
              type="button"
              variant="destructive"
              disabled={!canDeleteAccount(account, canWrite) || deleting}
              title={
                canDeleteAccount(account, canWrite)
                  ? undefined
                  : "Les comptes officiels du PCGO ne peuvent pas être supprimés."
              }
              onClick={() => onDelete(account)}
            >
              {deleting ? "Suppression…" : "Supprimer"}
            </Button>
          )}
        </div>
        {actionError && <p className="text-sm text-destructive">{actionError}</p>}
        <p className="text-sm text-muted-foreground">
          Détails : fiche officielle. Personnaliser : subdivision d’entité sous ce compte.
        </p>
      </CardContent>
    </Card>
  );
}

function AccountDetails({
  account,
  byId,
  byCode,
  canWrite,
  deleting,
  onClose,
  onSelect,
  onPersonalize,
  onDelete,
}: {
  account: LedgerAccount;
  byId: Map<string, LedgerAccount>;
  byCode: Map<string, LedgerAccount>;
  canWrite: boolean;
  deleting: boolean;
  onClose: () => void;
  onSelect: (account: LedgerAccount) => void;
  onPersonalize: (account: LedgerAccount) => void;
  onDelete: (account: LedgerAccount) => void;
}) {
  const { orgSlug, companyId } = useTenant();
  const ficheQuery = useQuery({
    queryKey: ["account-fiche", orgSlug, companyId, account.code],
    queryFn: () =>
      api<AccountFiche>(`/api/ledger/accounts/fiche?code=${encodeURIComponent(account.code)}`, {
        orgSlug,
        companyId,
      }),
    enabled: Boolean(orgSlug && companyId && account.code),
  });

  const chain = lineage(account, byId);
  const color = classColor(account.account_class);
  const anatomy = account.anatomy;
  const segments = [
    { key: "Classe", value: anatomy.class_code },
    { key: "2 chiffres", value: anatomy.two_digit ?? anatomy.subclass },
    { key: "Principal", value: anatomy.principal },
    { key: "Divisionnaire", value: anatomy.divisionary ?? anatomy.secondary },
    { key: "Subdivision", value: anatomy.entity ?? anatomy.auxiliary },
  ].filter((item) => item.value);
  const reading = account.reading;
  const parallel = reading?.parallel_code
    ? byCode.get(reading.parallel_code) ?? byCode.get(reading.parallel_code.slice(0, 3))
    : undefined;

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-foreground/40 p-4"
      onClick={onClose}
    >
      <Card className="max-h-[90vh] w-full max-w-3xl overflow-auto" onClick={(event) => event.stopPropagation()}>
        <CardContent className="space-y-5 pt-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="font-mono text-sm" style={{ color }}>
                {account.code}
              </p>
              <h2 className="font-serif text-2xl leading-tight">{account.label}</h2>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <Badge>{account.level_label}</Badge>
                <Badge>{account.family_label}</Badge>
                <Badge>{account.sense_label}</Badge>
                {account.is_collective && <Badge>Collectif</Badge>}
                {account.is_postable ? <Badge>Imputable</Badge> : <Badge>Non imputable</Badge>}
                {!account.is_syscohada && <Badge className="bg-accent/30">Personnalisé</Badge>}
              </div>
            </div>
            <div className="flex shrink-0 flex-wrap justify-end gap-2">
              {canWrite && (
                <Button type="button" variant="secondary" onClick={() => onPersonalize(account)}>
                  Personnaliser
                </Button>
              )}
              {canWrite && (
                <Button
                  type="button"
                  variant="destructive"
                  disabled={!canDeleteAccount(account, canWrite) || deleting}
                  title={
                    canDeleteAccount(account, canWrite)
                      ? undefined
                      : "Les comptes officiels du PCGO ne peuvent pas être supprimés."
                  }
                  onClick={() => onDelete(account)}
                >
                  {deleting ? "Suppression…" : "Supprimer"}
                </Button>
              )}
              <Button type="button" variant="outline" onClick={onClose}>
                Fermer
              </Button>
            </div>
          </div>

          <div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Lecture du code
            </p>
            <div className="flex flex-wrap gap-2">
              {segments.map((segment) => (
                <div key={segment.key} className="min-w-[4.5rem] rounded-lg border border-border bg-muted/40 px-2.5 py-2">
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{segment.key}</p>
                  <p className="font-mono text-sm font-semibold" style={{ color }}>
                    {segment.value}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {(reading?.constants.length || reading?.parallel_code) && (
            <div className="space-y-2">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Grammaire du code
              </p>
              {reading.parallel_code && (
                <button
                  type="button"
                  className="w-full rounded-lg border border-accent/50 bg-accent/15 px-3 py-2 text-left"
                  onClick={() => parallel && onSelect(parallel)}
                  disabled={!parallel}
                >
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                    {reading.parallel_label ?? "Parallèle"}
                  </p>
                  <p className="font-mono text-sm font-semibold">
                    {reading.parallel_code}
                    {parallel ? ` · ${parallel.label}` : " · absent du plan"}
                  </p>
                </button>
              )}
              {(reading.constants ?? []).map((item) => (
                <div key={item.kind} className="rounded-lg border border-border bg-muted/30 px-3 py-2">
                  <p className="text-sm font-medium">{item.title}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">{item.detail}</p>
                </div>
              ))}
            </div>
          )}

          <div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Filiation
            </p>
            <ol className="space-y-1 text-sm">
              {chain.map((item, index) => (
                <li key={item.id} className="flex gap-2">
                  <span className="text-muted-foreground">{index === 0 ? "↳" : "→"}</span>
                  <span className="font-mono" style={{ color: classColor(item.account_class) }}>
                    {item.code}
                  </span>
                  <span className="text-muted-foreground">{item.label}</span>
                </li>
              ))}
            </ol>
          </div>

          {account.notes && <p className="rounded-lg bg-muted px-3 py-2 text-sm">{account.notes}</p>}

          {ficheQuery.isLoading && (
            <p className="text-sm text-muted-foreground">Chargement de la fiche officielle…</p>
          )}
          {ficheQuery.data && <OfficialFiche fiche={ficheQuery.data} accountCode={account.code} />}
          {ficheQuery.isError && (
            <p className="text-sm text-destructive">
              {ficheQuery.error instanceof ApiError
                ? ficheQuery.error.message
                : "Fiche officielle indisponible."}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function PersonalizeAccount({
  account,
  code,
  label,
  error,
  pending,
  onCodeChange,
  onLabelChange,
  onClose,
  onSubmit,
}: {
  account: LedgerAccount;
  code: string;
  label: string;
  error: string;
  pending: boolean;
  onCodeChange: (value: string) => void;
  onLabelChange: (value: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  const color = classColor(account.account_class);
  const example = `${account.code}-SOCOCIM`;

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-foreground/40 p-4"
      onClick={onClose}
    >
      <Card className="w-full max-w-lg" onClick={(event) => event.stopPropagation()}>
        <CardContent className="space-y-4 pt-5">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Subdivision d’entité
            </p>
            <h2 className="font-serif text-2xl">Personnaliser</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Le compte officiel{" "}
              <span className="font-mono font-medium" style={{ color }}>
                {account.code}
              </span>{" "}
              {account.label} reste intact. Vous ajoutez un sous-compte propre à la société
              (Titre VII).
            </p>
          </div>

          <ul className="space-y-1 text-sm text-muted-foreground">
            <li>
              Code avec tiret : <span className="font-mono text-foreground">{example}</span>
            </li>
            <li>
              Ou chiffres plus longs :{" "}
              <span className="font-mono text-foreground">{account.code}01</span>
            </li>
          </ul>

          <form
            className="space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              onSubmit();
            }}
          >
            <div className="space-y-1.5">
              <Label htmlFor="perso-code">Code</Label>
              <Input
                id="perso-code"
                value={code}
                onChange={(event) => onCodeChange(event.target.value)}
                placeholder={example}
                autoFocus
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="perso-label">Intitulé</Label>
              <Input
                id="perso-label"
                value={label}
                onChange={(event) => onLabelChange(event.target.value)}
                placeholder="Clients SOCOCIM"
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={onClose}>
                Annuler
              </Button>
              <Button type="submit" disabled={pending || !code || !label}>
                {pending ? "Création…" : "Ajouter au plan"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function OfficialFiche({ fiche, accountCode }: { fiche: AccountFiche; accountCode: string }) {
  const inherited = fiche.fiche_code !== accountCode.replace(/[-_].*$/, "") && fiche.fiche_code !== accountCode;
  return (
    <div className="space-y-2 border-t border-border pt-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        Fiche officielle · Titre VII
      </p>
      {inherited && (
        <p className="text-xs text-muted-foreground">
          Le SYSCOHADA décrit le compte {fiche.fiche_code} {fiche.title} — parent de {accountCode}.
        </p>
      )}
      {(fiche.debit.length > 0 || fiche.credit.length > 0) && (
        <div className="grid gap-2">
          {fiche.debit.map((line) => (
            <p key={line} className="rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-xs">
              <span className="font-semibold text-destructive">Débit · </span>
              {line}
            </p>
          ))}
          {fiche.credit.map((line) => (
            <p key={line} className="rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-xs">
              <span className="font-semibold text-primary">Crédit · </span>
              {line}
            </p>
          ))}
        </div>
      )}
      <FicheSection title="Contenu" text={fiche.contenu} open />
      <FicheSection title="Fonctionnement" text={fiche.fonctionnement} />
      <FicheSection title="Exclusions" text={fiche.exclusions} />
      <FicheSection title="Éléments de contrôle" text={fiche.controles} />
      <FicheSection title="Subdivisions" text={fiche.subdivisions} />
      <FicheSection title="Commentaires" text={fiche.commentaires} />
    </div>
  );
}

function FicheSection({ title, text, open = false }: { title: string; text: string; open?: boolean }) {
  if (!text) return null;
  return (
    <details open={open} className="rounded-lg border border-border bg-muted/20 px-3 py-2">
      <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
        {title}
      </summary>
      <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">{text}</p>
    </details>
  );
}
