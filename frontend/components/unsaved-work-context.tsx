"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

type UnsavedWorkContextValue = {
  hasUnsavedWork: boolean;
  setHasUnsavedWork: (value: boolean) => void;
};

const UnsavedWorkContext = createContext<UnsavedWorkContextValue | null>(null);

export function UnsavedWorkProvider({ children }: { children: React.ReactNode }) {
  const [hasUnsavedWork, setHasUnsavedWork] = useState(false);
  const set = useCallback((value: boolean) => setHasUnsavedWork(value), []);
  const value = useMemo(
    () => ({ hasUnsavedWork, setHasUnsavedWork: set }),
    [hasUnsavedWork, set],
  );
  return <UnsavedWorkContext.Provider value={value}>{children}</UnsavedWorkContext.Provider>;
}

export function useUnsavedWork() {
  const ctx = useContext(UnsavedWorkContext);
  if (!ctx) {
    return {
      hasUnsavedWork: false,
      setHasUnsavedWork: () => undefined,
    };
  }
  return ctx;
}
