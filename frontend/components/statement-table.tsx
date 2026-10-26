import { formatMoney } from "@/lib/money";
import type { StatementLine } from "@/lib/types";

export function StatementTable({
  lines,
  currency,
  priorYear,
  showGross = false,
}: {
  lines: StatementLine[];
  currency: string;
  priorYear: number | null;
  showGross?: boolean;
}) {
  const withGross = showGross && lines.some((line) => line.gross != null);
  return (
    <table className="w-full text-left text-sm">
      <thead className="border-b border-border text-muted-foreground">
        <tr>
          <th className="py-2 pr-3 font-medium">Poste</th>
          {withGross ? (
            <>
              <th className="py-2 pr-3 font-medium text-right">Brut</th>
              <th className="py-2 pr-3 font-medium text-right">Amort. et dép.</th>
            </>
          ) : null}
          <th className="py-2 pr-3 font-medium text-right">Net N</th>
          <th className="py-2 font-medium text-right">{priorYear ? `Net N-1 (${priorYear})` : "Net N-1"}</th>
        </tr>
      </thead>
      <tbody>
        {lines.map((line, index) => (
          <tr key={`${line.code}-${line.label}-${index}`} className="border-b border-border/70">
            <td className={`py-1.5 pr-3 ${line.bold ? "font-semibold" : ""} ${line.kind === "dont" ? "pl-6 text-muted-foreground" : ""}`}>
              {line.code ? <span className="mr-2 font-mono text-xs text-muted-foreground">{line.code}</span> : null}
              {line.label}
            </td>
            {withGross ? (
              <>
                <td className={`py-1.5 pr-3 text-right font-mono ${line.bold ? "font-semibold" : ""}`}>
                  {formatMoney(line.gross ?? "0", currency)}
                </td>
                <td className={`py-1.5 pr-3 text-right font-mono ${line.bold ? "font-semibold" : ""}`}>
                  {formatMoney(line.amort ?? "0", currency)}
                </td>
              </>
            ) : null}
            <td className={`py-1.5 pr-3 text-right font-mono ${line.bold ? "font-semibold" : ""}`}>
              {formatMoney(line.current, currency)}
            </td>
            <td className={`py-1.5 text-right font-mono ${line.bold ? "font-semibold" : ""}`}>
              {formatMoney(line.prior, currency)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
