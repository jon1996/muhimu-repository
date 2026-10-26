import type { AccountLevel, LedgerAccount } from "@/lib/types";

export const CLASS_PILLARS = [
  { code: "1", short: "Capitaux", color: "#0A66FF", ink: "#FFFFFF" },
  { code: "2", short: "Immos", color: "#081C3A", ink: "#FFFFFF" },
  { code: "3", short: "Stocks", color: "#8a6d3b", ink: "#FFFFFF" },
  { code: "4", short: "Tiers", color: "#7a3e2c", ink: "#FFFFFF" },
  { code: "5", short: "Tréso", color: "#2d6a4f", ink: "#FFFFFF" },
  { code: "6", short: "Charges", color: "#9f2d2d", ink: "#FFFFFF" },
  { code: "7", short: "Produits", color: "#3d6b2f", ink: "#FFFFFF" },
  { code: "8", short: "HAO", color: "#5c4d7a", ink: "#FFFFFF" },
] as const;

export const LEVEL_ORDER: AccountLevel[] = [
  "class",
  "subclass",
  "principal",
  "secondary",
  "auxiliary",
];

export const LEVEL_LABELS: Record<AccountLevel, string> = {
  class: "Classe",
  subclass: "Compte à 2 chiffres",
  principal: "Compte principal",
  secondary: "Divisionnaire",
  auxiliary: "Subdivision d'entité",
};

export const LEVEL_DEPTH: Record<AccountLevel, number> = {
  class: 0,
  subclass: 1,
  principal: 2,
  secondary: 3,
  auxiliary: 4,
};

export function classColor(code: string): string {
  return CLASS_PILLARS.find((item) => item.code === code)?.color ?? "#6b645b";
}

export function downloadTextFile(filename: string, content: string, mime = "text/csv;charset=utf-8") {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export const IMPORT_TEMPLATE = [
  "code;intitule;imputable;collectif;notes",
  "4111;Clients nationaux;oui;non;subdivision du 411",
  "411-SOCOCIM;SOCOCIM Industries;oui;non;auxiliaire client",
  "401-TOTAL;TotalEnergies Marketing;oui;non;auxiliaire fournisseur",
].join("\n");

export function buildChildrenMap(accounts: LedgerAccount[]): Map<string | null, LedgerAccount[]> {
  const map = new Map<string | null, LedgerAccount[]>();
  for (const account of accounts) {
    const key = account.parent_id;
    const list = map.get(key) ?? [];
    list.push(account);
    map.set(key, list);
  }
  for (const list of map.values()) {
    list.sort((a, b) => a.code.localeCompare(b.code, "fr"));
  }
  return map;
}

export function matchingIds(
  accounts: LedgerAccount[],
  query: string,
  classFilter: string,
  levelFilter: string,
  kindFilter: string,
): Set<string> | null {
  const normalized = query.trim().toLowerCase();
  const active =
    Boolean(normalized) || Boolean(classFilter) || Boolean(levelFilter) || Boolean(kindFilter);
  if (!active) return null;

  const byId = new Map(accounts.map((account) => [account.id, account]));
  const matched = new Set<string>();

  for (const account of accounts) {
    if (classFilter && account.account_class !== classFilter) continue;
    if (levelFilter && account.level !== levelFilter) continue;
    if (kindFilter === "postable" && !account.is_postable) continue;
    if (kindFilter === "collective" && !account.is_collective) continue;
    if (kindFilter === "custom" && account.is_syscohada) continue;
    if (kindFilter === "auxiliary" && account.level !== "auxiliary") continue;
    if (
      normalized &&
      !account.code.toLowerCase().includes(normalized) &&
      !account.label.toLowerCase().includes(normalized)
    ) {
      continue;
    }
    matched.add(account.id);
    let parentId = account.parent_id;
    while (parentId) {
      matched.add(parentId);
      parentId = byId.get(parentId)?.parent_id ?? null;
    }
  }
  return matched;
}

export function lineage(account: LedgerAccount, byId: Map<string, LedgerAccount>): LedgerAccount[] {
  const chain = [account];
  let parentId = account.parent_id;
  while (parentId) {
    const parent = byId.get(parentId);
    if (!parent) break;
    chain.unshift(parent);
    parentId = parent.parent_id;
  }
  return chain;
}
