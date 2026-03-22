import { useState, useCallback } from "react";

const STORAGE_PREFIX = "novel_gui:";

export function useSessionState<T>(
  key: string,
  initial: T,
  validate?: (v: unknown) => v is T,
): [T, (v: T | ((prev: T) => T)) => void] {
  const fullKey = STORAGE_PREFIX + key;

  const [value, setValue] = useState<T>(() => {
    try {
      const stored = sessionStorage.getItem(fullKey);
      if (stored !== null) {
        const parsed: unknown = JSON.parse(stored);
        if (validate) {
          return validate(parsed) ? parsed : initial;
        }
        return parsed as T;
      }
    } catch { /* ignore */ }
    return initial;
  });

  const set = useCallback((v: T | ((prev: T) => T)) => {
    setValue((prev) => {
      const next = typeof v === "function" ? (v as (p: T) => T)(prev) : v;
      try {
        if (next === null || next === undefined) {
          sessionStorage.removeItem(fullKey);
        } else {
          sessionStorage.setItem(fullKey, JSON.stringify(next));
        }
      } catch { /* quota */ }
      return next;
    });
  }, [fullKey]);

  return [value, set];
}
