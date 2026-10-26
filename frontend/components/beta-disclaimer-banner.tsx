import { AlertTriangle } from "lucide-react";

/** Bandeau bêta privée — données fictives, pas de revendication de certification (PDF-CLAIM). */
export function BetaDisclaimerBanner({ className = "" }: { className?: string }) {
  return (
    <div
      role="status"
      className={`flex gap-3 rounded-lg border border-amber-200/80 bg-amber-50 px-4 py-3 text-sm text-amber-950 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-100 ${className}`}
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-700 dark:text-amber-400" aria-hidden />
      <div className="space-y-1">
        <p className="font-medium">Bêta privée — données fictives uniquement</p>
        <p className="text-amber-900/90 dark:text-amber-100/90">
          MUHIMU Accounting est en phase de test. Les états financiers (SN / SMT) suivent le référentiel
          SYSCOHADA à titre descriptif ; la correspondance des postes et la présentation sont en cours de
          validation. Aucune certification de conformité n&apos;est revendiquée — les PDF exportés ne sont pas
          destinés au dépôt réglementaire.
        </p>
      </div>
    </div>
  );
}
