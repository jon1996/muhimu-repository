"use client";

import { createContext, useContext, type ReactNode } from "react";

import { BETA_SCOPE_OPEN, type BetaScope } from "@/lib/beta-scope";

const BetaScopeContext = createContext<BetaScope>(BETA_SCOPE_OPEN);

export function BetaScopeProvider({
  value,
  children,
}: {
  value: BetaScope;
  children: ReactNode;
}) {
  return <BetaScopeContext.Provider value={value}>{children}</BetaScopeContext.Provider>;
}

export function useBetaScope(): BetaScope {
  return useContext(BetaScopeContext);
}
