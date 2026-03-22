/**
 * useSearchState - 搜索状态管理 hook
 * 管理搜索查询、过滤器、结果、建议、最近搜索
 */

import { useState, useCallback, useRef, useMemo, useEffect } from "react";

// ── 类型定义 ──

export interface SearchHit {
  type: "chapter" | "event" | "character";
  id: string;
  title: string;
  snippet: string;
  score: number;
  chapter_id?: string;
  chapter_title?: string;
  metadata: Record<string, unknown>;
}

export interface SearchResult {
  query: string;
  total: number;
  hits: SearchHit[];
  facets: {
    by_type?: Record<string, number>;
    by_event_type?: Record<string, number>;
  };
}

export interface SearchFilters {
  scope?: ("chapter" | "event" | "character")[];
  event_type?: string;
  min_importance?: number;
  max_importance?: number;
  flags?: Record<string, boolean>;
}

export interface SearchState {
  query: string;
  filters: SearchFilters;
  result: SearchResult | null;
  suggestions: string[];
  recentSearches: string[];
  isSearching: boolean;
  error: string | null;
}

export interface SearchActions {
  setQuery: (q: string) => void;
  setFilters: (f: Partial<SearchFilters>) => void;
  search: () => Promise<void>;
  clearSearch: () => void;
  fetchSuggestions: (prefix: string) => Promise<void>;
  addRecentSearch: (q: string) => void;
  clearRecentSearches: () => void;
}

const RECENT_SEARCHES_KEY = "novel_gui:recent_searches";
const MAX_RECENT = 15;

function loadRecentSearches(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_SEARCHES_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveRecentSearches(items: string[]): void {
  localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(items.slice(0, MAX_RECENT)));
}

/**
 * 搜索状态 hook
 *
 * @param fetcher - 执行搜索的函数 (query, filters) => SearchResult
 * @param suggestFetcher - 获取建议的函数 (prefix) => string[]
 */
export function useSearchState(
  fetcher: (query: string, filters: SearchFilters, signal?: AbortSignal) => Promise<SearchResult>,
  suggestFetcher?: (prefix: string) => Promise<string[]>,
): [SearchState, SearchActions] {
  const [query, setQuery] = useState("");
  const [filters, setFiltersState] = useState<SearchFilters>({});
  const [result, setResult] = useState<SearchResult | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [recentSearches, setRecentSearches] = useState<string[]>(loadRecentSearches);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  // Abort in-flight request on unmount
  useEffect(() => {
    return () => { abortRef.current?.abort(); };
  }, []);

  const search = useCallback(async () => {
    const q = query.trim();
    if (!q) return;

    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setIsSearching(true);
    setError(null);

    try {
      const res = await fetcher(q, filters, ctrl.signal);
      if (!ctrl.signal.aborted) {
        setResult(res);
      }
    } catch (err) {
      if (!ctrl.signal.aborted) {
        setError(err instanceof Error ? err.message : "搜索失败");
      }
    } finally {
      if (!ctrl.signal.aborted) {
        setIsSearching(false);
      }
    }
  }, [query, filters, fetcher]);

  const clearSearch = useCallback(() => {
    abortRef.current?.abort();
    setQuery("");
    setResult(null);
    setSuggestions([]);
    setError(null);
    setIsSearching(false);
  }, []);

  const fetchSuggestions = useCallback(
    async (prefix: string) => {
      if (!suggestFetcher || !prefix.trim()) {
        setSuggestions([]);
        return;
      }
      try {
        const items = await suggestFetcher(prefix);
        setSuggestions(items);
      } catch {
        setSuggestions([]);
      }
    },
    [suggestFetcher],
  );

  const setFilters = useCallback((partial: Partial<SearchFilters>) => {
    setFiltersState((prev) => ({ ...prev, ...partial }));
  }, []);

  const addRecentSearch = useCallback((q: string) => {
    setRecentSearches((prev) => {
      const next = [q, ...prev.filter((s) => s !== q)].slice(0, MAX_RECENT);
      saveRecentSearches(next);
      return next;
    });
  }, []);

  const clearRecentSearches = useCallback(() => {
    setRecentSearches([]);
    saveRecentSearches([]);
  }, []);

  const state = useMemo<SearchState>(
    () => ({ query, filters, result, suggestions, recentSearches, isSearching, error }),
    [query, filters, result, suggestions, recentSearches, isSearching, error],
  );

  const actions = useMemo<SearchActions>(
    () => ({ setQuery, setFilters, search, clearSearch, fetchSuggestions, addRecentSearch, clearRecentSearches }),
    [setQuery, setFilters, search, clearSearch, fetchSuggestions, addRecentSearch, clearRecentSearches],
  );

  return [state, actions];
}
