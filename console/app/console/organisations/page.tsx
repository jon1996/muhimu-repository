"use client";

import { useMemo, useState, type ReactNode } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { TenantDirectory, TenantOrg } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";

type Filter = "all" | "sme" | "cabinet" | "client" | "demo";

function formatWhen(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("fr-FR");
}

function Pill({
  children,
  tone = "muted",
}: {
  children: ReactNode;
  tone?: "ok" | "warn" | "muted";
}) {
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium",
        tone === "ok" && "bg-primary/15 text-primary",
        tone === "warn" && "bg-destructive/10 text-destructive",
        tone === "muted" && "bg-muted text-muted-foreground",
      )}
    >
      {children}
    </span>
  );
}

export default function OrganisationsPage() {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [selectedId, setSelectedId] = useState<string>("");

  const directory = useQuery({
    queryKey: ["tenants"],
    queryFn: () => api<TenantDirectory>("/api/tenants"),
  });

  const orgs = directory.data?.organizations ?? [];
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return orgs.filter((org) => {
      if (filter === "sme" && org.type !== "sme") return false;
      if (filter === "cabinet" && org.type !== "cabinet") return false;
      if (filter === "client" && org.is_demo) return false;
      if (filter === "demo" && !org.is_demo) return false;
      if (!needle) return true;
      const hay = [
        org.name,
        org.slug,
        ...org.companies.flatMap((company) => [company.name, company.rccm, company.tax_id, company.city]),
        ...org.members.flatMap((member) => [member.email, member.full_name]),
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(needle);
    });
  }, [filter, orgs, query]);

  const selected =
    filtered.find((org) => org.id === selectedId) ?? filtered[0] ?? orgs.find((org) => org.id === selectedId);

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <div>
        <h1 className="font-serif text-3xl">Organisations</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Toutes les PME et cabinets inscrits sur Muhimu, avec sociétés, identité SYSCOHADA et
          membres.
        </p>
      </div>

      {directory.isPending && <p className="text-sm text-muted-foreground">Chargement…</p>}
      {directory.isError && (
        <p className="text-sm text-destructive">
          {directory.error instanceof ApiError
            ? directory.error.message
            : "Impossible de charger les organisations."}
        </p>
      )}

      {directory.data && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <Stat label="Dossiers" value={directory.data.org_count} />
            <Stat label="PME" value={directory.data.pme_count} />
            <Stat label="Cabinets" value={directory.data.cabinet_count} />
            <Stat label="Sociétés" value={directory.data.company_count} />
            <Stat label="Utilisateurs ERP" value={directory.data.user_count} />
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Rechercher nom, RCCM, NIF, e-mail…"
              className="sm:max-w-sm"
            />
            <div className="flex flex-wrap gap-2">
              {(
                [
                  ["all", "Tous"],
                  ["sme", "PME"],
                  ["cabinet", "Cabinets"],
                  ["client", "Clients"],
                  ["demo", "Démo"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setFilter(id)}
                  className={cn(
                    "rounded-full border px-3 py-1 text-xs",
                    filter === id
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border text-muted-foreground hover:border-primary/40",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <Card>
            <CardContent className="overflow-x-auto pt-6">
              {filtered.length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucun dossier ne correspond.</p>
              ) : (
                <table className="w-full min-w-[720px] text-left text-sm">
                  <thead className="text-xs uppercase tracking-wide text-muted-foreground">
                    <tr>
                      <th className="pb-3 font-medium">Organisation</th>
                      <th className="pb-3 font-medium">Type</th>
                      <th className="pb-3 font-medium">Sociétés</th>
                      <th className="pb-3 font-medium">Membres</th>
                      <th className="pb-3 font-medium">Identité</th>
                      <th className="pb-3 font-medium">Créée</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((org) => (
                      <tr
                        key={org.id}
                        className={cn(
                          "cursor-pointer border-t border-border",
                          selected?.id === org.id && "bg-muted/60",
                        )}
                        onClick={() => setSelectedId(org.id)}
                      >
                        <td className="py-3">
                          <div className="font-medium">{org.name}</div>
                          <div className="text-xs text-muted-foreground">{org.slug}</div>
                        </td>
                        <td className="py-3">
                          <div className="flex flex-wrap gap-1">
                            <Pill>{org.type_label}</Pill>
                            <Pill tone={org.is_demo ? "muted" : "ok"}>{org.is_demo ? "Démo" : "Client"}</Pill>
                          </div>
                        </td>
                        <td className="py-3">{org.company_count}</td>
                        <td className="py-3">{org.member_count}</td>
                        <td className="py-3">
                          <Pill tone={org.identity_complete ? "ok" : "warn"}>
                            {org.identity_complete ? "Complète" : "À renseigner"}
                          </Pill>
                        </td>
                        <td className="py-3 text-muted-foreground">{formatWhen(org.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>

          {selected && <OrgDetail org={selected} />}
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardContent className="pt-5">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="mt-1 font-serif text-3xl">{value}</p>
      </CardContent>
    </Card>
  );
}

function OrgDetail({ org }: { org: TenantOrg }) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>{org.name}</CardTitle>
          <CardDescription>
            {org.type_label} · {org.is_demo ? "sandbox démo" : "dossier client"} · slug {org.slug}
            {org.setup_data ? ` · init ${org.setup_data}` : ""}
          </CardDescription>
        </CardHeader>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Sociétés</CardTitle>
          <CardDescription>Identité reprise sur la liasse : RCCM, NIF, pays, devise, dirigeants.</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {org.companies.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune société.</p>
          ) : (
            <div className="space-y-4">
              {org.companies.map((company) => (
                <div key={company.id} className="rounded-lg border border-border p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="font-medium">{company.legal_name || company.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {company.country_label} · {company.currency_code} · {company.accounting_regime_label}
                        {company.city ? ` · ${company.city}` : ""}
                      </p>
                    </div>
                    <Pill tone={company.identity_complete ? "ok" : "warn"}>
                      {company.identity_complete ? "Identité complète" : "Identité incomplète"}
                    </Pill>
                  </div>
                  <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
                    <Info label="RCCM" value={company.rccm} />
                    <Info label="NIF" value={company.tax_id} />
                    <Info label="Forme" value={company.legal_form_label} />
                    <Info label="Régime fiscal" value={company.tax_regime_label} />
                    <Info label="Activité" value={company.activity_label} />
                    <Info label="Adresse" value={company.address} />
                  </dl>
                  <p className="mt-3 text-xs text-muted-foreground">
                    Dirigeants :{" "}
                    {company.officers.length
                      ? company.officers.map((officer) => `${officer.full_name} (${officer.role_label})`).join(", ")
                      : "aucun"}
                  </p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Membres</CardTitle>
          <CardDescription>Comptes ayant accès à ce dossier dans l’ERP.</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {org.members.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucun membre.</p>
          ) : (
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="pb-3 font-medium">Utilisateur</th>
                  <th className="pb-3 font-medium">Rôle</th>
                  <th className="pb-3 font-medium">Statut</th>
                  <th className="pb-3 font-medium">Dernière connexion</th>
                </tr>
              </thead>
              <tbody>
                {org.members.map((member) => (
                  <tr key={member.id} className="border-t border-border">
                    <td className="py-3">
                      <div className="font-medium">{member.full_name || member.email}</div>
                      <div className="text-xs text-muted-foreground">{member.email}</div>
                    </td>
                    <td className="py-3">{member.role_label}</td>
                    <td className="py-3">{member.is_active ? "Actif" : "Inactif"}</td>
                    <td className="py-3 text-muted-foreground">{formatWhen(member.last_login)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd>{value || "—"}</dd>
    </div>
  );
}
