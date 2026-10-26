"use client";

import { createContext, useContext, type ReactNode } from "react";

import type { Company, Membership } from "@/lib/types";

type TenantContextValue = {
  orgSlug: string;
  membership?: Membership;
  companies: Company[];
  companyId: string;
  activeCompany?: Company;
  setCompanyId: (id: string) => void;
};

const TenantContext = createContext<TenantContextValue | null>(null);

export function TenantProvider({
  value,
  children,
}: {
  value: TenantContextValue;
  children: ReactNode;
}) {
  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>;
}

export function useTenant() {
  const ctx = useContext(TenantContext);
  if (!ctx) {
    throw new Error("useTenant must be used within TenantProvider");
  }
  return ctx;
}
