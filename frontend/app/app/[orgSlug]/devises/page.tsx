"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { useTenant } from "@/components/tenant-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { localTodayIso } from "@/lib/dates";
import { FX_CURRENCY_CHOICES } from "@/lib/ohada";
import type { FxRate } from "@/lib/types";

const SELECT_CLASS = "h-10 w-full rounded-md border border-input bg-background px-3 text-sm";

export default function FxRatesPage() {
  const { orgSlug, companyId, activeCompany, membership } = useTenant();
  const canWrite = ["owner", "admin", "accountant"].includes(membership?.role ?? "");
  const functional = activeCompany?.currency_code ?? "XOF";
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const [currencyCode, setCurrencyCode] = useState("EUR");
  const [rateDate, setRateDate] = useState("");
  const [rate, setRate] = useState("");

  useEffect(() => {
    setRateDate((current) => current || localTodayIso());
  }, []);

  const rates = useQuery({
    queryKey: ["fx-rates", orgSlug, companyId],
    queryFn: () => api<FxRate[]>("/api/ledger/fx-rates", { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId),
  });

  const onError = (err: unknown) => {
    setError(err instanceof ApiError ? err.message : "Action impossible.");
  };

  const save = useMutation({
    mutationFn: () =>
      api<FxRate>("/api/ledger/fx-rates", {
        method: "POST",
        orgSlug,
        companyId,
        body: JSON.stringify({
          currency_code: currencyCode,
          rate_date: rateDate,
          rate,
        }),
      }),
    onSuccess: () => {
      setRate("");
      setError("");
      queryClient.invalidateQueries({ queryKey: ["fx-rates"] });
    },
    onError,
  });

  const remove = useMutation({
    mutationFn: (id: string) =>
      api(`/api/ledger/fx-rates/${id}`, { method: "DELETE", orgSlug, companyId }),
    onSuccess: () => {
      setError("");
      queryClient.invalidateQueries({ queryKey: ["fx-rates"] });
    },
    onError,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl">Devises</h1>
        <p className="mt-1 max-w-2xl text-muted-foreground">
          Devise de tenue {functional} (fixe à la création de la société). Saisissez le cours au comptant :
          1 unité étrangère = x {functional}. À l’imputation, les lignes en devise sont converties à la date
          de valeur. À l’arrêté, les postes monétaires (classes 4 et 5) sont réévalués en 478 / 479 depuis
          Clôture.
        </p>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}

      {canWrite && (
        <Card>
          <CardHeader>
            <CardTitle>Nouveau cours</CardTitle>
            <CardDescription>
              Le cours le plus récent à une date donnée sert à la conversion et à la réévaluation.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-4">
            <div className="space-y-1.5">
              <Label>Devise</Label>
              <select
                className={SELECT_CLASS}
                value={currencyCode}
                onChange={(event) => setCurrencyCode(event.target.value)}
              >
                {FX_CURRENCY_CHOICES.filter((code) => code !== functional).map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="fx-date">Date</Label>
              <Input id="fx-date" type="date" value={rateDate} onChange={(event) => setRateDate(event.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="fx-rate">1 {currencyCode} = … {functional}</Label>
              <Input
                id="fx-rate"
                inputMode="decimal"
                placeholder="655,957"
                value={rate}
                onChange={(event) => setRate(event.target.value)}
              />
            </div>
            <div className="flex items-end">
              <Button
                type="button"
                disabled={!rate.trim() || save.isPending}
                onClick={() => save.mutate()}
              >
                {save.isPending ? "Enregistrement…" : "Enregistrer"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Cours enregistrés</CardTitle>
        </CardHeader>
        <CardContent>
          {(rates.data ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucun cours pour l’instant.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border text-muted-foreground">
                  <tr>
                    <th className="py-1.5 pr-3 font-medium">Devise</th>
                    <th className="py-1.5 pr-3 font-medium">Date</th>
                    <th className="py-1.5 pr-3 font-medium text-right">Cours / {functional}</th>
                    {canWrite && <th className="py-1.5 font-medium" />}
                  </tr>
                </thead>
                <tbody>
                  {(rates.data ?? []).map((row) => (
                    <tr key={row.id} className="border-b border-border/70">
                      <td className="py-1.5 pr-3 font-mono">{row.currency_code}</td>
                      <td className="py-1.5 pr-3">{row.rate_date}</td>
                      <td className="py-1.5 pr-3 text-right font-mono">{row.rate}</td>
                      {canWrite && (
                        <td className="py-1.5 text-right">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            disabled={remove.isPending}
                            onClick={() => remove.mutate(row.id)}
                          >
                            Retirer
                          </Button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
