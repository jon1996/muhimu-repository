"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { BetaScopeGate } from "@/components/beta-scope-gate";
import { useTenant } from "@/components/tenant-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import type { EsgReport, LedgerExercise } from "@/lib/types";

const SELECT_CLASS = "h-10 w-full rounded-md border border-input bg-background px-3 text-sm";
const AREA_CLASS = "min-h-[72px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm";

const EMPTY: Omit<
  EsgReport,
  "id" | "required" | "threshold" | "chapter30_threshold" | "payroll" | "note_preview"
> = {
  year: 0,
  headcount: 0,
  hires: 0,
  dismissals: 0,
  disabled_count: 0,
  social_dialogue: "",
  health: "",
  training: "",
  equality: "",
  env_policy: "",
  waste: "",
  water: "",
  energy: "",
  ghg: "",
  biodiversity: "",
  territory: "",
  neighbors: "",
  patronage: "",
  purchases: "",
};

export default function EsgPage() {
  const { orgSlug, companyId, activeCompany, membership } = useTenant();
  const canWrite = ["owner", "admin", "accountant"].includes(membership?.role ?? "");
  const currency = activeCompany?.currency_code ?? "XOF";
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const [year, setYear] = useState<number | "">("");
  const [form, setForm] = useState(EMPTY);

  const exercises = useQuery({
    queryKey: ["exercises", orgSlug, companyId],
    queryFn: () => api<LedgerExercise[]>("/api/ledger/exercises", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const report = useQuery({
    queryKey: ["esg", orgSlug, companyId, year],
    queryFn: () =>
      api<EsgReport>(`/api/ledger/esg${year ? `?year=${year}` : ""}`, { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });

  useEffect(() => {
    if (!report.data) return;
    setYear(report.data.year);
    setForm({
      year: report.data.year,
      headcount: report.data.headcount,
      hires: report.data.hires,
      dismissals: report.data.dismissals,
      disabled_count: report.data.disabled_count,
      social_dialogue: report.data.social_dialogue,
      health: report.data.health,
      training: report.data.training,
      equality: report.data.equality,
      env_policy: report.data.env_policy,
      waste: report.data.waste,
      water: report.data.water,
      energy: report.data.energy,
      ghg: report.data.ghg,
      biodiversity: report.data.biodiversity,
      territory: report.data.territory,
      neighbors: report.data.neighbors,
      patronage: report.data.patronage,
      purchases: report.data.purchases,
    });
  }, [report.data?.id, report.data?.year]);

  const onError = (err: unknown) => {
    setError(err instanceof ApiError ? err.message : "Action impossible.");
  };

  const save = useMutation({
    mutationFn: () =>
      api<EsgReport>("/api/ledger/esg", {
        method: "PUT",
        orgSlug,
        companyId,
        body: JSON.stringify({ ...form, year: year || form.year }),
      }),
    onSuccess: () => {
      setError("");
      queryClient.invalidateQueries({ queryKey: ["esg"] });
      queryClient.invalidateQueries({ queryKey: ["statements"] });
    },
    onError,
  });

  const setNum = (key: "headcount" | "hires" | "dismissals" | "disabled_count", value: string) => {
    setForm((current) => ({ ...current, [key]: Number(value) || 0 }));
  };
  const setText = (key: keyof typeof EMPTY, value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const required = (form.headcount || 0) > (report.data?.threshold ?? 250);
  const preview = report.data?.note_preview ?? "";

  return (
    <BetaScopeGate feature="esg">
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl">RSE</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Note 35 — informations sociales, environnementales et sociétales. Obligatoire si
          l’effectif dépasse 250 salariés (Titre IX). Le chapitre 30 de l’acte cite 500 ; le
          seuil des notes l’emporte.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="flex flex-wrap items-center gap-3">
        <Label>Exercice</Label>
        <select
          className={`${SELECT_CLASS} w-32`}
          value={year}
          onChange={(event) => setYear(Number(event.target.value) || "")}
        >
          {(exercises.data ?? []).map((item) => (
            <option key={item.id} value={item.year}>
              {item.year}
            </option>
          ))}
          {year && !(exercises.data ?? []).some((item) => item.year === year) && (
            <option value={year}>{year}</option>
          )}
        </select>
        {required ? (
          <Badge>Note 35 obligatoire</Badge>
        ) : (
          <Badge>Facultative sous le seuil</Badge>
        )}
        {report.data?.payroll ? (
          <span className="text-sm text-muted-foreground">
            Masse salariale (66) : {formatMoney(report.data.payroll, currency)}
          </span>
        ) : null}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Social</CardTitle>
          <CardDescription>Effectif, embauches, licenciements, rémunérations, dialogue, santé, formation, égalité, handicap.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <NumberField label="Effectif" value={form.headcount} disabled={!canWrite} onChange={(v) => setNum("headcount", v)} />
          <NumberField label="Embauches" value={form.hires} disabled={!canWrite} onChange={(v) => setNum("hires", v)} />
          <NumberField label="Licenciements" value={form.dismissals} disabled={!canWrite} onChange={(v) => setNum("dismissals", v)} />
          <NumberField
            label="Travailleurs handicapés"
            value={form.disabled_count}
            disabled={!canWrite}
            onChange={(v) => setNum("disabled_count", v)}
          />
          <AreaField label="Dialogue social" value={form.social_dialogue} disabled={!canWrite} onChange={(v) => setText("social_dialogue", v)} />
          <AreaField label="Santé" value={form.health} disabled={!canWrite} onChange={(v) => setText("health", v)} />
          <AreaField label="Formation" value={form.training} disabled={!canWrite} onChange={(v) => setText("training", v)} />
          <AreaField label="Égalité" value={form.equality} disabled={!canWrite} onChange={(v) => setText("equality", v)} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Environnement</CardTitle>
          <CardDescription>Politique, déchets, eau, énergie, gaz à effet de serre, biodiversité.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <AreaField label="Politique" value={form.env_policy} disabled={!canWrite} onChange={(v) => setText("env_policy", v)} />
          <AreaField label="Déchets" value={form.waste} disabled={!canWrite} onChange={(v) => setText("waste", v)} />
          <AreaField label="Eau" value={form.water} disabled={!canWrite} onChange={(v) => setText("water", v)} />
          <AreaField label="Énergie" value={form.energy} disabled={!canWrite} onChange={(v) => setText("energy", v)} />
          <AreaField label="GES" value={form.ghg} disabled={!canWrite} onChange={(v) => setText("ghg", v)} />
          <AreaField label="Biodiversité" value={form.biodiversity} disabled={!canWrite} onChange={(v) => setText("biodiversity", v)} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Sociétal</CardTitle>
          <CardDescription>Territoire, riverains, mécénat, achats responsables.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <AreaField label="Territoire" value={form.territory} disabled={!canWrite} onChange={(v) => setText("territory", v)} />
          <AreaField label="Riverains" value={form.neighbors} disabled={!canWrite} onChange={(v) => setText("neighbors", v)} />
          <AreaField label="Mécénat" value={form.patronage} disabled={!canWrite} onChange={(v) => setText("patronage", v)} />
          <AreaField label="Achats" value={form.purchases} disabled={!canWrite} onChange={(v) => setText("purchases", v)} />
        </CardContent>
      </Card>

      {preview && (
        <p className="rounded-md bg-muted px-3 py-2 font-mono text-xs">{preview}</p>
      )}

      {canWrite && (
        <Button disabled={save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "Enregistrement…" : "Enregistrer la fiche"}
        </Button>
      )}
    </div>
    </BetaScopeGate>
  );
}

function NumberField({
  label,
  value,
  disabled,
  onChange,
}: {
  label: string;
  value: number;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Input type="number" min={0} value={value || ""} disabled={disabled} onChange={(event) => onChange(event.target.value)} />
    </div>
  );
}

function AreaField({
  label,
  value,
  disabled,
  onChange,
}: {
  label: string;
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-1.5 sm:col-span-2 lg:col-span-2">
      <Label>{label}</Label>
      <textarea className={AREA_CLASS} value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)} />
    </div>
  );
}
