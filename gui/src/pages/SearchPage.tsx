import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { SearchBar } from "../components/search/SearchBar";
import { SearchResults } from "../components/search/SearchResults";
import { SearchFiltersPanel } from "../components/search/SearchFiltersPanel";
import { useSearchState } from "../hooks/useSearchState";
import type { SearchHit } from "../hooks/useSearchState";
import { executeSearch, fetchSuggestions } from "../features/search/searchService";

export default function SearchPage() {
  const navigate = useNavigate();
  const [state, actions] = useSearchState(executeSearch, fetchSuggestions);

  const handleSearch = useCallback(() => {
    actions.search();
    if (state.query.trim()) actions.addRecentSearch(state.query.trim());
  }, [actions, state.query]);

  const handleSelectRecent = useCallback(
    (q: string) => {
      actions.setQuery(q);
      actions.addRecentSearch(q);
    },
    [actions],
  );

  const handleHitClick = useCallback(
    (hit: SearchHit) => {
      if (hit.type === "chapter") {
        navigate("/chapter-analysis");
      } else if (hit.type === "character") {
        navigate("/characters");
      } else {
        navigate("/chapter-analysis");
      }
    },
    [navigate],
  );

  return (
    <div className="p-4 md:p-6 space-y-5">
      <h1 className="text-2xl font-semibold text-txt">搜索</h1>

      <SearchBar
        query={state.query}
        filters={state.filters}
        suggestions={state.suggestions}
        recentSearches={state.recentSearches}
        isSearching={state.isSearching}
        onQueryChange={actions.setQuery}
        onFiltersChange={actions.setFilters}
        onSearch={handleSearch}
        onClear={actions.clearSearch}
        onFetchSuggestions={actions.fetchSuggestions}
        onSelectRecent={handleSelectRecent}
      />

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-3">
          <SearchResults
            result={state.result}
            isSearching={state.isSearching}
            error={state.error}
            onHitClick={handleHitClick}
          />
        </div>
        <div className="lg:col-span-1">
          <SearchFiltersPanel
            filters={state.filters}
            onChange={actions.setFilters}
          />
        </div>
      </div>
    </div>
  );
}
