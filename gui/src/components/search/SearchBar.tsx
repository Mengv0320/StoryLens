import { useState, useRef, useEffect, useCallback } from "react";
import { Search, X, Clock, ArrowRight } from "lucide-react";
import type { SearchFilters } from "../../hooks/useSearchState";

interface SearchBarProps {
  query: string;
  filters: SearchFilters;
  suggestions: string[];
  recentSearches: string[];
  isSearching: boolean;
  onQueryChange: (q: string) => void;
  onFiltersChange: (f: Partial<SearchFilters>) => void;
  onSearch: () => void;
  onClear: () => void;
  onFetchSuggestions: (prefix: string) => void;
  onSelectRecent: (q: string) => void;
  className?: string;
}

const SCOPES: { label: string; value: SearchFilters["scope"] }[] = [
  { label: "全部", value: undefined },
  { label: "章节", value: ["chapter"] },
  { label: "事件", value: ["event"] },
  { label: "角色", value: ["character"] },
];

export function SearchBar({
  query,
  filters,
  suggestions,
  recentSearches,
  isSearching,
  onQueryChange,
  onFiltersChange,
  onSearch,
  onClear,
  onFetchSuggestions,
  onSelectRecent,
  className = "",
}: SearchBarProps) {
  const [isFocused, setIsFocused] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const dropdownItems = query.trim()
    ? suggestions.map((s) => ({ label: s, type: "suggestion" as const }))
    : recentSearches.map((s) => ({ label: s, type: "recent" as const }));

  const showDropdown = isFocused && dropdownItems.length > 0;

  useEffect(() => {
    clearTimeout(debounceRef.current);
    if (query.trim()) {
      debounceRef.current = setTimeout(() => onFetchSuggestions(query), 300);
    }
    return () => clearTimeout(debounceRef.current);
  }, [query, onFetchSuggestions]);

  useEffect(() => setActiveIndex(-1), [dropdownItems.length]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(e.target as Node)
      ) {
        setIsFocused(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!showDropdown) {
        if (e.key === "Enter") onSearch();
        return;
      }
      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setActiveIndex((i) => Math.min(i + 1, dropdownItems.length - 1));
          break;
        case "ArrowUp":
          e.preventDefault();
          setActiveIndex((i) => Math.max(i - 1, 0));
          break;
        case "Enter":
          e.preventDefault();
          if (activeIndex >= 0 && activeIndex < dropdownItems.length) {
            const item = dropdownItems[activeIndex];
            onQueryChange(item.label);
            onSelectRecent(item.label);
            setIsFocused(false);
          }
          onSearch();
          break;
        case "Escape":
          setIsFocused(false);
          break;
      }
    },
    [showDropdown, activeIndex, dropdownItems, onSearch, onQueryChange, onSelectRecent],
  );

  const currentScope = filters.scope;
  const scopeKey = currentScope ? currentScope.join(",") : "all";

  return (
    <div className={`relative ${className}`}>
      <div className="flex items-center gap-2 bg-panel border border-border rounded-card px-3 py-2 focus-within:border-accent transition-colors">
        <Search size={16} className="text-txt-soft shrink-0" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onKeyDown={handleKeyDown}
          placeholder="搜索章节、事件、角色..."
          className="flex-1 bg-transparent text-txt text-sm outline-none placeholder:text-txt-soft/50"
        />
        {isSearching && (
          <div className="w-4 h-4 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
        )}
        {query && !isSearching && (
          <button
            onClick={onClear}
            className="text-txt-soft hover:text-txt transition-colors"
          >
            <X size={14} />
          </button>
        )}
      </div>

      <div className="flex gap-1.5 mt-2">
        {SCOPES.map((s) => {
          const key = s.value ? s.value.join(",") : "all";
          const active = key === scopeKey;
          return (
            <button
              key={key}
              onClick={() => onFiltersChange({ scope: s.value })}
              className={`px-2.5 py-0.5 text-xs rounded-full border transition-colors ${
                active
                  ? "bg-accent/10 text-accent border-accent/30"
                  : "bg-panel text-txt-soft border-border hover:border-accent/20"
              }`}
            >
              {s.label}
            </button>
          );
        })}
      </div>

      {showDropdown && (
        <div
          ref={dropdownRef}
          className="absolute z-50 top-[calc(100%+4px)] left-0 right-0 bg-panel border border-border rounded-card shadow-card overflow-hidden"
        >
          {dropdownItems.map((item, i) => (
            <button
              key={`${item.type}-${item.label}`}
              onMouseDown={(e) => {
                e.preventDefault();
                onQueryChange(item.label);
                onSelectRecent(item.label);
                setIsFocused(false);
                onSearch();
              }}
              onMouseEnter={() => setActiveIndex(i)}
              className={`w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors ${
                i === activeIndex ? "bg-accent/10 text-accent" : "text-txt hover:bg-panel-hover"
              }`}
            >
              {item.type === "recent" ? (
                <Clock size={13} className="text-txt-soft shrink-0" />
              ) : (
                <ArrowRight size={13} className="text-txt-soft shrink-0" />
              )}
              <span className="truncate">{item.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
