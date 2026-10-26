"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useBetaScope } from "@/components/beta-scope-context";
import { useTenant } from "@/components/tenant-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import type { Commitment } from "@/lib/types";

const SELECT_CLASS = "h-10 w-full rounded-md border border-input bg-background px-3 text-sm";

const KINDS = [
  { id: "mortgage", label: "Hypothèque" },
  { id: "pledge", label: "Nantissement" },
  { id: "gage", label: "Gage" },
  { id: "guarantee", label: "Caution / aval" },
  { id: "discount", label: "Effets escomptés non échus" },
  { id: "assigned", label: "Créances cédées" },
  { id: "lease", label: "Location-acquisition / loyers" },
  { id: "other", label: "Autre engagement" },
];

export default function CommitmentsPage() {
  const { orgSlug, companyId, activeCompany, membership } = useTenant();
  const betaScope = useBetaScope();
  const showClass9 = betaScope.class9_cage;
  const canWrite = ["owner", "admin", "accountant"].includes(membership?.role ?? "");
  const currency = activeCompany?.currency_code ?? "XOF";
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const [kind, setKind] = useState("guarantee");
  const [side, setSide] = useState("given");
  const [label, setLabel] = useState("");
  const [counterparty, setCounterparty] = useState("");
  const [amount, setAmount] = useState("");
  const [startsOn, setStartsOn] = useState("");
  const [endsOn, setEndsOn] = useState("");

  const items = useQuery({
    queryKey: ["commitments", orgSlug, companyId],
    queryFn: () => api<Commitment[]>("/api/ledger/commitments", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });

  const onError = (err: unknown) => {
    setError(err instanceof ApiError ? err.message : "Action impossible.");
  };

  const create = useMutation({
    mutationFn: () =>
      api<Commitment>("/api/ledger/commitments", {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({
          kind,
          side,
          label,
          counterparty,
          amount,
          starts_on: startsOn,
          ends_on: endsOn,
        }),
      }),
    onSuccess: () => {
      setLabel("");
      setCounterparty("");
      setAmount("");
      setError("");
      queryClient.invalidateQueries({ queryKey: ["commitments"] });
      queryClient.invalidateQueries({ queryKey: ["statements"] });
    },
    onError,
  });

  const remove = useMutation({
    mutationFn: (id: string) =>
      api(`/api/ledger/commitments/${id}`, { method: "DELETE", orgSlug, companyId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["commitments"] });
      queryClient.invalidateQueries({ queryKey: ["statements"] });
      queryClient.invalidateQueries({ queryKey: ["class9"] });
      queryClient.invalidateQueries({ queryKey: ["balance"] });
    },
    onError,
  });

  const postClass9 = useMutation({
    mutationFn: (id: string) =>
      api<Commitment>(`/api/ledger/commitments/${id}/class9`, {
        method: "POST",
        orgSlug,
        companyId,
      }),
    onSuccess: () => {
      setError("");
      queryClient.invalidateQueries({ queryKey: ["commitments"] });
      queryClient.invalidateQueries({ queryKey: ["class9"] });
      queryClient.invalidateQueries({ queryKey: ["balance"] });
      queryClient.invalidateQueries({ queryKey: ["entries"] });
    },
    onError,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl">Engagements</h1>
        <p className="text-sm text-muted-foreground">
          Sûretés et engagements hors bilan (note 1). La classe 9 (90/91) est facultative.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {canWrite && (
        <Card>
          <CardHeader>
            <CardTitle>Nouvel engagement</CardTitle>
            <CardDescription>
              Hypothèques, nantissements, cautions, effets escomptés, créances cédées, loyers.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-1.5">
              <Label>Type</Label>
              <select className={SELECT_CLASS} value={kind} onChange={(event) => setKind(event.target.value)}>
                {KINDS.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>Sens</Label>
              <select className={SELECT_CLASS} value={side} onChange={(event) => setSide(event.target.value)}>
                <option value="given">Donné par l’entité</option>
                <option value="received">Reçu par l’entité</option>
              </select>
            </div>
            <div className="space-y-1.5 lg:col-span-2">
              <Label>Libellé</Label>
              <Input value={label} onChange={(event) => setLabel(event.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Tiers</Label>
              <Input value={counterparty} onChange={(event) => setCounterparty(event.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Montant</Label>
              <Input value={amount} onChange={(event) => setAmount(event.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Début</Label>
              <Input type="date" value={startsOn} onChange={(event) => setStartsOn(event.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Échéance</Label>
              <Input type="date" value={endsOn} onChange={(event) => setEndsOn(event.target.value)} />
            </div>
            <div className="self-end">
              <Button onClick={() => create.mutate()} disabled={create.isPending || !label || !amount}>
                {create.isPending ? "Enregistrement…" : "Ajouter"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Registre</CardTitle>
          <CardDescription>Les lignes actives alimentent la note 1 des états.</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-muted-foreground">
              <tr>
                <th className="px-2 py-2">Sens</th>
                <th className="px-2 py-2">Type</th>
                <th className="px-2 py-2">Libellé</th>
                <th className="px-2 py-2">Tiers</th>
                <th className="px-2 py-2 text-right">Montant</th>
                  <th className="px-2 py-2">Échéance</th>
                  {showClass9 && <th className="px-2 py-2">Classe 9</th>}
                {canWrite && <th className="px-2 py-2" />}
              </tr>
            </thead>
            <tbody>
              {(items.data ?? []).map((item) => (
                <tr key={item.id} className="border-t border-border">
                  <td className="px-2 py-2">
                    <Badge>{item.side_label}</Badge>
                  </td>
                  <td className="px-2 py-2">{item.kind_label}</td>
                  <td className="px-2 py-2">{item.label}</td>
                  <td className="px-2 py-2">{item.counterparty || "—"}</td>
                  <td className="px-2 py-2 text-right font-mono">{formatMoney(item.amount, currency)}</td>
                  <td className="px-2 py-2 whitespace-nowrap">{item.ends_on || "—"}</td>
                  {showClass9 && (
                    <td className="px-2 py-2 text-xs">
                      {item.entry_number ? (
                        <span className="font-mono">{item.entry_number}</span>
                      ) : (
                        <span className="text-muted-foreground">
                          {item.class9_debit} / {item.class9_credit}
                        </span>
                      )}
                    </td>
                  )}
                  {canWrite && (
                    <td className="px-2 py-2 text-right">
                      <div className="flex justify-end gap-2">
                        {showClass9 && !item.entry_id && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => postClass9.mutate(item.id)}
                            disabled={postClass9.isPending}
                          >
                            90/91
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => remove.mutate(item.id)}
                          disabled={remove.isPending}
                        >
                          Retirer
                        </Button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
              {(items.data ?? []).length === 0 && (
                <tr>
                    <td
                      colSpan={(canWrite ? 7 : 6) + (showClass9 ? 1 : 0)}
                      className="px-2 py-6 text-center text-muted-foreground"
                    >
                    Aucun engagement. S’il n’y en a pas, la note 1 reste N/A.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
