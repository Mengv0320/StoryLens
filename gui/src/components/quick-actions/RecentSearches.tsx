import { Clock, Search, Trash2 } from "lucide-react";

interface RecentSearchesProps {
  searches: string[];
  onSelect: (query: string) => void;
  onClear: () => void;
  className?: string;
}

export function RecentSearches({
  searches,
  onSelect,
  onClear,
  className = "",
}: RecentSearchesProps) {
  if (searches.length === 0) return null;

  return (
    <div className={`bg-panel border border-border rounded-card ${className}`}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2 text-txt text-sm font-medium">
          <Clock size={16} />
          <span>最近搜索</span>
        </div>
        <button
          onClick={onClear}
          className="text-txt-secondary hover:text-danger text-xs flex items-center gap-1 transition-colors"
        >
          <Trash2 size={12} />
          清除
        </button>
      </div>
      <div className="p-2 flex flex-wrap gap-2">
        {searches.map((q) => (
          <button
            key={q}
            onClick={() => onSelect(q)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs bg-bg border border-border rounded-full text-txt-secondary hover:text-accent hover:border-accent/50 transition-colors"
          >
            <Search size={11} />
            <span className="max-w-32 truncate">{q}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
