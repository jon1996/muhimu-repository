"use client";

import { useEffect, useState } from "react";

/** Date locale YYYY-MM-DD — à n’appeler que dans un useEffect (pas au SSR). */
export function localTodayIso(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function useTodayIso(): [string, (value: string) => void] {
  const [value, setValue] = useState("");
  useEffect(() => {
    setValue((current) => current || localTodayIso());
  }, []);
  return [value, setValue];
}

export function formatInstant(iso: string): string {
  if (!iso) return "—";
  return iso.replace("T", " ").slice(0, 19);
}
