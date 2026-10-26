"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import type { MailStatus, MailTestResult, StaffMe } from "@/lib/types";

function modeLabel(mode: string) {
  if (mode === "smtp") return "SMTP PrivateMail";
  if (mode === "console") return "Console (logs Docker)";
  if (mode === "test") return "Test (mémoire)";
  return mode;
}

export default function EmailsPage() {
  const me = useQuery({
    queryKey: ["platform-me"],
    queryFn: () => api<StaffMe>("/api/auth/me"),
  });
  const status = useQuery({
    queryKey: ["mail-status"],
    queryFn: () => api<MailStatus>("/api/mail/status"),
  });
  const [to, setTo] = useState("");
  const [result, setResult] = useState<MailTestResult | null>(null);

  const sendTest = useMutation({
    mutationFn: () =>
      api<MailTestResult>("/api/mail/test", {
        method: "POST",
        body: JSON.stringify({ to: to.trim() }),
      }),
    onSuccess: (payload) => setResult(payload),
  });

  const data = status.data;

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="font-serif text-3xl">E-mails</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Envoi via Namecheap Private Email (<code>mail.privateemail.com</code>).
        </p>
      </div>

      {status.isPending && <p className="text-sm text-muted-foreground">Chargement de la configuration…</p>}
      {status.isError && (
        <p className="text-sm text-destructive">
          {status.error instanceof ApiError ? status.error.message : "Impossible de lire le SMTP."}
        </p>
      )}

      {data && (
        <>
          <Card className={data.configured ? "border-primary/40" : ""}>
            <CardHeader>
              <CardTitle>{data.configured ? "SMTP prêt" : "SMTP à renseigner"}</CardTitle>
              <CardDescription>
                {data.configured
                  ? "Les invitations démo et les tests partent par PrivateMail."
                  : "Sans boîte ni mot de passe d’application, les mails s’écrivent dans les logs du service platform."}
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm sm:grid-cols-2">
              <Info label="Fournisseur" value={data.provider} />
              <Info label="Mode" value={modeLabel(data.mode)} />
              <Info label="Serveur" value={`${data.host}:${data.port}`} />
              <Info
                label="Chiffrement"
                value={data.use_ssl ? "SSL (465)" : data.use_tls ? "STARTTLS (587)" : "Aucun"}
              />
              <Info label="Boîte" value={data.username || "—"} />
              <Info label="Expéditeur" value={data.from_email} />
              <Info label="Mot de passe" value={data.password_set ? "Renseigné" : "Manquant"} />
            </CardContent>
          </Card>

          {!data.configured && (
            <Card>
              <CardHeader>
                <CardTitle>À coller dans .env</CardTitle>
                <CardDescription>
                  Mot de passe d’application : Private Email → Security Center → App passwords. Puis
                  redémarrer <code>platform</code>.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="overflow-x-auto rounded-lg bg-muted p-4 text-xs leading-6">
{`EMAIL_HOST=mail.privateemail.com
EMAIL_PORT=465
EMAIL_USE_SSL=1
EMAIL_HOST_USER=jp@muhimu.tech
EMAIL_HOST_PASSWORD=mot-de-passe-application
DEFAULT_FROM_EMAIL=Muhimu <jp@muhimu.tech>`}
                </pre>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Envoyer un test</CardTitle>
              <CardDescription>
                Vérifie que PrivateMail accepte l’authentification SMTP. Laissez vide pour vous écrire à vous-même.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form
                className="flex flex-col gap-4 sm:flex-row sm:items-end"
                onSubmit={(event) => {
                  event.preventDefault();
                  setResult(null);
                  sendTest.mutate();
                }}
              >
                <div className="min-w-0 flex-1 space-y-2">
                  <Label htmlFor="to">Destinataire</Label>
                  <Input
                    id="to"
                    type="email"
                    value={to}
                    onChange={(event) => setTo(event.target.value)}
                    placeholder={me.data?.user.email || "vous@domaine"}
                  />
                </div>
                <Button type="submit" disabled={sendTest.isPending}>
                  {sendTest.isPending ? "Envoi…" : "Envoyer le test"}
                </Button>
              </form>
              {sendTest.isError && (
                <p className="mt-3 text-sm text-destructive">
                  {sendTest.error instanceof ApiError
                    ? sendTest.error.message
                    : "Envoi impossible."}
                </p>
              )}
              {result && (
                <p className="mt-3 text-sm">
                  {result.message} Destinataire : <strong>{result.to}</strong>
                </p>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-0.5 break-all">{value}</p>
    </div>
  );
}
