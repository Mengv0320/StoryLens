import { useState, useCallback, useEffect } from "react";
import { Clock, ChevronRight, Trash2, BookOpen, Zap, User } from "lucide-react";

export interface RecentViewItem {
  type: "chapter" | "event" | "character";
  id: string;
  label: string;
  sublabel?: string;
  timestamp: number;
  path?: string;
}

interface RecentViewsProps {
  maxItems?: number;
  onNavigate?: (item: RecentViewItem) => void;
  className?: string;
}

const STORAGE_KEY = "novel_gui:recent_views";
const DEFAULT_MAX = 20;

function loadItems(): RecentViewItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveItems(items: RecentViewItem[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
}

/** 供外部调用：记录一次查看 */
export function recordRecentView(item: Omit<RecentViewItem, "timestamp">): void {
  const items = loadItems();
  const next = [
    { ...item, timestamp: Date.now() },
    ...items.filter((i) => !(i.type === item.type && i.id === item.id)),
  ].slice(0, 50);
  saveItems(next);
  window.dispatchEvent(new CustomEvent("recent-views-updated"));
}

const TYPE_ICON = {
  chapter: BookOpen,
  event: Zap,
  character: User,
};

const TYPE_LABEL = {
  chapter: "章节",
  event: "事件",
  character: "角色",
};

export function RecentViews({
  maxItems = DEFAULT_MAX,
  onNavigate,
  className = "",
}: RecentViewsProps) {
  const [items, setItems] = useState<RecentViewItem[]>(loadItems);

  useEffect(() => {
    const handler = () => setItems(loadItems());
    window.addEventListener("recent-views-updated", handler);
    window.addEventListener("storage", handler);
    return () => {
      window.removeEventListener("recent-views-updated", handler);
      window.removeEventListener("storage", handler);
    };
  }, []);

  const clearAll = useCallback(() => {
    saveItems([]);
    setItems([]);
  }, []);

  const displayed = items.slice(0, maxItems);

  if (displayed.length === 0) {
    return (
      <div className={`bg-panel border border-border rounded-card p-4 ${className}`}>
        <div className="flex items-center gap-2 text-txt-soft text-sm">
          <Clock size={16} />
          <span>暂无最近查看记录</span>
        </div>
      </div>
    );
  }

  const formatTime = (ts: number) => {
    const diff = Date.now() - ts;
    if (diff < 60000) return "刚刚";
    if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`;
    return `${Math.floor(diff / 86400000)}天前`;
  };

  return (
    <div className={`bg-panel border border-border rounded-card ${className}`}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2 text-txt text-sm font-medium">
          <Clock size={16} />
          <span>最近查看</span>
          <span className="text-txt-soft text-xs">({displayed.length})</span>
        </div>
        <button
          onClick={clearAll}
          className="text-txt-soft hover:text-danger text-xs flex items-center gap-1 transition-colors"
        >
          <Trash2 size={12} />
          清除
        </button>
      </div>
      <div className="divide-y divide-border max-h-80 overflow-y-auto">
        {displayed.map((item) => {
          const Icon = TYPE_ICON[item.type];
          return (
            <button
              key={`${item.type}-${item.id}`}
              onClick={() => onNavigate?.(item)}
              className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-panel-hover transition-colors text-left"
            >
              <Icon size={14} className="text-txt-soft shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-sm text-txt truncate">{item.label}</div>
                <div className="text-xs text-txt-soft flex items-center gap-2">
                  <span>{TYPE_LABEL[item.type]}</span>
                  {item.sublabel && (
                    <>
                      <span>·</span>
                      <span className="truncate">{item.sublabel}</span>
                    </>
                  )}
                </div>
              </div>
              <span className="text-xs text-txt-soft/60 shrink-0">{formatTime(item.timestamp)}</span>
              <ChevronRight size={12} className="text-txt-soft/40 shrink-0" />
            </button>
          );
        })}
      </div>
    </div>
  );
}
