"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { useTenant } from "@/components/tenant-context";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { JournalEntry, LedgerStatus } from "@/lib/types";

export default function DashboardPage() {
  const { membership, activeCompany, companies, orgSlug, companyId } = useTenant();
  const status = useQuery({
    queryKey: ["ledger-status", orgSlug, companyId],
    queryFn: () => api<LedgerStatus>("/api/ledger/status", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const entries = useQuery({
    queryKey: ["entries", orgSlug, companyId],
    queryFn: () => api<JournalEntry[]>("/api/ledger/entries", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId && status.data?.ready),
  });

  const recent = (entries.data ?? []).slice(0, 6);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl">Tableau de bord</h1>
        <p className="mt-1 text-muted-foreground">
          Comptabilité SYSCOHADA — exercice civil, partie double, écritures validées immuables.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardDescription>Organisation</CardDescription>
            <CardTitle>{membership?.organization.name ?? "—"}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Type {membership?.organization.type === "cabinet" ? "cabinet" : "PME"} · {companies.length}{" "}
            société(s)
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Société active</CardDescription>
            <CardTitle>{activeCompany?.name ?? "Aucune"}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            {activeCompany
              ? `${activeCompany.country_code} · ${activeCompany.currency_code}`
              : "Choisissez une société dans la barre."}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Exercice</CardDescription>
            <CardTitle>
              {status.data?.exercise ? `${status.data.exercise.year}` : "Non initialisé"}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            {status.data?.current_period
              ? `Période ${String(status.data.current_period.month).padStart(2, "0")} · ${status.data.accounts} comptes`
              : "Le plan PCGO n’est pas encore copié."}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Dernières écritures</CardTitle>
            <CardDescription>Livre-journal de la société active.</CardDescription>
          </div>
          <div className="flex gap-2">
            <Link href={`/app/${orgSlug}/etats`} className={buttonVariants({ size: "sm", variant: "outline" })}>
              États
            </Link>
            <Link href={`/app/${orgSlug}/journal/nouveau`} className={buttonVariants({ size: "sm" })}>
              Nouvelle pièce
            </Link>
          </div>
        </CardHeader>
        <CardContent>
          {recent.length === 0 && (
            <p className="text-sm text-muted-foreground">Aucune écriture pour l’instant.</p>
          )}
          <ul className="divide-y divide-border">
            {recent.map((entry) => (
              <li key={entry.id} className="flex items-center justify-between py-2 text-sm">
                <Link href={`/app/${orgSlug}/journal/${entry.id}`} className="hover:underline">
                  <span className="font-medium">{entry.number_display || "Brouillon"}</span>
                  <span className="ml-2 text-muted-foreground">{entry.description}</span>
                </Link>
                <span className="text-muted-foreground">
                  {entry.journal_code} · {entry.status === "posted" ? "Validée" : "Brouillon"}
                </span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
