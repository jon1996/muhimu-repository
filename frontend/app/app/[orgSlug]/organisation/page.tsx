"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";

import { useTenant } from "@/components/tenant-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { IDENTITY_REQUIRED_LABELS } from "@/lib/identity";
import { OHADA_COUNTRIES } from "@/lib/ohada";
import type { Company, CompanyOfficer, SmtEligibility } from "@/lib/types";

const SMT_LIMITS = { trade: "60 millions", craft: "40 millions", services: "30 millions" };
const SELECT_CLASS = "h-10 w-full rounded-md border border-input bg-background px-3 text-sm";

const LEGAL_FORMS = [
  ["", "—"],
  ["sa", "SA"],
  ["sas", "SAS"],
  ["sarl", "SARL"],
  ["suarl", "SUARL"],
  ["snc", "SNC"],
  ["scs", "SCS"],
  ["gie", "GIE"],
  ["ets", "Entreprise individuelle"],
  ["coop", "Coopérative"],
  ["other", "Autre"],
] as const;

const TAX_REGIMES = [
  ["", "—"],
  ["reel_normal", "Réel normal"],
  ["reel_simplifie", "Réel simplifié"],
  ["synthetique", "Synthétique / unique"],
  ["exemption", "Exonéré"],
  ["other", "Autre"],
] as const;

const CONTROL_KINDS = [
  ["", "—"],
  ["private_national", "Privé national"],
  ["public", "Public"],
  ["private_foreign", "Privé étranger"],
] as const;

const OFFICER_ROLES = [
  ["manager", "Gérant"],
  ["chairman", "Président"],
  ["director", "Directeur général"],
  ["board", "Administrateur"],
  ["other", "Autre"],
] as const;

type IdentityForm = {
  legal_name: string;
  acronym: string;
  country_code: string;
  address: string;
  city: string;
  postal_code: string;
  phone: string;
  email: string;
  tax_id: string;
  rccm: string;
  social_register: string;
  legal_form: string;
  tax_regime: string;
  naema_code: string;
  control_kind: string;
  establishments_domestic: string;
  establishments_foreign: string;
  distinct_branch_accounts: boolean;
  auditor_name: string;
  auditor_order_no: string;
  signatory_name: string;
  signatory_title: string;
  banks: string;
};

function identityFrom(company: Company): IdentityForm {
  return {
    legal_name: company.legal_name ?? "",
    acronym: company.acronym ?? "",
    country_code: company.country_code ?? "CI",
    address: company.address ?? "",
    city: company.city ?? "",
    postal_code: company.postal_code ?? "",
    phone: company.phone ?? "",
    email: company.email ?? "",
    tax_id: company.tax_id ?? "",
    rccm: company.rccm ?? "",
    social_register: company.social_register ?? "",
    legal_form: company.legal_form ?? "",
    tax_regime: company.tax_regime ?? "",
    naema_code: company.naema_code ?? "",
    control_kind: company.control_kind ?? "",
    establishments_domestic: String(company.establishments_domestic ?? 1),
    establishments_foreign: String(company.establishments_foreign ?? 0),
    distinct_branch_accounts: Boolean(company.distinct_branch_accounts),
    auditor_name: company.auditor_name ?? "",
    auditor_order_no: company.auditor_order_no ?? "",
    signatory_name: company.signatory_name ?? "",
    signatory_title: company.signatory_title ?? "",
    banks: company.banks ?? "",
  };
}

const EMPTY_IDENTITY: IdentityForm = {
  legal_name: "",
  acronym: "",
  country_code: "CI",
  address: "",
  city: "",
  postal_code: "",
  phone: "",
  email: "",
  tax_id: "",
  rccm: "",
  social_register: "",
  legal_form: "",
  tax_regime: "",
  naema_code: "",
  control_kind: "",
  establishments_domestic: "1",
  establishments_foreign: "0",
  distinct_branch_accounts: false,
  auditor_name: "",
  auditor_order_no: "",
  signatory_name: "",
  signatory_title: "",
  banks: "",
};

export default function OrganizationPage() {
  const { orgSlug, companyId, activeCompany, membership } = useTenant();
  const canWrite = ["owner", "admin", "accountant"].includes(membership?.role ?? "");
  const queryClient = useQueryClient();
  const [regime, setRegime] = useState<"normal" | "smt">("normal");
  const [activity, setActivity] = useState<"trade" | "craft" | "services">("trade");
  const [manual, setManual] = useState("");
  const [goingConcern, setGoingConcern] = useState(true);
  const [identity, setIdentity] = useState<IdentityForm>(EMPTY_IDENTITY);
  const [officerName, setOfficerName] = useState("");
  const [officerRole, setOfficerRole] = useState("manager");
  const [officerNationality, setOfficerNationality] = useState("");
  const [message, setMessage] = useState("");
  const [identityMessage, setIdentityMessage] = useState("");
  const [officerMessage, setOfficerMessage] = useState("");

  useEffect(() => {
    if (!activeCompany) return;
    setRegime(activeCompany.accounting_regime ?? "normal");
    setActivity(activeCompany.activity_kind ?? "trade");
    setManual(activeCompany.procedure_manual ?? "");
    setGoingConcern(activeCompany.going_concern ?? true);
    setIdentity(identityFrom(activeCompany));
  }, [activeCompany]);

  const refreshCompanies = () => {
    queryClient.invalidateQueries({ queryKey: ["companies"] });
    queryClient.invalidateQueries({ queryKey: ["statements"] });
    queryClient.invalidateQueries({ queryKey: ["smt"] });
  };

  const smt = useQuery({
    queryKey: ["smt", orgSlug, companyId],
    queryFn: () => api<SmtEligibility>("/api/ledger/smt", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });

  const save = useMutation({
    mutationFn: () =>
      api<Company>(`/api/companies/${companyId}/settings`, {
        method: "PATCH",
        orgSlug,
        companyId,
        body: JSON.stringify({
          accounting_regime: regime,
          activity_kind: activity,
          procedure_manual: manual,
          going_concern: goingConcern,
        }),
      }),
    onSuccess: () => {
      setMessage("Organisation enregistrée.");
      refreshCompanies();
    },
    onError: (error) => {
      setMessage(error instanceof ApiError ? error.message : "Enregistrement impossible.");
    },
  });

  const saveIdentity = useMutation({
    mutationFn: () =>
      api<Company>(`/api/companies/${companyId}/settings`, {
        method: "PATCH",
        orgSlug,
        companyId,
        body: JSON.stringify({
          legal_name: identity.legal_name,
          acronym: identity.acronym,
          country_code: identity.country_code,
          address: identity.address,
          city: identity.city,
          postal_code: identity.postal_code,
          phone: identity.phone,
          email: identity.email,
          tax_id: identity.tax_id,
          rccm: identity.rccm,
          social_register: identity.social_register,
          legal_form: identity.legal_form,
          tax_regime: identity.tax_regime,
          naema_code: identity.naema_code,
          control_kind: identity.control_kind,
          establishments_domestic: Number(identity.establishments_domestic) || 0,
          establishments_foreign: Number(identity.establishments_foreign) || 0,
          distinct_branch_accounts: identity.distinct_branch_accounts,
          auditor_name: identity.auditor_name,
          auditor_order_no: identity.auditor_order_no,
          signatory_name: identity.signatory_name,
          signatory_title: identity.signatory_title,
          banks: identity.banks,
        }),
      }),
    onSuccess: () => {
      setIdentityMessage("Identité enregistrée (fiches R1–R2).");
      refreshCompanies();
    },
    onError: (error) => {
      setIdentityMessage(error instanceof ApiError ? error.message : "Enregistrement impossible.");
    },
  });

  const addOfficer = useMutation({
    mutationFn: () =>
      api<CompanyOfficer>(`/api/companies/${companyId}/officers`, {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({
          full_name: officerName,
          role: officerRole,
          nationality: officerNationality,
        }),
      }),
    onSuccess: () => {
      setOfficerName("");
      setOfficerNationality("");
      setOfficerMessage("Dirigeant ajouté.");
      refreshCompanies();
    },
    onError: (error) => {
      setOfficerMessage(error instanceof ApiError ? error.message : "Ajout impossible.");
    },
  });

  const removeOfficer = useMutation({
    mutationFn: (officerId: string) =>
      api(`/api/companies/${companyId}/officers/${officerId}`, {
        method: "DELETE",
        orgSlug,
        companyId,
      }),
    onSuccess: () => {
      setOfficerMessage("Dirigeant retiré.");
      refreshCompanies();
    },
    onError: (error) => {
      setOfficerMessage(error instanceof ApiError ? error.message : "Suppression impossible.");
    },
  });

  const setField = <K extends keyof IdentityForm>(key: K, value: IdentityForm[K]) => {
    setIdentity((current) => ({ ...current, [key]: value }));
  };

  const officers = activeCompany?.officers ?? [];
  const identityLocked = !membership?.organization.is_demo && activeCompany?.identity_complete === false;
  const missingLabels = (activeCompany?.identity_missing ?? []).map(
    (key) => IDENTITY_REQUIRED_LABELS[key] ?? key,
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl">Organisation comptable</h1>
        <p className="mt-1 max-w-2xl text-muted-foreground">
          Régime (art. 11–13), continuité d’exploitation (art. 39), manuel des procédures (art. 16)
          et identité de la liasse SYSCOHADA (fiches R1–R3).
        </p>
      </div>

      {identityLocked && (
        <Card className="border-primary/50">
          <CardHeader>
            <CardTitle>Identité à enregistrer</CardTitle>
            <CardDescription>
              Le journal, les états et les autres écrans restent fermés tant que ces informations
              ne sont pas enregistrées.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {missingLabels.map((label) => (
                <li key={label}>{label}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
      <Card>
        <CardHeader>
          <CardTitle>{activeCompany?.name ?? "Société"}</CardTitle>
          <CardDescription>
            Devise de tenue {activeCompany?.currency_code ?? "XOF"} (fixe à la création).
            {!identityLocked ? (
              <>
                {" "}
                Cours et réévaluation 478/479 :{" "}
                <Link className="underline" href={`/app/${orgSlug}/devises`}>
                  Devises
                </Link>
                .
              </>
            ) : null}{" "}
            SMT possible si le CA HT est inférieur à {SMT_LIMITS[activity]}{" "}
            {activeCompany?.currency_code ?? "XOF"}
            {smt.data
              ? ` · CA HT actuel ${formatMoney(smt.data.revenue, activeCompany?.currency_code ?? "XOF")} (seuil ${smt.data.threshold_label}).`
              : "."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Régime</Label>
              <select
                className={SELECT_CLASS}
                value={regime}
                disabled={!canWrite}
                onChange={(event) => setRegime(event.target.value as "normal" | "smt")}
              >
                <option value="normal">Système normal</option>
                <option value="smt">Système minimal de trésorerie</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>Activité</Label>
              <select
                className={SELECT_CLASS}
                value={activity}
                disabled={!canWrite}
                onChange={(event) => setActivity(event.target.value as "trade" | "craft" | "services")}
              >
                <option value="trade">Négoce (seuil 60 M)</option>
                <option value="craft">Artisanat (seuil 40 M)</option>
                <option value="services">Services (seuil 30 M)</option>
              </select>
            </div>
          </div>
          {smt.data?.warning && (
            <p className={smt.data.eligible ? "text-sm text-muted-foreground" : "text-sm text-destructive"}>
              {smt.data.warning}
            </p>
          )}
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={goingConcern}
              disabled={!canWrite}
              onChange={(event) => setGoingConcern(event.target.checked)}
            />
            Continuité d’exploitation
          </label>
          <div className="space-y-1.5">
            <Label>Manuel des procédures</Label>
            <textarea
              className="min-h-48 w-full rounded-md border border-input bg-background p-3 text-sm"
              value={manual}
              disabled={!canWrite}
              onChange={(event) => setManual(event.target.value)}
              placeholder="Classement des pièces, journaux auxiliaires, centralisation mensuelle, responsables…"
            />
          </div>
          {message && <p className="text-sm text-muted-foreground">{message}</p>}
          {canWrite && (
            <Button onClick={() => save.mutate()} disabled={save.isPending}>
              {save.isPending ? "Enregistrement…" : "Enregistrer"}
            </Button>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Identité (R1–R2)</CardTitle>
          <CardDescription>
            RCCM, NIF, forme, régime fiscal, établissements et signataires — repris sur chaque
            état et en note 36.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <Field label="Raison sociale" required>
              <Input
                value={identity.legal_name}
                disabled={!canWrite}
                onChange={(event) => setField("legal_name", event.target.value)}
              />
            </Field>
            <Field label="Sigle">
              <Input
                value={identity.acronym}
                disabled={!canWrite}
                onChange={(event) => setField("acronym", event.target.value)}
              />
            </Field>
            <Field label="Pays du siège" required>
              <select
                className={SELECT_CLASS}
                value={identity.country_code}
                disabled={!canWrite}
                onChange={(event) => setField("country_code", event.target.value)}
              >
                {OHADA_COUNTRIES.map((item) => (
                  <option key={item.code} value={item.code}>
                    {item.label} ({item.currency})
                  </option>
                ))}
              </select>
            </Field>
            <Field label="RCCM" required>
              <Input
                value={identity.rccm}
                disabled={!canWrite}
                onChange={(event) => setField("rccm", event.target.value)}
              />
            </Field>
            <Field label="NIF" required>
              <Input
                value={identity.tax_id}
                disabled={!canWrite}
                onChange={(event) => setField("tax_id", event.target.value)}
              />
            </Field>
            <Field label="Répertoire / CNPS">
              <Input
                value={identity.social_register}
                disabled={!canWrite}
                onChange={(event) => setField("social_register", event.target.value)}
              />
            </Field>
            <Field label="Forme juridique" required>
              <select
                className={SELECT_CLASS}
                value={identity.legal_form}
                disabled={!canWrite}
                onChange={(event) => setField("legal_form", event.target.value)}
              >
                {LEGAL_FORMS.map(([value, label]) => (
                  <option key={value || "empty"} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Régime fiscal" required>
              <select
                className={SELECT_CLASS}
                value={identity.tax_regime}
                disabled={!canWrite}
                onChange={(event) => setField("tax_regime", event.target.value)}
              >
                {TAX_REGIMES.map(([value, label]) => (
                  <option key={value || "empty"} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Nature du contrôle">
              <select
                className={SELECT_CLASS}
                value={identity.control_kind}
                disabled={!canWrite}
                onChange={(event) => setField("control_kind", event.target.value)}
              >
                {CONTROL_KINDS.map(([value, label]) => (
                  <option key={value || "empty"} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Code NAEMA">
              <Input
                value={identity.naema_code}
                disabled={!canWrite}
                onChange={(event) => setField("naema_code", event.target.value)}
              />
            </Field>
            <Field label="Adresse" required>
              <Input
                value={identity.address}
                disabled={!canWrite}
                onChange={(event) => setField("address", event.target.value)}
              />
            </Field>
            <Field label="Ville" required>
              <Input
                value={identity.city}
                disabled={!canWrite}
                onChange={(event) => setField("city", event.target.value)}
              />
            </Field>
            <Field label="Code postal">
              <Input
                value={identity.postal_code}
                disabled={!canWrite}
                onChange={(event) => setField("postal_code", event.target.value)}
              />
            </Field>
            <Field label="Téléphone">
              <Input
                value={identity.phone}
                disabled={!canWrite}
                onChange={(event) => setField("phone", event.target.value)}
              />
            </Field>
            <Field label="Courriel">
              <Input
                type="email"
                value={identity.email}
                disabled={!canWrite}
                onChange={(event) => setField("email", event.target.value)}
              />
            </Field>
            <Field label="Établissements dans le pays">
              <Input
                type="number"
                min={0}
                value={identity.establishments_domestic}
                disabled={!canWrite}
                onChange={(event) => setField("establishments_domestic", event.target.value)}
              />
            </Field>
            <Field label="Établissements hors pays">
              <Input
                type="number"
                min={0}
                value={identity.establishments_foreign}
                disabled={!canWrite}
                onChange={(event) => setField("establishments_foreign", event.target.value)}
              />
            </Field>
            <Field label="Expert-comptable">
              <Input
                value={identity.auditor_name}
                disabled={!canWrite}
                onChange={(event) => setField("auditor_name", event.target.value)}
              />
            </Field>
            <Field label="N° ordre">
              <Input
                value={identity.auditor_order_no}
                disabled={!canWrite}
                onChange={(event) => setField("auditor_order_no", event.target.value)}
              />
            </Field>
            <Field label="Signataire">
              <Input
                value={identity.signatory_name}
                disabled={!canWrite}
                onChange={(event) => setField("signatory_name", event.target.value)}
              />
            </Field>
            <Field label="Qualité du signataire">
              <Input
                value={identity.signatory_title}
                disabled={!canWrite}
                onChange={(event) => setField("signatory_title", event.target.value)}
              />
            </Field>
            <Field label="Banques" className="md:col-span-2 xl:col-span-3">
              <Input
                value={identity.banks}
                disabled={!canWrite}
                onChange={(event) => setField("banks", event.target.value)}
              />
            </Field>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={identity.distinct_branch_accounts}
              disabled={!canWrite}
              onChange={(event) => setField("distinct_branch_accounts", event.target.checked)}
            />
            Comptabilité distincte par établissement
          </label>
          {identityMessage && <p className="text-sm text-muted-foreground">{identityMessage}</p>}
          {canWrite && (
            <Button onClick={() => saveIdentity.mutate()} disabled={saveIdentity.isPending}>
              {saveIdentity.isPending ? "Enregistrement…" : "Enregistrer l’identité"}
            </Button>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Dirigeants (R3)</CardTitle>
          <CardDescription>
            Au moins un dirigeant est obligatoire. Administrateurs, gérants et dirigeants
            mentionnés sur la liasse.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {officers.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucun dirigeant enregistré.</p>
          ) : (
            <ul className="divide-y divide-border rounded-md border border-border">
              {officers.map((officer) => (
                <li key={officer.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                  <div>
                    <p className="font-medium">{officer.full_name}</p>
                    <p className="text-muted-foreground">
                      {officer.role_label}
                      {officer.nationality ? ` · ${officer.nationality}` : ""}
                    </p>
                  </div>
                  {canWrite && (
                    <Button
                      variant="destructive"
                      size="sm"
                      disabled={removeOfficer.isPending}
                      onClick={() => removeOfficer.mutate(officer.id)}
                    >
                      Retirer
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
          {canWrite && (
            <div className="grid gap-3 md:grid-cols-4">
              <Field label="Nom" required>
                <Input value={officerName} onChange={(event) => setOfficerName(event.target.value)} />
              </Field>
              <Field label="Qualité">
                <select
                  className={SELECT_CLASS}
                  value={officerRole}
                  onChange={(event) => setOfficerRole(event.target.value)}
                >
                  {OFFICER_ROLES.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Nationalité">
                <Input
                  value={officerNationality}
                  onChange={(event) => setOfficerNationality(event.target.value)}
                />
              </Field>
              <div className="flex items-end">
                <Button onClick={() => addOfficer.mutate()} disabled={addOfficer.isPending || !officerName.trim()}>
                  {addOfficer.isPending ? "Ajout…" : "Ajouter"}
                </Button>
              </div>
            </div>
          )}
          {officerMessage && <p className="text-sm text-muted-foreground">{officerMessage}</p>}
        </CardContent>
      </Card>
    </div>
  );
}

function Field({
  label,
  required,
  children,
  className,
}: {
  label: string;
  required?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`space-y-1.5 ${className ?? ""}`}>
      <Label>
        {label}
        {required ? <span className="text-destructive"> *</span> : null}
      </Label>
      {children}
    </div>
  );
}
