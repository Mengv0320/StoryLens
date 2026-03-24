import { useState, useMemo, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { SectionHeader, EmptyState, SkeletonCard } from "../components/primitives";
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
  const [deletedIds, setDeletedIds] = useState<Set<string>>(new Set());

  const books: BookListItem[] = useMemo(
    () => (apiBooks ?? []).filter((b) => !deletedIds.has(b.bookId)),
    [apiBooks, deletedIds],
  );

  // Clear optimistic deletes once server confirms removal
  useEffect(() => {
    if (apiBooks && deletedIds.size > 0) {
      const freshIds = new Set(apiBooks.map((b) => b.bookId));
      setDeletedIds((prev) => {
        const next = new Set([...prev].filter((id) => freshIds.has(id)));
        return next.size === prev.size ? prev : next;
      });
    }
  }, [apiBooks, deletedIds.size]);

  const filtered = useMemo(
    () => (filter === "all" ? books : books.filter((b) => (b.latestStatus || "idle") === filter)),
    [filter, books],
  );

  const handleAction = async (bookId: string, action: string) => {
    if (action === "view" || action === "start") {
      navigate(`/book/${bookId}`);
    } else if (action === "retry") {
      navigate(`/book/${bookId}`);
    } else if (action === "delete") {
      setDeletedIds((prev) => new Set(prev).add(bookId));
      try { await api.deleteBook(bookId); } catch { /* reappears on next poll if failed */ }
    }
  };

  return (
    <div className="p-4 md:p-6 space-y-5">
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
      {!apiBooks && !error ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }, (_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState message={books.length === 0 ? (error ? "加载失败，请检查后端连接" : "书架为空") : "没有符合条件的书籍"} />
      ) : (
        <BookGrid books={filtered} onAction={handleAction} />
      )}
    </div>
  );
}
