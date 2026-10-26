"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { currencyForCountry, OHADA_COUNTRIES } from "@/lib/ohada";
import type { Me, Membership, Organization, OrganizationType } from "@/lib/types";
import { ROLE_LABELS } from "@/lib/types";

type OrgSetupResult = {
  slug: string;
  setup_data: string;
};

const SELECT_CLASS =
  "h-10 w-full rounded-md border border-input bg-card px-3 text-sm text-foreground";

function OrgOnboarding() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const requestedSlug = searchParams.get("org") ?? "";
  const wantCreate = searchParams.get("create") === "1";
  const [selected, setSelected] = useState<Membership | null>(null);
  const [creating, setCreating] = useState(wantCreate);
  const [orgType, setOrgType] = useState<OrganizationType>("sme");
  const [orgName, setOrgName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [legalName, setLegalName] = useState("");
  const [country, setCountry] = useState("CI");
  const ignoreOrgQuery = useRef(false);

  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api<Me>("/api/auth/me"),
  });

  useEffect(() => {
    if (me.error instanceof ApiError && me.error.status === 401) {
      router.replace("/login");
    }
  }, [me.error, router]);

  const memberships = me.data?.memberships ?? [];

  useEffect(() => {
    if (!memberships.length || selected || creating || ignoreOrgQuery.current) return;
    const fromQuery = memberships.find((item) => item.organization.slug === requestedSlug);
    if (fromQuery) {
      if (fromQuery.organization.setup_data) {
        router.replace(`/app/${fromQuery.organization.slug}`);
        return;
      }
      setSelected(fromQuery);
    }
  }, [memberships, requestedSlug, router, selected, creating]);

  const goBackToList = () => {
    ignoreOrgQuery.current = true;
    setSelected(null);
    setCreating(false);
    router.replace("/app");
  };

  const canWrite = ["owner", "admin", "accountant"].includes(selected?.role ?? "");
  const typeLabel = selected?.organization.type === "cabinet" ? "cabinet" : "PME";
  const sandboxSelected = Boolean(selected?.organization.is_demo);

  const setup = useMutation({
    mutationFn: (withDemo: boolean) =>
      api<OrgSetupResult>("/api/ledger/setup-organization", {
        method: "POST",
        orgSlug: selected?.organization.slug,
        body: JSON.stringify({ with_demo: withDemo }),
      }),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["me"] });
      queryClient.invalidateQueries({ queryKey: ["companies"] });
      queryClient.invalidateQueries({ queryKey: ["ledger-status"] });
      router.replace(`/app/${result.slug}`);
    },
  });

  const createOwn = useMutation({
    mutationFn: () =>
      api<Organization>("/api/organizations/own", {
        method: "POST",
        body: JSON.stringify({
          type: orgType,
          name: orgName,
          company_name: companyName,
          legal_name: legalName,
          country_code: country,
          currency_code: currencyForCountry(country),
        }),
      }),
    onSuccess: (org) => {
      queryClient.invalidateQueries({ queryKey: ["me"] });
      router.replace(`/app/${org.slug}/organisation`);
    },
  });

  const pickType = (membership: Membership) => {
    if (membership.organization.setup_data) {
      router.push(`/app/${membership.organization.slug}`);
      return;
    }
    setSelected(membership);
  };

  const demoHint = useMemo(() => {
    if (selected?.organization.type === "cabinet") {
      return "Écritures, tiers et une immobilisation pour chaque société du cabinet.";
    }
    return "Capital, ventes, achats, banque, caisse, deux tiers et une immobilisation.";
  }, [selected]);

  if (me.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Chargement des organisations…
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-background px-6 py-16">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(10,102,255,0.28),_transparent_55%)]" />
      <div className="relative mx-auto w-full max-w-3xl">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary">Muhimu</p>

        {!selected && !creating && (
          <>
            <h1 className="mt-3 font-serif text-4xl">Choisir un dossier</h1>
            <p className="mt-2 text-muted-foreground">
              Créez votre entreprise et saisissez vos informations, ou ouvrez un dossier déjà
              disponible.
            </p>
            <div className="mt-8 grid gap-4">
              <button type="button" onClick={() => setCreating(true)} className="text-left">
                <Card className="border-primary/40 transition-colors hover:border-primary hover:bg-muted/40">
                  <CardHeader>
                    <div className="flex items-center justify-between gap-3">
                      <CardTitle>Créer mon entreprise</CardTitle>
                      <Badge>Nouveau</Badge>
                    </div>
                    <CardDescription>
                      PME ou cabinet à zéro. Vous renseignez l’identité, le RCCM, les dirigeants.
                    </CardDescription>
                  </CardHeader>
                </Card>
              </button>
              {memberships.map((membership) => (
                <button
                  key={membership.id}
                  type="button"
                  onClick={() => pickType(membership)}
                  className="text-left"
                >
                  <Card className="transition-colors hover:border-primary/40 hover:bg-muted/40">
                    <CardHeader>
                      <div className="flex items-center justify-between gap-3">
                        <CardTitle>{membership.organization.name}</CardTitle>
                        <Badge>
                          {membership.organization.type === "cabinet" ? "Cabinet" : "PME"}
                        </Badge>
                      </div>
                      <CardDescription>{ROLE_LABELS[membership.role]}</CardDescription>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground">
                      {membership.organization.setup_data
                        ? "Ouvrir le tableau de bord."
                        : "Initialiser le dossier, puis accéder au tableau de bord."}
                    </CardContent>
                  </Card>
                </button>
              ))}
            </div>
          </>
        )}

        {creating && (
          <>
            <h1 className="mt-3 font-serif text-4xl">Nouvelle entreprise</h1>
            <p className="mt-2 text-muted-foreground">
              Dossier vide. Les détails (RCCM, impôts, dirigeants) se complètent ensuite.
            </p>
            <form
              className="mt-8 space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                createOwn.mutate();
              }}
            >
              <div className="flex gap-3">
                <Button
                  type="button"
                  variant={orgType === "sme" ? "default" : "outline"}
                  onClick={() => setOrgType("sme")}
                >
                  PME
                </Button>
                <Button
                  type="button"
                  variant={orgType === "cabinet" ? "default" : "outline"}
                  onClick={() => setOrgType("cabinet")}
                >
                  Cabinet
                </Button>
              </div>
              <div className="space-y-2">
                <Label htmlFor="orgName">
                  {orgType === "cabinet" ? "Nom du cabinet" : "Nom de l’organisation"}
                </Label>
                <Input
                  id="orgName"
                  value={orgName}
                  onChange={(event) => setOrgName(event.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="companyName">Nom de la société</Label>
                <Input
                  id="companyName"
                  value={companyName}
                  onChange={(event) => setCompanyName(event.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="legalName">Raison sociale (optionnel)</Label>
                <Input
                  id="legalName"
                  value={legalName}
                  onChange={(event) => setLegalName(event.target.value)}
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="country">Pays</Label>
                  <select
                    id="country"
                    className={SELECT_CLASS}
                    value={country}
                    onChange={(event) => setCountry(event.target.value)}
                  >
                    {OHADA_COUNTRIES.map((item) => (
                      <option key={item.code} value={item.code}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="currency">Devise de tenue</Label>
                  <Input id="currency" value={currencyForCountry(country)} readOnly />
                  <p className="text-xs text-muted-foreground">
                    Fixée par le pays : franc CFA UEMOA (XOF), CEMAC (XAF), Comores (KMF),
                    RDC (CDF) ou Guinée (GNF).
                  </p>
                </div>
              </div>
              {createOwn.isError && (
                <p className="text-sm text-destructive">
                  {createOwn.error instanceof ApiError
                    ? createOwn.error.message
                    : "Impossible de créer le dossier."}
                </p>
              )}
              <div className="flex items-center gap-4">
                <Button type="submit" disabled={createOwn.isPending}>
                  {createOwn.isPending ? "Création…" : "Créer et renseigner l’identité"}
                </Button>
                <button
                  type="button"
                  className="text-sm text-muted-foreground hover:text-foreground"
                  onClick={goBackToList}
                >
                  ← Retour
                </button>
              </div>
            </form>
          </>
        )}

        {selected && (
          <>
            <p className="mt-3 text-sm text-muted-foreground">
              Type sélectionné :{" "}
              <span className="font-medium text-foreground">{typeLabel}</span>
              {" · "}
              {selected.organization.name}
            </p>
            <h1 className="mt-1 font-serif text-4xl">Comment commencer ?</h1>
            <p className="mt-2 text-muted-foreground">
              {sandboxSelected
                ? "Cette question n’est posée qu’une fois, avant le tableau de bord."
                : "Votre dossier personnel démarre toujours vide."}
            </p>
            <div className="mt-8 grid gap-4 md:grid-cols-2">
              <button
                type="button"
                disabled={setup.isPending || !canWrite}
                onClick={() => setup.mutate(false)}
                className="text-left disabled:opacity-50"
              >
                <Card className="h-full transition-colors hover:border-primary/40 hover:bg-muted/40">
                  <CardHeader>
                    <CardTitle>Dossier vide</CardTitle>
                    <CardDescription>
                      Plan SYSCOHADA, journaux et exercice, sans écriture ni tiers.
                    </CardDescription>
                  </CardHeader>
                </Card>
              </button>
              {sandboxSelected && (
                <button
                  type="button"
                  disabled={setup.isPending || !canWrite}
                  onClick={() => setup.mutate(true)}
                  className="text-left disabled:opacity-50"
                >
                  <Card className="h-full transition-colors hover:border-primary/40 hover:bg-muted/40">
                    <CardHeader>
                      <CardTitle>Écritures d&apos;exemple</CardTitle>
                      <CardDescription>{demoHint}</CardDescription>
                    </CardHeader>
                  </Card>
                </button>
              )}
            </div>
            <button
              type="button"
              className="mt-6 text-sm text-muted-foreground hover:text-foreground"
              onClick={goBackToList}
            >
              ← Changer de dossier
            </button>
            {setup.isPending && <p className="mt-4 text-sm text-muted-foreground">Initialisation…</p>}
            {setup.isError && (
              <p className="mt-4 text-sm text-destructive">
                {setup.error instanceof ApiError
                  ? setup.error.message
                  : "Impossible d’initialiser le dossier."}
              </p>
            )}
            {!canWrite && (
              <p className="mt-4 text-sm text-muted-foreground">
                Seul un propriétaire, administrateur ou comptable peut initialiser le dossier.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default function OrgPickerPage() {
  return (
    <Suspense fallback={<p className="p-10 text-muted-foreground">Chargement des organisations…</p>}>
      <OrgOnboarding />
    </Suspense>
  );
}
