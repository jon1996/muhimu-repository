"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import type { ReactNode } from "react";

import { useBetaScope } from "@/components/beta-scope-context";
import type { BetaScopeFeature } from "@/lib/beta-scope";

const LABELS: Record<BetaScopeFeature, string> = {
  consolidation: "Consolidation",
  class9_cage: "Classe 9 / CAGE",
  esg: "RSE / ESG",
  escompte: "Escompte d’effet",
};

export function BetaScopeGate({
  feature,
  children,
}: {
  feature: BetaScopeFeature;
  children: ReactNode;
}) {
  const scope = useBetaScope();
  const params = useParams<{ orgSlug: string }>();
  const orgSlug = params.orgSlug;

  if (scope[feature]) {
    return <>{children}</>;
  }

  return (
    <div className="mx-auto max-w-lg space-y-4 py-16 text-center">
      <h1 className="font-serif text-2xl">Hors périmètre bêta</h1>
      <p className="text-sm text-muted-foreground">
        {LABELS[feature]} n’est pas proposé dans cette phase de la bêta privée. L’accès direct par URL est
        également refusé côté API.
      </p>
      {orgSlug ? (
        <Link
          href={`/app/${orgSlug}`}
          className="inline-flex h-9 items-center justify-center rounded-md border border-input bg-background px-4 text-sm font-medium hover:bg-accent"
        >
          Retour au tableau de bord
        </Link>
      ) : null}
    </div>
  );
}
