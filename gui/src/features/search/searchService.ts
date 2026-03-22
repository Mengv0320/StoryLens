/**
 * searchService - 搜索服务层
 * 封装搜索 API 调用，供 useSearchState 使用。
 */

import type { SearchResult, SearchFilters } from "../../hooks/useSearchState";
import { getJson, postJson } from "../../lib/api";

export async function executeSearch(
  query: string,
  filters: SearchFilters,
): Promise<SearchResult> {
  return postJson<SearchResult>("/api/search", {
    query,
    scope: filters.scope,
    event_type: filters.event_type,
    min_importance: filters.min_importance ?? 0,
    max_importance: filters.max_importance ?? 5,
    flags: filters.flags,
    limit: 50,
  });
}

export async function fetchSuggestions(prefix: string): Promise<string[]> {
  try {
    const data = await getJson<{ suggestions: string[] }>(
      `/api/search/suggestions?prefix=${encodeURIComponent(prefix)}&limit=10`
    );
    return data.suggestions ?? [];
  } catch {
    return [];
  }
}
