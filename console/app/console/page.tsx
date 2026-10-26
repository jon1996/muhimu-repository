"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { BarChart, DonutChart, HBarChart } from "@/components/charts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import type { Dashboard } from "@/lib/types";

function formatWhen(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("fr-FR");
}

export default function DashboardPage() {
  const dashboard = useQuery({
    queryKey: ["platform-dashboard"],
    queryFn: () => api<Dashboard>("/api/dashboard"),
  });

  if (dashboard.isPending) {
    return <p className="text-sm text-muted-foreground">Chargement du tableau de bord…</p>;
  }
  if (dashboard.isError) {
    return (
      <p className="text-sm text-destructive">
        {dashboard.error instanceof ApiError
          ? dashboard.error.message
          : "Impossible de charger les indicateurs."}
      </p>
    );
  }

  const data = dashboard.data;
  const k = data.kpis;

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <div>
        <h1 className="font-serif text-3xl">Tableau de bord</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Vue SaaS : dossiers, usage ERP, identités SYSCOHADA et accès démo.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="Dossiers clients" value={k.client_count} hint={`${k.demo_count} démo`} />
        <Kpi label="Sociétés" value={k.company_count} hint={`${k.identity_rate} % identité complète`} />
        <Kpi label="Utilisateurs ERP" value={k.user_count} hint={`${k.users_active_7d} actifs / 7 j`} />
        <Kpi
          label="Écritures validées"
          value={k.entries_posted}
          hint={`${k.entries_draft} brouillons`}
        />
        <Kpi label="Grants démo" value={k.grants_active} hint="accès sandbox ouverts" />
        <Kpi label="Identités à renseigner" value={k.identity_incomplete} hint="sociétés incomplètes" />
        <Kpi label="Jamais connectés" value={k.users_never} hint="comptes ERP sans login" />
        <Kpi label="Dossiers totaux" value={k.org_count} hint={`${k.client_count} clients · ${k.demo_count} démo`} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Nouveaux dossiers</CardTitle>
            <CardDescription>Organisations créées, 8 dernières semaines</CardDescription>
          </CardHeader>
          <CardContent>
            <BarChart items={data.orgs_by_week} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Nouveaux utilisateurs ERP</CardTitle>
            <CardDescription>Comptes hors équipe Muhimu, 8 dernières semaines</CardDescription>
          </CardHeader>
          <CardContent>
            <BarChart items={data.users_by_week} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>PME / cabinets</CardTitle>
          </CardHeader>
          <CardContent>
            <DonutChart items={data.by_type} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Clients / démo</CardTitle>
          </CardHeader>
          <CardContent>
            <DonutChart items={data.by_kind} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Identité SYSCOHADA</CardTitle>
            <CardDescription>Sociétés avec RCCM, NIF, forme et dirigeant</CardDescription>
          </CardHeader>
          <CardContent>
            <DonutChart items={data.by_identity} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Sociétés par pays</CardTitle>
          </CardHeader>
          <CardContent>
            <HBarChart items={data.by_country} />
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>À surveiller</CardTitle>
            <CardDescription>Dossiers clients sans identité complète</CardDescription>
          </CardHeader>
          <CardContent>
            {data.watch.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucun dossier client en attente.</p>
            ) : (
              <ul className="space-y-3 text-sm">
                {data.watch.map((item) => (
                  <li key={item.id} className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-medium">{item.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {item.type_label} · {item.reason}
                      </p>
                    </div>
                    <Link className="text-xs text-primary underline" href="/console/organisations">
                      Voir
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Derniers dossiers</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3 text-sm">
              {data.recent.map((item) => (
                <li key={item.id} className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-medium">{item.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {item.type_label} · {item.is_demo ? "démo" : "client"} · {formatWhen(item.created_at)}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Kpi({ label, value, hint }: { label: string; value: number; hint: string }) {
  return (
    <Card>
      <CardContent className="pt-5">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="mt-1 font-serif text-3xl">{value}</p>
        <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
      </CardContent>
    </Card>
  );
}
