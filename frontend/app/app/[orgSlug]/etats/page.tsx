"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type Dispatch, type SetStateAction } from "react";

import { StatementTable } from "@/components/statement-table";
import { useTenant } from "@/components/tenant-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError, downloadApi } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import type { FinancialStatements, LedgerPeriod, StatementIndicator, StatementNote } from "@/lib/types";

const TABS = [
  ["bilan", "Bilan"],
  ["result", "Compte de résultat"],
  ["tft", "TFT"],
  ["notes", "Notes annexes"],
] as const;

const SMT_TABS = [
  ["bilan", "Situation patrimoniale"],
  ["tft", "État de trésorerie"],
  ["notes", "Notes annexes"],
] as const;

export default function StatementsPage() {
  const { orgSlug, companyId, activeCompany } = useTenant();
  const currency = activeCompany?.currency_code ?? "XOF";
  const queryClient = useQueryClient();
  const [periodId, setPeriodId] = useState("");
  const [tab, setTab] = useState<"bilan" | "result" | "tft" | "notes">("bilan");
  const [noteDraft, setNoteDraft] = useState<StatementNote[]>([]);
  const [pdfKind, setPdfKind] = useState<"liasse" | "bilan" | "result" | "tft" | "notes" | null>(null);
  const [pdfError, setPdfError] = useState("");

  const periods = useQuery({
    queryKey: ["periods", orgSlug, companyId],
    queryFn: () => api<LedgerPeriod[]>("/api/ledger/periods", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });
  const statements = useQuery({
    queryKey: ["statements", orgSlug, companyId, periodId],
    queryFn: () =>
      api<FinancialStatements>(
        `/api/ledger/statements${periodId ? `?period_id=${periodId}` : ""}`,
        { orgSlug, companyId },
      ),
    enabled: Boolean(orgSlug && companyId),
  });

  useEffect(() => {
    if (statements.data?.notes) {
      setNoteDraft(statements.data.notes);
    }
  }, [statements.data]);

  const saveNotes = useMutation({
    mutationFn: () =>
      api("/api/ledger/exercise/notes", {
        method: "PATCH",
        orgSlug,
        companyId,
        body: JSON.stringify({
          period_id: statements.data?.period_id || periodId || undefined,
          notes: noteDraft.map((note) => ({
            number: note.number,
            status: note.number === 2 ? "A" : note.status,
            body: note.body,
            conformity: note.conformity,
            methods: note.methods,
            derogations: note.derogations,
            extra: note.extra,
          })),
        }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["statements"] }),
  });

  const data = statements.data;
  const prior = data?.comparative_year ?? null;
  const entity = data?.entity;
  const isSmt = data?.regime === "smt";
  const tabs = isSmt ? SMT_TABS : TABS;

  useEffect(() => {
    if (isSmt && tab === "result") {
      setTab("tft");
    }
  }, [isSmt, tab]);

  async function downloadPdf(kind: "liasse" | "bilan" | "result" | "tft" | "notes") {
    if (!data) return;
    setPdfError("");
    setPdfKind(kind);
    const query = new URLSearchParams({ kind });
    if (periodId) query.set("period_id", periodId);
    const names = isSmt
      ? {
          liasse: "liasse-smt",
          bilan: "situation-patrimoniale",
          result: "etat-de-tresorerie",
          tft: "etat-de-tresorerie",
          notes: "notes-annexes-smt",
        }
      : {
          liasse: "liasse-sn",
          bilan: "bilan",
          result: "compte-de-resultat",
          tft: "tft",
          notes: "notes-annexes",
        };
    try {
      await downloadApi(`/api/ledger/statements/pdf?${query}`, {
        orgSlug,
        companyId,
        filename: `${names[kind]}-${data.exercise_year}.pdf`,
      });
    } catch (error) {
      setPdfError(error instanceof ApiError ? error.message : "Téléchargement PDF impossible.");
    } finally {
      setPdfKind(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl">États financiers</h1>
          <p className="mt-1 max-w-2xl text-muted-foreground">
            {isSmt
              ? "Liasse SMT (art. 11–13) : situation patrimoniale, état de trésorerie (recettes / dépenses, classe 5) et notes annexes. Inventaire de fin d’exercice. PDF numéroté et daté (art. 22)."
              : "Liasse SN (Titre IX, référentiel SYSCOHADA) : bilan AD–DZ avant répartition, compte de résultat TA–XI, TFT depuis la CAFG, notes 1–36. Colonne N-1 obligatoire. Export PDF version bêta — présentation en validation, non certifié."}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {data && (
            <Button
              type="button"
              onClick={() => downloadPdf("liasse")}
              disabled={pdfKind !== null}
            >
              {pdfKind === "liasse" ? "Préparation…" : "Télécharger la liasse"}
            </Button>
          )}
          <select
            className="h-10 rounded-md border border-input bg-background px-2 text-sm"
            value={periodId}
            onChange={(event) => setPeriodId(event.target.value)}
          >
            <option value="">Période courante</option>
            {(periods.data ?? []).map((period) => (
              <option key={period.id} value={period.id}>
                {period.year}-{String(period.month).padStart(2, "0")}
              </option>
            ))}
          </select>
        </div>
      </div>

      {entity && (
        <Card>
          <CardHeader>
            <CardTitle>{entity.legal_name}</CardTitle>
            <CardDescription>
              Titre IX ch. 1–2 — identité sur chaque état. Devise {entity.currency_code}.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm sm:grid-cols-2 xl:grid-cols-4">
            <HeaderCell label="Dénomination" value={entity.name} />
            <HeaderCell label="Sigle" value={entity.acronym} />
            <HeaderCell label="Pays du siège" value={entity.country_label || entity.country_code} />
            <HeaderCell label="RCCM" value={entity.rccm} />
            <HeaderCell label="NIF" value={entity.tax_id} />
            <HeaderCell label="Répertoire / CNPS" value={entity.social_register} />
            <HeaderCell label="Forme juridique" value={entity.legal_form_label} />
            <HeaderCell label="Régime fiscal" value={entity.tax_regime_label} />
            <HeaderCell label="NAEMA" value={entity.naema_code} />
            <HeaderCell label="Contrôle" value={entity.control_label} />
            <HeaderCell
              label="Adresse"
              value={[entity.address, entity.postal_code, entity.city].filter(Boolean).join(", ")}
            />
            <HeaderCell label="Téléphone" value={entity.phone} />
            <HeaderCell label="Courriel" value={entity.email} />
            <HeaderCell label="Régime" value={entity.regime_label} />
            <HeaderCell label="Activité" value={entity.activity_label} />
            <HeaderCell label="Exercice du" value={entity.starts_on} />
            <HeaderCell label="au" value={entity.ends_on} />
            <HeaderCell label="Durée (mois)" value={String(entity.duration_months)} />
            <HeaderCell
              label="Continuité d’exploitation"
              value={data?.going_concern ? "Retenue" : "Non retenue"}
            />
            <HeaderCell
              label="Expert-comptable"
              value={[entity.auditor_name, entity.auditor_order_no].filter(Boolean).join(" · ")}
            />
            <HeaderCell
              label="Signataire"
              value={[entity.signatory_name, entity.signatory_title].filter(Boolean).join(" · ")}
            />
            <HeaderCell label="Banques" value={entity.banks} />
            <HeaderCell
              label="Dirigeants"
              value={(entity.officers ?? [])
                .map((officer) =>
                  officer.nationality
                    ? `${officer.full_name} (${officer.role_label}, ${officer.nationality})`
                    : `${officer.full_name} (${officer.role_label})`,
                )
                .join(" · ")}
            />
          </CardContent>
        </Card>
      )}

      {data && (
        <p className="text-sm text-muted-foreground">
          Arrêté au plus tard le {data.arrete_due_on} · AGO avant le {data.ago_due_on}
          {data.bilan.balanced ? "" : isSmt ? " · situation non équilibrée" : " · bilan non équilibré"}
        </p>
      )}
      {data?.smt?.warning && (
        <p className={data.smt.eligible ? "text-sm text-muted-foreground" : "text-sm text-destructive"}>
          {data.smt.warning}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {tabs.map(([key, label]) => (
          <Button key={key} variant={tab === key ? "default" : "outline"} onClick={() => setTab(key)}>
            {label}
          </Button>
        ))}
      </div>

      {statements.isError && (
        <p className="text-sm text-destructive">
          {statements.error instanceof ApiError ? statements.error.message : "États indisponibles."}
        </p>
      )}
      {pdfError && <p className="text-sm text-destructive">{pdfError}</p>}

      {data && tab === "bilan" && (
        <div className="space-y-6">
          <div className="flex justify-end">
            <Button
              type="button"
              variant="outline"
              onClick={() => downloadPdf("bilan")}
              disabled={pdfKind !== null}
            >
              {pdfKind === "bilan" ? "Préparation…" : isSmt ? "PDF situation" : "PDF du bilan"}
            </Button>
          </div>
          {data.analysis && !isSmt && (
            <Card>
              <CardHeader>
                <CardTitle>Analyse financière</CardTitle>
                <CardDescription>
                  Titre IX ch. 3 — hors liasse. Le bilan publié n’est pas retraité. FR = ressources
                  stables − immos nettes. TN = trésorerie-actif − trésorerie-passif.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  <Metric label="FR (haut)" value={data.analysis.fr} currency={currency} priorYear={prior} />
                  <Metric label="BFE" value={data.analysis.bfe} currency={currency} priorYear={prior} />
                  <Metric label="BF.HAO" value={data.analysis.bf_hao} currency={currency} priorYear={prior} />
                  <Metric label="BFG" value={data.analysis.bfg} currency={currency} priorYear={prior} />
                  <Metric label="TN" value={data.analysis.tn} currency={currency} priorYear={prior} />
                  <Metric
                    label="Écarts de conversion (478−479)"
                    value={data.analysis.conversion}
                    currency={currency}
                    priorYear={prior}
                  />
                </div>
              </CardContent>
            </Card>
          )}
          <div className="grid gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Actif</CardTitle>
                <CardDescription>
                  {isSmt
                    ? "Immobilisations, stocks, créances, trésorerie — inventaire de fin de période."
                    : "Brut, amortissements et dépréciations, net N / net N-1. Codes AD–BZ."}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <StatementTable
                  lines={data.bilan.actif}
                  currency={currency}
                  priorYear={prior}
                  showGross={!isSmt}
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Passif</CardTitle>
                <CardDescription>
                  {isSmt
                    ? "Capitaux propres, dettes, trésorerie-passif."
                    : "Capitaux propres, dettes financières, circulant, trésorerie-passif. Codes CA–DZ."}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <StatementTable lines={data.bilan.passif} currency={currency} priorYear={prior} />
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {data && tab === "result" && !isSmt && (
        <Card>
          <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Compte de résultat</CardTitle>
              <CardDescription>
                Signes +/− du modèle. SIG XA–XI. EBE négatif = IBE. Participation et impôt après HAO.
              </CardDescription>
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={() => downloadPdf("result")}
              disabled={pdfKind !== null}
            >
              {pdfKind === "result" ? "Préparation…" : "PDF du CR"}
            </Button>
          </CardHeader>
          <CardContent>
            <StatementTable lines={data.result.lines} currency={currency} priorYear={prior} />
          </CardContent>
        </Card>
      )}

      {data && tab === "tft" && (
        <Card>
          <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>{isSmt ? "État de trésorerie" : "Tableau des flux de trésorerie"}</CardTitle>
              <CardDescription>
                {isSmt
                  ? "Encaissements et décaissements constatés sur la classe 5 (virements internes exclus du flux). Contrôle avec la trésorerie de la situation patrimoniale."
                  : "Méthode indirecte depuis la CAFG (Titre IX ch. 5). Variations d’exploitation hors créances et dettes d’immobilisations. Codes ZA–ZH / FA–FQ."}
              </CardDescription>
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={() => downloadPdf("tft")}
              disabled={pdfKind !== null}
            >
              {pdfKind === "tft" ? "Préparation…" : isSmt ? "PDF de l’ET" : "PDF du TFT"}
            </Button>
          </CardHeader>
          <CardContent>
            <StatementTable lines={data.tft.lines} currency={currency} priorYear={prior} />
          </CardContent>
        </Card>
      )}

      {data && tab === "notes" && (
        <Card>
          <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Notes annexes</CardTitle>
              <CardDescription>
                Titre IX ch. 6. Note 2 obligatoire (A). Les autres : A à joindre, N/A à ne pas joindre
                (fiche R4). Le PDF de liasse inclut uniquement les notes A.
              </CardDescription>
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={() => downloadPdf("notes")}
              disabled={pdfKind !== null}
            >
              {pdfKind === "notes" ? "Préparation…" : "PDF des notes"}
            </Button>
          </CardHeader>
          <CardContent className="space-y-4">
            {noteDraft.map((note, index) => (
              <div key={note.number} className="rounded-md border border-border p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium">
                    Note {note.number} — {note.title}
                    {note.required ? <span className="ml-2 text-xs text-muted-foreground">obligatoire</span> : null}
                  </p>
                  <select
                    className="h-8 rounded-md border border-input bg-background px-2 text-xs"
                    value={note.number === 2 ? "A" : note.status}
                    disabled={note.number === 2}
                    onChange={(event) =>
                      setNoteDraft((current) =>
                        current.map((item, i) =>
                          i === index ? { ...item, status: event.target.value } : item,
                        ),
                      )
                    }
                  >
                    <option value="A">A — jointe</option>
                    <option value="NA">N/A — non jointe</option>
                  </select>
                </div>
                {note.number === 2 ? (
                  <div className="mt-3 grid gap-2">
                    <NoteField
                      label="A. Référentiel comptable et présentation (SYSCOHADA / PCGO)"
                      value={note.conformity}
                      onChange={(value) => patchNote(setNoteDraft, index, { conformity: value })}
                    />
                    <NoteField
                      label="B. Règles et méthodes"
                      value={note.methods}
                      onChange={(value) => patchNote(setNoteDraft, index, { methods: value })}
                    />
                    <NoteField
                      label="C. Dérogations"
                      value={note.derogations}
                      onChange={(value) => patchNote(setNoteDraft, index, { derogations: value })}
                    />
                    <NoteField
                      label="D. Informations complémentaires"
                      value={note.extra}
                      onChange={(value) => patchNote(setNoteDraft, index, { extra: value })}
                    />
                  </div>
                ) : (
                  <div className="mt-3 space-y-2">
                    {note.computed ? (
                      <p className="rounded-md bg-muted px-3 py-2 font-mono text-xs">{note.computed}</p>
                    ) : null}
                    {(note.status === "A" || Boolean(note.computed) || note.number === 34) && (
                      <NoteField
                        label={note.number === 34 ? "Commentaire (note 34)" : "Contenu"}
                        value={note.body}
                        onChange={(value) => patchNote(setNoteDraft, index, { body: value })}
                      />
                    )}
                  </div>
                )}
              </div>
            ))}
            <Button onClick={() => saveNotes.mutate()} disabled={saveNotes.isPending}>
              {saveNotes.isPending ? "Enregistrement…" : "Enregistrer les notes"}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function HeaderCell({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p>{value}</p>
    </div>
  );
}

function Metric({
  label,
  value,
  currency,
  priorYear,
}: {
  label: string;
  value: StatementIndicator;
  currency: string;
  priorYear: number | null;
}) {
  return (
    <div className="rounded-md border border-border px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-mono text-sm">{formatMoney(value.current, currency)}</p>
      <p className="text-xs text-muted-foreground">
        N-1{priorYear ? ` (${priorYear})` : ""} : {formatMoney(value.prior, currency)}
      </p>
    </div>
  );
}

function NoteField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block text-sm">
      <span className="text-xs text-muted-foreground">{label}</span>
      <textarea
        className="mt-1 min-h-20 w-full rounded-md border border-input bg-background p-2 text-sm"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function patchNote(
  setNoteDraft: Dispatch<SetStateAction<StatementNote[]>>,
  index: number,
  patch: Partial<StatementNote>,
) {
  setNoteDraft((current) => current.map((item, i) => (i === index ? { ...item, ...patch } : item)));
}
