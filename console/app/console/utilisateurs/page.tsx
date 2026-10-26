"use client";

import { useMemo, useState } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { PlatformUser } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";

function formatWhen(value: string | null) {
  if (!value) return "Jamais";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("fr-FR");
}

export default function UsersPage() {
  const [query, setQuery] = useState("");
  const [staffOnly, setStaffOnly] = useState(false);

  const users = useQuery({
    queryKey: ["platform-users"],
    queryFn: () => api<PlatformUser[]>("/api/users"),
  });

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (users.data ?? []).filter((user) => {
      if (staffOnly && !user.is_staff) return false;
      if (!needle) return true;
      const hay = [
        user.email,
        user.full_name,
        ...user.organizations.map((org) => `${org.name} ${org.slug}`),
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(needle);
    });
  }, [query, staffOnly, users.data]);

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <div>
        <h1 className="font-serif text-3xl">Utilisateurs</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Comptes ERP et équipe Muhimu, avec leurs dossiers et le dernier accès.
        </p>
      </div>

      {users.isPending && <p className="text-sm text-muted-foreground">Chargement…</p>}
      {users.isError && (
        <p className="text-sm text-destructive">
          {users.error instanceof ApiError ? users.error.message : "Impossible de charger les utilisateurs."}
        </p>
      )}

      {users.data && (
        <>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Rechercher e-mail, nom, organisation…"
              className="sm:max-w-sm"
            />
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={staffOnly}
                onChange={(event) => setStaffOnly(event.target.checked)}
              />
              Équipe Muhimu seulement
            </label>
          </div>

          <Card>
            <CardContent className="overflow-x-auto pt-6">
              {filtered.length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucun utilisateur ne correspond.</p>
              ) : (
                <table className="w-full min-w-[720px] text-left text-sm">
                  <thead className="text-xs uppercase tracking-wide text-muted-foreground">
                    <tr>
                      <th className="pb-3 font-medium">Compte</th>
                      <th className="pb-3 font-medium">Dossiers</th>
                      <th className="pb-3 font-medium">Accès</th>
                      <th className="pb-3 font-medium">Dernière connexion</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((user) => (
                      <tr key={user.id} className="border-t border-border">
                        <td className="py-3">
                          <div className="font-medium">{user.full_name || user.email}</div>
                          <div className="text-xs text-muted-foreground">{user.email}</div>
                        </td>
                        <td className="py-3">
                          {user.organizations.length === 0 ? (
                            <span className="text-muted-foreground">—</span>
                          ) : (
                            <ul className="space-y-1">
                              {user.organizations.map((org) => (
                                <li key={org.id}>
                                  {org.name}{" "}
                                  <span className="text-xs text-muted-foreground">
                                    ({org.type_label} · {org.role_label}
                                    {org.is_demo ? " · démo" : ""})
                                  </span>
                                </li>
                              ))}
                            </ul>
                          )}
                        </td>
                        <td className="py-3">
                          <div className="flex flex-wrap gap-1">
                            {user.is_staff && (
                              <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[11px] text-primary">
                                Staff
                              </span>
                            )}
                            {user.has_demo_grant && (
                              <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                                Grant démo
                              </span>
                            )}
                            <span
                              className={cn(
                                "rounded-full px-2 py-0.5 text-[11px]",
                                user.is_active
                                  ? "bg-primary/15 text-primary"
                                  : "bg-destructive/10 text-destructive",
                              )}
                            >
                              {user.is_active ? "Actif" : "Inactif"}
                            </span>
                          </div>
                        </td>
                        <td className="py-3 text-muted-foreground">{formatWhen(user.last_login)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
