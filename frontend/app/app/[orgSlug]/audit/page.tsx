"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatInstant } from "@/lib/dates";
import type { AuditLog } from "@/lib/types";

export default function AuditPage() {
  const { orgSlug } = useParams<{ orgSlug: string }>();
  const logs = useQuery({
    queryKey: ["audit", orgSlug],
    queryFn: () => api<AuditLog[]>("/api/audit-logs?limit=50", { orgSlug }),
    enabled: Boolean(orgSlug),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl">Journal d’audit</h1>
        <p className="mt-1 text-muted-foreground">
          Traçabilité des actions (connexion, création de société, attributions). Réservé aux
          administrateurs et auditeurs.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Événements récents</CardTitle>
          <CardDescription>Les 50 derniers événements de l’organisation.</CardDescription>
        </CardHeader>
        <CardContent>
          {logs.isError && (
            <p className="text-sm text-destructive">Accès refusé ou journal indisponible.</p>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-muted-foreground">
                <tr>
                  <th className="py-2 pr-4 font-medium">Date</th>
                  <th className="py-2 pr-4 font-medium">Action</th>
                  <th className="py-2 pr-4 font-medium">Acteur</th>
                  <th className="py-2 font-medium">Ressource</th>
                </tr>
              </thead>
              <tbody>
                {(logs.data ?? []).map((log) => (
                  <tr key={log.id} className="border-b border-border/70">
                    <td className="py-2 pr-4 whitespace-nowrap">
                      {formatInstant(log.created_at)}
                    </td>
                    <td className="py-2 pr-4 font-mono text-xs">{log.action}</td>
                    <td className="py-2 pr-4">{log.actor_email ?? "—"}</td>
                    <td className="py-2 text-muted-foreground">
                      {log.resource_type}
                      {log.resource_id ? ` · ${log.resource_id.slice(0, 8)}` : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {logs.isSuccess && logs.data.length === 0 && (
              <p className="py-6 text-sm text-muted-foreground">Aucun événement pour l’instant.</p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
