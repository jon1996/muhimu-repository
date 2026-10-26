"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { Building2, CreditCard, KeyRound, LayoutDashboard, Mail, Users } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import type { StaffMe } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/console", label: "Tableau de bord", icon: LayoutDashboard, ready: true },
  { href: "/console/organisations", label: "Organisations", icon: Building2, ready: true },
  { href: "/console/utilisateurs", label: "Utilisateurs", icon: Users, ready: true },
  { href: "/console/demo", label: "Accès démo", icon: KeyRound, ready: true },
  { href: "/console/emails", label: "E-mails", icon: Mail, ready: true },
  { href: "/console/facturation", label: "Facturation", icon: CreditCard, ready: false },
];

export function ConsoleShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const me = useQuery({
    queryKey: ["platform-me"],
    queryFn: () => api<StaffMe>("/api/auth/me"),
    retry: false,
  });

  const logout = useMutation({
    mutationFn: () => api("/api/auth/logout", { method: "POST" }),
    onSettled: () => router.replace("/login"),
  });

  useEffect(() => {
    if (me.isError && me.error instanceof ApiError && (me.error.status === 401 || me.error.status === 403)) {
      router.replace("/login");
    }
  }, [me.error, me.isError, router]);

  if (me.isPending) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Chargement de la console…
      </div>
    );
  }

  if (!me.data) {
    return null;
  }

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-64 shrink-0 flex-col bg-sidebar text-sidebar-foreground">
        <div className="border-b border-sidebar-border px-5 py-5">
          <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-sidebar-accent">Muhimu</p>
          <p className="mt-1 font-serif text-xl">Console SaaS</p>
          <p className="mt-1 text-xs text-sidebar-foreground/70">Pilotage de l&apos;ERP, hors produit</p>
        </div>
        <nav className="flex flex-1 flex-col gap-1 p-3">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active =
              item.href === "/console"
                ? pathname === "/console"
                : pathname === item.href || pathname.startsWith(`${item.href}/`);
            if (!item.ready) {
              return (
                <span
                  key={item.href}
                  className="flex items-center justify-between rounded-lg px-3 py-2 text-sm text-sidebar-foreground/45"
                >
                  <span className="flex items-center gap-2">
                    <Icon className="size-4" />
                    {item.label}
                  </span>
                  <span className="text-[10px] uppercase tracking-wide">Bientôt</span>
                </span>
              );
            }
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-3 py-2 text-sm",
                  active ? "bg-sidebar-accent text-sidebar-accent-foreground" : "hover:bg-white/5",
                )}
              >
                <Icon className="size-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-sidebar-border p-4">
          <p className="truncate text-sm">{me.data.user.full_name || me.data.user.email}</p>
          <p className="truncate text-xs text-sidebar-foreground/60">{me.data.user.email}</p>
          <Button
            className="mt-3 w-full"
            variant="outline"
            size="sm"
            onClick={() => logout.mutate()}
          >
            Déconnexion
          </Button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-8">{children}</main>
    </div>
  );
}
