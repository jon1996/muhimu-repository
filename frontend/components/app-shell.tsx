"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, LayoutDashboard } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { cn } from "@/lib/utils";

import { BetaDisclaimerBanner } from "@/components/beta-disclaimer-banner";
import { BetaScopeProvider } from "@/components/beta-scope-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TenantProvider } from "@/components/tenant-context";
import { api, ApiError, clearCsrf, companyStorageKey } from "@/lib/api";
import { sessionExpiredLoginMessage } from "@/lib/session-events";
import { BETA_SCOPE_OPEN, isNavPathAllowed, type BetaScope } from "@/lib/beta-scope";
import type { Company, Me, Role } from "@/lib/types";
import { ROLE_LABELS } from "@/lib/types";
export function AppShell({ children }: { children: React.ReactNode }) {
  const params = useParams<{ orgSlug: string }>();
  const orgSlug = params.orgSlug;
  const router = useRouter();
  const queryClient = useQueryClient();
  const [companyId, setCompanyId] = useState<string>("");

  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api<Me>("/api/auth/me"),
  });

  const membership = useMemo(
    () => me.data?.memberships.find((item) => item.organization.slug === orgSlug),
    [me.data, orgSlug],
  );

  const companies = useQuery({
    queryKey: ["companies", orgSlug],
    queryFn: () => api<Company[]>("/api/companies", { orgSlug }),
    enabled: Boolean(orgSlug) && Boolean(me.data),
  });

  const betaScopeQuery = useQuery({
    queryKey: ["beta-scope", orgSlug],
    queryFn: () => api<BetaScope>("/api/ledger/beta-scope", { orgSlug }),
    enabled: Boolean(orgSlug) && Boolean(me.data),
    staleTime: 60_000,
  });
  const betaScope = betaScopeQuery.data ?? BETA_SCOPE_OPEN;

  useEffect(() => {
    if (me.error instanceof ApiError && me.error.status === 401) {
      clearCsrf();
      queryClient.clear();
      const message = encodeURIComponent(sessionExpiredLoginMessage("unknown"));
      router.replace(`/login?reason=unknown&message=${message}`);
    }
  }, [me.error, queryClient, router]);

  useEffect(() => {
    if (!orgSlug) return;
    const stored = window.localStorage.getItem(companyStorageKey(orgSlug)) ?? "";
    setCompanyId(stored);
  }, [orgSlug]);

  useEffect(() => {
    const list = companies.data;
    if (!list?.length) return;
    const exists = list.some((company) => company.id === companyId);
    if (!exists) {
      const next = list[0].id;
      setCompanyId(next);
      window.localStorage.setItem(companyStorageKey(orgSlug), next);
    }
  }, [companies.data, companyId, orgSlug]);

  const logout = useMutation({
    mutationFn: () => api("/api/auth/logout", { method: "POST" }),
    onSuccess: () => {
      clearCsrf();
      queryClient.clear();
      router.replace("/login");
    },
  });

  const onCompanyChange = (value: string) => {
    setCompanyId(value);
    window.localStorage.setItem(companyStorageKey(orgSlug), value);
  };

  const role: Role | undefined = membership?.role;
  const canSeeAudit = role === "owner" || role === "admin" || role === "auditor";
  const pendingSetup =
    Boolean(membership) &&
    !membership?.organization.setup_data &&
    (role === "owner" || role === "admin" || role === "accountant");

  useEffect(() => {
    if (!pendingSetup) return;
    router.replace(`/app?org=${encodeURIComponent(orgSlug)}`);
  }, [pendingSetup, orgSlug, router]);

  const pathname = usePathname();
  const activeCompany = (companies.data ?? []).find((company) => company.id === companyId);
  const organisationHref = `/app/${orgSlug}/organisation`;
  const onOrganisation =
    pathname === organisationHref || pathname.startsWith(`${organisationHref}/`);
  const identityGate = Boolean(membership) && !membership?.organization.is_demo;
  const identityPending =
    identityGate &&
    companies.isSuccess &&
    Boolean(activeCompany) &&
    activeCompany?.identity_complete === false;
  const lockNav = identityPending || (identityGate && !companies.isSuccess);

  useEffect(() => {
    if (!identityPending || onOrganisation) return;
    router.replace(organisationHref);
  }, [identityPending, onOrganisation, organisationHref, router]);

  const navGroups = useMemo(
    () => navGroupsFor(orgSlug, canSeeAudit, { identityPending: lockNav, betaScope }),
    [orgSlug, canSeeAudit, lockNav, betaScope],
  );

  if (pendingSetup) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Initialisation du dossier…
      </div>
    );
  }

  if (me.isPending) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Chargement de l&apos;ERP…
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="flex w-64 shrink-0 flex-col bg-sidebar text-sidebar-foreground">
        <div className="border-b border-sidebar-border px-5 py-5">
          <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-sidebar-accent">Muhimu</p>
          <p className="mt-1 font-serif text-xl">ERP</p>
          <p className="mt-1 text-xs text-sidebar-foreground/70">Comptabilité SYSCOHADA · bêta</p>
        </div>
        <nav className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto p-3 text-sm">
          {!lockNav && (
            <NavLink href={`/app/${orgSlug}`} label="Tableau de bord" pathname={pathname} exact icon={LayoutDashboard} />
          )}
          {navGroups.map((group) => (
            <NavGroup key={group.id} group={group} pathname={pathname} />
          ))}
        </nav>
        <div className="border-t border-sidebar-border p-4">
          <p className="truncate text-sm">{me.data?.user.full_name || me.data?.user.email}</p>
          <p className="truncate text-xs text-sidebar-foreground/60">{me.data?.user.email}</p>
          <p className="mt-2 text-[11px] text-sidebar-foreground/45">
            {(companies.data ?? []).find((company) => company.id === companyId)?.accounting_regime === "smt"
              ? "SMT"
              : "Système normal"}
          </p>
          <Button
            className="mt-3 w-full border-sidebar-border bg-transparent text-sidebar-foreground hover:bg-white/5 hover:text-sidebar-foreground"
            variant="outline"
            size="sm"
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
          >
            Déconnexion
          </Button>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-border bg-background px-8 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <select
              className="h-9 max-w-[220px] rounded-lg border border-input bg-card px-2.5 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
              value={orgSlug}
              onChange={(event) => {
                const slug = event.target.value;
                const next = (me.data?.memberships ?? []).find(
                  (item) => item.organization.slug === slug,
                );
                if (next && !next.organization.setup_data) {
                  router.push(`/app?org=${encodeURIComponent(slug)}`);
                  return;
                }
                router.push(`/app/${slug}`);
              }}
            >
              {(me.data?.memberships ?? []).map((item) => (
                <option key={item.id} value={item.organization.slug}>
                  {item.organization.name}
                </option>
              ))}
            </select>
            <Button variant="outline" size="sm" onClick={() => router.push("/app?create=1")}>
              Nouvelle entreprise
            </Button>
            <select
              className="h-9 max-w-[240px] rounded-lg border border-input bg-card px-2.5 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
              value={companyId}
              onChange={(event) => onCompanyChange(event.target.value)}
            >
              {(companies.data ?? []).map((company) => (
                <option key={company.id} value={company.id}>
                  {company.name} ({company.currency_code})
                </option>
              ))}
            </select>
            {membership && (
              <Badge>
                {membership.organization.type === "cabinet" ? "Cabinet" : "PME"} ·{" "}
                {ROLE_LABELS[membership.role]}
              </Badge>
            )}
          </div>
        </header>
        <main className="flex-1 overflow-auto p-8">
          <BetaDisclaimerBanner className="mb-6" />
          <BetaScopeProvider value={betaScope}>
          <TenantProvider
            value={{
              orgSlug,
              membership,
              companies: companies.data ?? [],
              companyId,
              activeCompany,
              setCompanyId: onCompanyChange,
            }}
          >
            {lockNav && !onOrganisation ? (
              <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted-foreground">
                Renseignez l’identité de l’entreprise pour continuer…
              </div>
            ) : (
              children
            )}
          </TenantProvider>
          </BetaScopeProvider>
        </main>
      </div>
    </div>
  );
}

type NavItem = { href: string; label: string };

type NavGroupDef = {
  id: string;
  label: string;
  items: NavItem[];
};

function navGroupsFor(
  orgSlug: string,
  canSeeAudit: boolean,
  options: { identityPending?: boolean; betaScope?: BetaScope } = {},
): NavGroupDef[] {
  const scope = options.betaScope ?? BETA_SCOPE_OPEN;
  const root = `/app/${orgSlug}`;
  if (options.identityPending) {
    return [
      {
        id: "parametres",
        label: "Paramètres",
        items: [{ href: `${root}/organisation`, label: "Organisation" }],
      },
    ];
  }
  const groups: NavGroupDef[] = [
    {
      id: "ecritures",
      label: "Écritures",
      items: [
        { href: `${root}/journal`, label: "Livre-journal" },
        { href: `${root}/plan-comptable`, label: "Plan de comptes" },
        { href: `${root}/balance`, label: "Balance" },
        { href: `${root}/grand-livre`, label: "Grand-livre" },
      ],
    },
    {
      id: "etats",
      label: "États",
      items: [
        { href: `${root}/etats`, label: "États financiers" },
        { href: `${root}/consolides`, label: "Consolidés" },
        { href: `${root}/livres`, label: "Livres légaux" },
      ],
    },
    {
      id: "registres",
      label: "Registres",
      items: [
        { href: `${root}/tiers`, label: "Tiers" },
        { href: `${root}/tresorerie`, label: "Trésorerie" },
        { href: `${root}/immobilisations`, label: "Immobilisations" },
        { href: `${root}/engagements`, label: "Engagements" },
        { href: `${root}/classe-9`, label: "Classe 9" },
      ],
    },
    {
      id: "arrete",
      label: "Arrêté",
      items: [
        { href: `${root}/cloture`, label: "Clôture" },
        { href: `${root}/devises`, label: "Devises" },
        { href: `${root}/rse`, label: "RSE" },
      ],
    },
    {
      id: "parametres",
      label: "Paramètres",
      items: [{ href: `${root}/organisation`, label: "Organisation" }],
    },
  ];
  if (canSeeAudit) {
    groups.push({
      id: "controle",
      label: "Contrôle",
      items: [{ href: `${root}/audit`, label: "Journal d’audit" }],
    });
  }
  return groups.map((group) => ({
    ...group,
    items: group.items.filter((item) => isNavPathAllowed(item.href, scope)),
  }));
}

function pathMatches(pathname: string, href: string, exact = false) {
  if (exact) return pathname === href || pathname === `${href}/`;
  return pathname === href || pathname.startsWith(`${href}/`);
}

function NavGroup({ group, pathname }: { group: NavGroupDef; pathname: string }) {
  const hasActive = group.items.some((item) => pathMatches(pathname, item.href));
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (hasActive) setOpen(true);
  }, [hasActive]);

  const toggle = () => {
    setOpen((current) => !current);
  };

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-[11px] font-medium uppercase tracking-[0.16em] text-sidebar-foreground/55 hover:bg-white/5 hover:text-sidebar-foreground/85"
      >
        {group.label}
        {open ? <ChevronDown className="size-3.5" aria-hidden /> : <ChevronRight className="size-3.5" aria-hidden />}
      </button>
      {open && (
        <div className="mt-0.5 flex flex-col gap-0.5">
          {group.items.map((item) => (
            <NavLink key={item.href} href={item.href} label={item.label} pathname={pathname} />
          ))}
        </div>
      )}
    </div>
  );
}

function NavLink({
  href,
  label,
  pathname,
  exact = false,
  icon: Icon,
}: {
  href: string;
  label: string;
  pathname: string;
  exact?: boolean;
  icon?: typeof LayoutDashboard;
}) {
  const active = pathMatches(pathname, href, exact);
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-2 rounded-lg px-3 py-2 text-sidebar-foreground/85 hover:bg-white/5",
        active && "bg-sidebar-accent text-sidebar-accent-foreground hover:bg-sidebar-accent",
      )}
    >
      {Icon ? <Icon className="size-4" /> : null}
      {label}
    </Link>
  );
}
