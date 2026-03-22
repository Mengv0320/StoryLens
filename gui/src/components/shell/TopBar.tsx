import React, { useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { BookOpen, X } from "lucide-react";
import { api, getAuthHeaders } from "../../lib/api";
import { usePolling } from "../../lib/usePolling";
import { useActiveBook } from "../../lib/useActiveBook";
import { Badge } from "../primitives";
import type { BookListItem } from "../../lib/types";

export default function TopBar() {
  const { data: status } = usePolling(() => api.getPipelineStatus(), 5_000);
  const { activeBook, setActiveBook } = useActiveBook();
  const runStatus = status?.status ?? "idle";

  // Auto-clear activeBook if it no longer exists in the backend
  const booksFetcher = useCallback(() => api.getBooks(), []);
  const { data: books } = usePolling<BookListItem[]>(booksFetcher, 30_000);
  useEffect(() => {
    if (activeBook && books && books.length > 0) {
      const exists = books.some((b) => b.bookId === activeBook.bookId);
      if (!exists) setActiveBook(null);
    }
  }, [activeBook, books, setActiveBook]);

  // Browser notification when pipeline completes
  const prevStatus = React.useRef(runStatus);
  useEffect(() => {
    if (prevStatus.current === "running" && runStatus === "completed") {
      if ("Notification" in window && Notification.permission === "granted") {
        new Notification("分析完成", { body: `${status?.projectName ?? "小说"} 精炼完毕！` });
      }
    }
    prevStatus.current = runStatus;
  }, [runStatus, status?.projectName]);

  // Request notification permission on first render
  useEffect(() => {
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
  }, []);

  const progress = status?.progress;
  const hasProgress = progress && progress.totalChapters > 0;
  const progressPct = hasProgress ? Math.round((progress.completedChapters / progress.totalChapters) * 100) : 0;
  const variantMap: Record<string, "default" | "success" | "warning" | "danger" | "accent"> = {
    idle: "default", running: "accent", completed: "success", failed: "danger",
  };

  return (
    <header className="h-16 flex-shrink-0 border-b border-border/40 bg-panel/70 backdrop-blur-xl flex items-center justify-between px-6 gap-4 sticky top-0 z-50 shadow-sm transition-all duration-300">
      {/* 左侧：产品名 */}
      <span className="text-lg font-semibold text-txt whitespace-nowrap">History Pipeline</span>

      {/* 中部：当前激活书本 */}
      <div className="flex-1 flex items-center justify-center">
        {activeBook ? (
          <div className="flex flex-col items-center">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-accent-soft border border-accent/20 max-w-sm shadow-sm transition-all hover:shadow-md">
              <BookOpen size={14} className="text-accent shrink-0" />
              <Link
                to={`/book/${activeBook.bookId}`}
                className="text-sm font-medium text-accent hover:underline truncate"
                title={activeBook.title}
              >
                {activeBook.title}
              </Link>
              <button
                type="button"
                onClick={() => setActiveBook(null)}
                className="shrink-0 text-accent/60 hover:text-danger transition-colors duration-200"
                title="取消选中"
              >
                <X size={13} />
              </button>
            </div>
            <div className="mt-1">
              <button
                type="button"
                onClick={async () => {
                  try {
                    const res = await fetch(`/api/export/epub/${encodeURIComponent(activeBook.bookId)}`, {
                      headers: getAuthHeaders(),
                    });
                    if (!res.ok) throw new Error(`导出失败: HTTP ${res.status}`);
                    const blob = await res.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `${activeBook.title}.epub`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    URL.revokeObjectURL(url);
                  } catch (err) {
                    console.error("EPUB download failed:", err);
                  }
                }}
                className="text-xs font-semibold text-accent/80 hover:text-accent hover:underline flex items-center gap-1 transition-colors bg-white/50 px-2 py-0.5 rounded-full border border-accent/10"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                导出 EPUB
              </button>
            </div>
          </div>
        ) : (
          <span className="text-sm px-4 py-1.5 rounded-full bg-panel-muted/50 text-txt-faint border border-border/30 shadow-inner">未选中任何书籍</span>
        )}
      </div>

      {/* 右侧：管线状态 */}
      <div className="flex items-center gap-3 shrink-0">
        {status?.mode && (
          <span className="text-xs px-2 py-0.5 rounded bg-panel-muted text-txt-soft">
            {status.mode === "standard_analysis" ? "标准分析" : status.mode}
          </span>
        )}
        <Badge label={runStatus} variant={variantMap[runStatus] ?? "default"} />
        {runStatus === "running" && hasProgress && (
          <div className="flex items-center gap-2">
            <div className="w-24 h-1.5 bg-border/40 rounded-full overflow-hidden">
              <div className="h-full bg-accent rounded-full transition-all duration-500 ease-out" style={{ width: `${progressPct}%` }} />
            </div>
            <span className="text-xs text-txt-soft whitespace-nowrap">{progress.completedChapters}/{progress.totalChapters} 章</span>
          </div>
        )}
        <span className="text-xs text-txt-soft">{status?.model || "—"}</span>
      </div>
    </header>
  );
}
