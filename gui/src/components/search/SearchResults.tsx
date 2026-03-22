import { BookOpen, Zap, User } from "lucide-react";
import type { SearchHit, SearchResult as SearchResultType } from "../../hooks/useSearchState";

interface SearchResultsProps {
  result: SearchResultType | null;
  isSearching: boolean;
  error: string | null;
  onHitClick?: (hit: SearchHit) => void;
  className?: string;
}

const TYPE_CONFIG: Record<string, { icon: typeof BookOpen; label: string; color: string }> = {
  chapter: { icon: BookOpen, label: "章节", color: "text-accent" },
  event: { icon: Zap, label: "事件", color: "text-warning" },
  character: { icon: User, label: "角色", color: "text-success" },
};

function HitCard({ hit, onClick }: { hit: SearchHit; onClick?: () => void }) {
  const config = TYPE_CONFIG[hit.type] || TYPE_CONFIG.chapter;
  const Icon = config.icon;

  return (
    <button
      onClick={onClick}
      className="w-full text-left bg-panel border border-border rounded-card p-3 hover:border-accent/30 transition-colors group"
    >
      <div className="flex items-center gap-2 mb-1">
        <Icon size={14} className={config.color} />
        <span className={`text-xs font-medium ${config.color}`}>{config.label}</span>
        {hit.chapter_title && hit.type !== "chapter" && (
          <span className="text-xs text-txt-soft ml-auto truncate max-w-[40%]">
            {hit.chapter_title}
          </span>
        )}
      </div>
      <div className="text-sm text-txt font-medium group-hover:text-accent transition-colors">
        {hit.title}
      </div>
      {hit.snippet && (
        <div className="text-xs text-txt-soft mt-1 line-clamp-2">{hit.snippet}</div>
      )}
    </button>
  );
}

export function SearchResults({
  result,
  isSearching,
  error,
  onHitClick,
  className = "",
}: SearchResultsProps) {
  if (error) {
    return (
      <div className={`text-sm text-danger bg-danger/5 border border-danger/20 rounded-card p-3 ${className}`}>
        {error}
      </div>
    );
  }

  if (isSearching) {
    return (
      <div className={`flex items-center justify-center py-8 ${className}`}>
        <div className="w-5 h-5 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
        <span className="ml-2 text-sm text-txt-soft">搜索中...</span>
      </div>
    );
  }

  if (!result) return null;

  if (result.total === 0) {
    return (
      <div className={`text-center py-8 ${className}`}>
        <p className="text-sm text-txt-soft">
          未找到与 "<span className="text-txt">{result.query}</span>" 相关的结果
        </p>
      </div>
    );
  }

  const facetEntries = result.facets?.by_type
    ? Object.entries(result.facets.by_type)
    : [];

  return (
    <div className={className}>
      <div className="flex items-center gap-3 mb-3">
        <span className="text-xs text-txt-soft">
          找到 <span className="text-txt font-medium">{result.total}</span> 条结果
        </span>
        {facetEntries.map(([type, count]) => {
          const config = TYPE_CONFIG[type];
          if (!config) return null;
          return (
            <span key={type} className={`text-xs ${config.color}`}>
              {config.label} {count}
            </span>
          );
        })}
      </div>

      <div className="flex flex-col gap-2">
        {result.hits.map((hit) => (
          <HitCard
            key={`${hit.type}-${hit.id}`}
            hit={hit}
            onClick={() => onHitClick?.(hit)}
          />
        ))}
      </div>
    </div>
  );
}
