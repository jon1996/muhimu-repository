"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError, clearCsrf } from "@/lib/api";
import type { Me } from "@/lib/types";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionMessage = searchParams.get("message");
  const [email, setEmail] = useState(
    process.env.NEXT_PUBLIC_DEV_PREFILL === "1" ? "demo@muhimu.local" : "",
  );
  const [password, setPassword] = useState(
    process.env.NEXT_PUBLIC_DEV_PREFILL === "1" ? "Demo1234!" : "",
  );

  const login = useMutation({
    mutationFn: () =>
      api<Me>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    onSuccess: () => {
      clearCsrf();
      router.replace("/app");
    },
  });

  return (
    <Card className="relative w-full max-w-md border-border bg-card">
      <CardHeader>
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary">Muhimu</p>
        <CardTitle className="font-serif text-3xl">ERP</CardTitle>
        <CardDescription>
          Comptabilité &amp; FinTech — référentiel SYSCOHADA. Bêta privée : données fictives uniquement,
          états non certifiés.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {sessionMessage ? (
          <p className="mb-4 rounded-md border border-border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
            {sessionMessage}
          </p>
        ) : null}
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            login.mutate();
          }}
        >
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder={process.env.NEXT_PUBLIC_DEV_PREFILL === "1" ? undefined : "vous@entreprise.com"}
              required
              suppressHydrationWarning
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Mot de passe</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              suppressHydrationWarning
            />
          </div>
          {login.isError && (
            <p className="text-sm text-destructive">
              {login.error instanceof ApiError ? login.error.message : "Connexion impossible."}
            </p>
          )}
          <Button
            className="w-full"
            size="lg"
            type="submit"
            disabled={login.isPending}
            suppressHydrationWarning
          >
            {login.isPending ? "Connexion…" : "Entrer"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

export default function LoginPage() {
  return (
    <div className="relative flex min-h-screen items-center justify-center bg-background px-4">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(10,102,255,0.28),_transparent_55%)]" />
      <Suspense
        fallback={
          <Card className="relative w-full max-w-md border-border bg-card p-8 text-sm text-muted-foreground">
            Chargement…
          </Card>
        }
      >
        <LoginForm />
      </Suspense>
    </div>
  );
}
