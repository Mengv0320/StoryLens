import { useState, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { SectionHeader, EmptyState } from "../components/primitives";
import BookGrid from "../components/library/BookGrid";
import { usePolling } from "../lib/usePolling";
import { api } from "../lib/api";
import type { BookListItem } from "../lib/types";
import { getStatusBadge } from "../features/library/utils";
import { Library } from "lucide-react";

const statusFilters: (string | "all")[] = ["all", "idle", "running", "completed", "partial_failure", "failed"];

export default function LibraryPage() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<string>("all");

  const fetcher = useCallback(() => api.getBooks(), []);
  const { data: apiBooks, error } = usePolling<BookListItem[]>(fetcher, 15_000);

  const books: BookListItem[] = apiBooks ?? [];

  const filtered = useMemo(
    () => (filter === "all" ? books : books.filter((b) => (b.latestStatus || "idle") === filter)),
    [filter, books],
  );

  const handleAction = (bookId: string, action: string) => {
    if (action === "view" || action === "start") {
      navigate(`/book/${bookId}`);
    } else if (action === "retry") {
      navigate(`/book/${bookId}`);
    }
  };

  return (
    <div className="p-6 space-y-5">
      <SectionHeader
        title="书架"
        extra={
          <div className="flex items-center gap-1.5">
            <Library size={16} className="text-txt-soft" />
            <span className="text-sm text-txt-soft">{books.length} 本</span>
          </div>
        }
      />

      {/* filter bar */}
      <div className="flex flex-wrap gap-2">
        {statusFilters.map((s) => {
          const active = s === filter;
          const label = s === "all" ? "全部" : getStatusBadge(s).label;
          return (
            <button
              key={s}
              type="button"
              onClick={() => setFilter(s)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                active
                  ? "bg-accent text-white"
                  : "bg-panel-muted text-txt-soft hover:bg-panel-soft"
              }`}
            >
              {label}
            </button>
          );
        })}
      </div>

      {/* content */}
      {filtered.length === 0 ? (
        <EmptyState message={books.length === 0 ? (error ? "加载失败，请检查后端连接" : "加载中...") : "没有符合条件的书籍"} />
      ) : (
        <BookGrid books={filtered} onAction={handleAction} />
      )}
    </div>
  );
}
