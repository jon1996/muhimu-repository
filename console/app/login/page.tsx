"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError, clearCsrf } from "@/lib/api";
import type { StaffMe } from "@/lib/types";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState(
    process.env.NEXT_PUBLIC_DEV_PREFILL === "1" ? "ops@muhimu.local" : "",
  );
  const [password, setPassword] = useState(
    process.env.NEXT_PUBLIC_DEV_PREFILL === "1" ? "Ops1234!" : "",
  );

  const login = useMutation({
    mutationFn: () =>
      api<StaffMe>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    onSuccess: () => {
      clearCsrf();
      router.replace("/console");
    },
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(10,102,255,0.16),_transparent_55%)]" />
      <Card className="relative w-full max-w-md">
        <CardHeader>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary">Muhimu</p>
          <CardTitle className="font-serif text-3xl">Console SaaS</CardTitle>
          <CardDescription>
            Administration interne — séparée de l&apos;ERP. Réservée à l&apos;équipe Muhimu.
          </CardDescription>
        </CardHeader>
        <CardContent>
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
                placeholder={process.env.NEXT_PUBLIC_DEV_PREFILL === "1" ? undefined : "jp@muhimu.tech"}
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
            <Button className="w-full" size="lg" type="submit" disabled={login.isPending} suppressHydrationWarning>
              {login.isPending ? "Connexion…" : "Entrer"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
