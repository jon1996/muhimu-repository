export type BetaScope = {
  restrict_mode: boolean;
  consolidation: boolean;
  class9_cage: boolean;
  esg: boolean;
  escompte: boolean;
};

/** Toutes fonctionnalités ouvertes (DEV ou chargement initial). */
export const BETA_SCOPE_OPEN: BetaScope = {
  restrict_mode: false,
  consolidation: true,
  class9_cage: true,
  esg: true,
  escompte: true,
};

export type BetaScopeFeature = keyof Omit<BetaScope, "restrict_mode">;

/** Chemin ERP → feature requise (undefined = toujours visible). */
export function navPathFeature(path: string): BetaScopeFeature | undefined {
  if (path.endsWith("/consolides")) return "consolidation";
  if (path.endsWith("/classe-9")) return "class9_cage";
  if (path.endsWith("/rse")) return "esg";
  return undefined;
}

export function isNavPathAllowed(path: string, scope: BetaScope): boolean {
  const feature = navPathFeature(path);
  if (!feature) return true;
  return scope[feature];
}
