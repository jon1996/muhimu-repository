"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import type { DemoGrant } from "@/lib/types";

function scopes(grant: DemoGrant) {
  const parts: string[] = [];
  if (grant.access_pme) parts.push("PME");
  if (grant.access_cabinet) parts.push("Cabinet");
  return parts.join(" · ") || "—";
}

function formatWhen(value: string | null) {
  if (!value) return "Jamais";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("fr-FR");
}

export default function DemoAccessPage() {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [accessPme, setAccessPme] = useState(true);
  const [accessCabinet, setAccessCabinet] = useState(true);
  const [notes, setNotes] = useState("");
  const [issued, setIssued] = useState<DemoGrant | null>(null);

  const grants = useQuery({
    queryKey: ["demo-grants"],
    queryFn: () => api<DemoGrant[]>("/api/demo/grants"),
  });

  const invite = useMutation({
    mutationFn: () =>
      api<DemoGrant>("/api/demo/grants", {
        method: "POST",
        body: JSON.stringify({
          email,
          full_name: fullName,
          access_pme: accessPme,
          access_cabinet: accessCabinet,
          notes,
          send_email: true,
        }),
      }),
    onSuccess: (grant) => {
      setIssued(grant);
      setEmail("");
      setFullName("");
      setNotes("");
      queryClient.invalidateQueries({ queryKey: ["demo-grants"] });
    },
  });

  const resend = useMutation({
    mutationFn: (id: string) => api<DemoGrant>(`/api/demo/grants/${id}/resend`, { method: "POST" }),
    onSuccess: (grant) => {
      setIssued(grant);
      queryClient.invalidateQueries({ queryKey: ["demo-grants"] });
    },
  });

  const revoke = useMutation({
    mutationFn: (id: string) => api<DemoGrant>(`/api/demo/grants/${id}/revoke`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["demo-grants"] });
    },
  });

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <div>
        <h1 className="font-serif text-3xl">Accès démo</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Choisissez qui peut ouvrir les dossiers sandbox de l&apos;ERP, puis envoyez les identifiants par e-mail.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Inviter un utilisateur</CardTitle>
          <CardDescription>
            Un mot de passe temporaire est généré et envoyé. L&apos;ERP (port 3001) reste distinct de cette console.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-4 md:grid-cols-2"
            onSubmit={(event) => {
              event.preventDefault();
              invite.mutate();
            }}
          >
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="fullName">Nom</Label>
              <Input
                id="fullName"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                placeholder="Optionnel"
              />
            </div>
            <div className="flex items-center gap-6 md:col-span-2">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={accessPme}
                  onChange={(event) => setAccessPme(event.target.checked)}
                />
                Accès PME démo
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={accessCabinet}
                  onChange={(event) => setAccessCabinet(event.target.checked)}
                />
                Accès cabinet démo
              </label>
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="notes">Note interne</Label>
              <Input
                id="notes"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="Prospect salon, partenaire…"
              />
            </div>
            {invite.isError && (
              <p className="text-sm text-destructive md:col-span-2">
                {invite.error instanceof ApiError ? invite.error.message : "Invitation impossible."}
              </p>
            )}
            <div className="md:col-span-2">
              <Button type="submit" disabled={invite.isPending || (!accessPme && !accessCabinet)}>
                {invite.isPending ? "Envoi…" : "Créer l'accès et envoyer le mail"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {issued?.temporary_password && (
        <Card className="border-primary/40">
          <CardContent className="pt-6 text-sm">
            Accès créé pour <strong>{issued.email}</strong>. Mot de passe temporaire :{" "}
            <code className="rounded bg-muted px-1.5 py-0.5">{issued.temporary_password}</code>
            {issued.email_sent ? (
              <span className="mt-2 block text-muted-foreground">E-mail envoyé.</span>
            ) : issued.email_error ? (
              <span className="mt-2 block text-destructive">E-mail non envoyé : {issued.email_error}</span>
            ) : null}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Utilisateurs autorisés</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {grants.isPending && <p className="text-sm text-muted-foreground">Chargement…</p>}
          {grants.isError && (
            <p className="text-sm text-destructive">
              {grants.error instanceof ApiError ? grants.error.message : "Impossible de charger les accès."}
            </p>
          )}
          {grants.data && grants.data.length === 0 && (
            <p className="text-sm text-muted-foreground">Aucun accès démo pour le moment.</p>
          )}
          {grants.data && grants.data.length > 0 && (
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="pb-3 font-medium">Utilisateur</th>
                  <th className="pb-3 font-medium">Dossiers</th>
                  <th className="pb-3 font-medium">Statut</th>
                  <th className="pb-3 font-medium">Dernier mail</th>
                  <th className="pb-3 font-medium" />
                </tr>
              </thead>
              <tbody>
                {grants.data.map((grant) => (
                  <tr key={grant.id} className="border-t border-border">
                    <td className="py-3">
                      <div className="font-medium">{grant.full_name || grant.email}</div>
                      <div className="text-xs text-muted-foreground">{grant.email}</div>
                    </td>
                    <td className="py-3">{scopes(grant)}</td>
                    <td className="py-3">{grant.is_active ? "Actif" : "Révoqué"}</td>
                    <td className="py-3 text-muted-foreground">{formatWhen(grant.last_emailed_at)}</td>
                    <td className="py-3 text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={resend.isPending}
                          onClick={() => resend.mutate(grant.id)}
                        >
                          Renvoyer
                        </Button>
                        {grant.is_active && (
                          <Button
                            size="sm"
                            variant="destructive"
                            disabled={revoke.isPending}
                            onClick={() => revoke.mutate(grant.id)}
                          >
                            Révoquer
                          </Button>
                        )}
                      </div>
                    </td>
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
