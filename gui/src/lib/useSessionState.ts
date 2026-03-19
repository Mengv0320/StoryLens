import { useState, useCallback } from "react";

const STORAGE_PREFIX = "novel_gui:";

export function useSessionState<T>(key: string, initial: T): [T, (v: T | ((prev: T) => T)) => void] {
  const fullKey = STORAGE_PREFIX + key;

  const [value, setValue] = useState<T>(() => {
    try {
      const stored = localStorage.getItem(fullKey);
      if (stored !== null) {
        return JSON.parse(stored) as T;
      }
    } catch { /* ignore */ }
    return initial;
  });

  const set = useCallback((v: T | ((prev: T) => T)) => {
    setValue((prev) => {
      const next = typeof v === "function" ? (v as (p: T) => T)(prev) : v;
      try {
        if (next === null || next === undefined) {
          localStorage.removeItem(fullKey);
        } else {
          localStorage.setItem(fullKey, JSON.stringify(next));
        }
      } catch { /* quota */ }
      return next;
    });
  }, [fullKey]);

  return [value, set];
}
