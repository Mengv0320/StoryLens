/**
 * 全局激活书本状态 — 选定后所有分析 Tab 均基于此书。
 * 使用 localStorage 持久化，刷新后保持选中状态。
 */
import { useState, useEffect, useCallback } from "react";

export interface ActiveBook {
  bookId: string;
  title: string;
}

const STORAGE_KEY = "activeBook";

function readStored(): ActiveBook | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as ActiveBook;
  } catch {
    return null;
  }
}

// Simple event-based cross-component sync (no external state lib needed)
// Use globalThis to survive HMR — module re-execution won't discard old listeners
const listeners: Set<() => void> = ((globalThis as any).__activeBookListeners ??= new Set());
function notify() { listeners.forEach((fn) => fn()); }

/** 获取/设置当前激活的书本，全局同步。 */
export function useActiveBook() {
  const [active, setActive] = useState<ActiveBook | null>(readStored);

  useEffect(() => {
    const handler = () => setActive(readStored());
    listeners.add(handler);
    return () => { listeners.delete(handler); };
  }, []);

  const setActiveBook = useCallback((book: ActiveBook | null) => {
    if (book) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(book));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
    setActive(book);
    notify();
  }, []);

  return { activeBook: active, setActiveBook };
}
