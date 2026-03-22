import { useState, useCallback } from "react";
import { Star, BookOpen, Zap, ChevronRight, Trash2 } from "lucide-react";

export interface FavoriteItem {
  type: "chapter" | "event";
  id: string;
  title: string;
  added_at: number;
  metadata?: Record<string, unknown>;
}

interface FavoritesListProps {
  items: FavoriteItem[];
  onNavigate?: (item: FavoriteItem) => void;
  onRemove?: (type: string, id: string) => Promise<void>;
  className?: string;
}

const TYPE_ICON = { chapter: BookOpen, event: Zap };
const TYPE_LABEL = { chapter: "章节", event: "事件" };

type FilterType = "all" | "chapter" | "event";

export function FavoritesList({
  items,
  onNavigate,
  onRemove,
  className = "",
}: FavoritesListProps) {
  const [filter, setFilter] = useState<FilterType>("all");
  const [removing, setRemoving] = useState<string | null>(null);

  const filtered = filter === "all" ? items : items.filter((i) => i.type === filter);

  const handleRemove = useCallback(
    async (type: string, id: string) => {
      if (!onRemove || removing) return;
      setRemoving(`${type}-${id}`);
      try {
        await onRemove(type, id);
      } finally {
        setRemoving(null);
      }
    },
    [onRemove, removing],
  );

  const formatDate = (ts: number) => {
    const d = new Date(ts);
    return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
  };

  return (
    <div className={`bg-panel border border-border rounded-card ${className}`}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2 text-txt text-sm font-medium">
          <Star size={16} className="text-warning" />
          <span>我的收藏</span>
          <span className="text-txt-soft text-xs">({items.length})</span>
        </div>
        <div className="flex gap-1">
          {(["all", "chapter", "event"] as FilterType[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-2 py-1 text-xs rounded transition-colors ${
                filter === f
                  ? "bg-accent/10 text-accent"
                  : "text-txt-soft hover:text-txt"
              }`}
            >
              {f === "all" ? "全部" : TYPE_LABEL[f]}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="px-4 py-8 text-center text-txt-soft text-sm">
          {items.length === 0 ? "暂无收藏" : "该分类下暂无收藏"}
        </div>
      ) : (
        <div className="divide-y divide-border max-h-96 overflow-y-auto">
          {filtered.map((item) => {
            const Icon = TYPE_ICON[item.type];
            const isRemoving = removing === `${item.type}-${item.id}`;
            return (
              <div
                key={`${item.type}-${item.id}`}
                className="flex items-center gap-3 px-4 py-2.5 hover:bg-panel-hover transition-colors"
              >
                <button
                  onClick={() => onNavigate?.(item)}
                  className="flex-1 flex items-center gap-3 text-left min-w-0"
                >
                  <Icon size={14} className="text-txt-soft shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-txt truncate">{item.title}</div>
                    <div className="text-xs text-txt-soft">
                      {TYPE_LABEL[item.type]} · {formatDate(item.added_at)}
                    </div>
                  </div>
                  <ChevronRight size={12} className="text-txt-soft/40 shrink-0" />
                </button>
                {onRemove && (
                  <button
                    onClick={() => handleRemove(item.type, item.id)}
                    disabled={isRemoving}
                    className="text-txt-soft/40 hover:text-danger transition-colors disabled:opacity-50 shrink-0"
                    title="取消收藏"
                  >
                    <Trash2 size={13} className={isRemoving ? "animate-pulse" : ""} />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
