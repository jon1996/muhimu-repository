"use client";

import { cn } from "@/lib/utils";

export type ChartPoint = {
  label: string;
  value: number;
  code?: string;
};

const COLORS = ["#0A66FF", "#5B8DEF", "#94A3B8", "#22C55E", "#F59E0B", "#EF4444"];

export function BarChart({ items }: { items: ChartPoint[] }) {
  const max = Math.max(...items.map((item) => item.value), 1);
  return (
    <div className="flex h-48 items-end gap-2">
      {items.map((item) => (
        <div key={item.label} className="flex min-w-0 flex-1 flex-col items-center gap-1">
          <span className="text-[11px] text-muted-foreground">{item.value}</span>
          <div className="flex h-36 w-full items-end">
            <div
              className="w-full rounded-t bg-primary"
              style={{ height: `${Math.max((item.value / max) * 100, item.value ? 6 : 0)}%` }}
            />
          </div>
          <span className="w-full truncate text-center text-[10px] text-muted-foreground">{item.label}</span>
        </div>
      ))}
    </div>
  );
}

export function HBarChart({ items }: { items: ChartPoint[] }) {
  const max = Math.max(...items.map((item) => item.value), 1);
  if (!items.length) {
    return <p className="text-sm text-muted-foreground">Pas encore de données.</p>;
  }
  return (
    <div className="space-y-3">
      {items.map((item, index) => (
        <div key={item.code || item.label}>
          <div className="mb-1 flex items-center justify-between text-xs">
            <span>{item.label}</span>
            <span className="text-muted-foreground">{item.value}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full"
              style={{
                width: `${(item.value / max) * 100}%`,
                background: COLORS[index % COLORS.length],
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function DonutChart({ items }: { items: ChartPoint[] }) {
  const total = items.reduce((sum, item) => sum + item.value, 0) || 1;
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  return (
    <div className="flex items-center gap-5">
      <svg viewBox="0 0 120 120" className="size-36 shrink-0">
        <circle cx="60" cy="60" r={radius} fill="none" stroke="currentColor" className="text-muted" strokeWidth="14" />
        {items.map((item, index) => {
          const length = (item.value / total) * circumference;
          const circle = (
            <circle
              key={item.label}
              cx="60"
              cy="60"
              r={radius}
              fill="none"
              stroke={COLORS[index % COLORS.length]}
              strokeWidth="14"
              strokeDasharray={`${length} ${circumference - length}`}
              strokeDashoffset={-offset}
              transform="rotate(-90 60 60)"
            />
          );
          offset += length;
          return circle;
        })}
        <text x="60" y="64" textAnchor="middle" className="fill-foreground text-lg font-semibold">
          {items.reduce((sum, item) => sum + item.value, 0)}
        </text>
      </svg>
      <ul className="space-y-2 text-sm">
        {items.map((item, index) => (
          <li key={item.label} className="flex items-center gap-2">
            <span
              className={cn("size-2.5 rounded-full")}
              style={{ background: COLORS[index % COLORS.length] }}
            />
            <span>{item.label}</span>
            <span className="text-muted-foreground">{item.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
