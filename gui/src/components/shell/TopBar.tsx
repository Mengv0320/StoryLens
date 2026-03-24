import React, { useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { BookOpen, X, Menu, Moon, Sun } from "lucide-react";
import { api } from "../../lib/api";
import { usePolling } from "../../lib/usePolling";
import { useActiveBook } from "../../lib/useActiveBook";
import { Badge } from "../primitives";
import { useDarkMode } from "../../lib/useDarkMode";
import type { BookListItem } from "../../lib/types";

type Props = { onMenuToggle?: () => void };

export default function TopBar({ onMenuToggle }: Props) {
  const [dark, toggleDark] = useDarkMode();
  const { data: status } = usePolling(() => api.getPipelineStatus(), 5_000);
  const { activeBook, setActiveBook } = useActiveBook();
  const runStatus = status?.status ?? "idle";

  // Auto-clear activeBook if it no longer exists in the backend
  const booksFetcher = useCallback(() => api.getBooks(), []);
  const { data: books } = usePolling<BookListItem[]>(booksFetcher, 10_000);
  useEffect(() => {
    if (activeBook && books) {
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

  const progress = status?.progress;
  const hasProgress = progress && progress.totalChapters > 0;
  const progressPct = hasProgress ? Math.round((progress.completedChapters / progress.totalChapters) * 100) : 0;
  const variantMap: Record<string, "default" | "success" | "warning" | "danger" | "accent"> = {
    idle: "default", running: "accent", completed: "success", failed: "danger",
  };

  return (
    <header className="h-14 md:h-16 flex-shrink-0 border-b border-border/40 bg-panel/70 backdrop-blur-xl flex items-center justify-between px-3 md:px-6 gap-2 md:gap-4 sticky top-0 z-50 shadow-sm transition-all duration-300">
      {/* 左侧：汉堡 + 产品名 */}
      <div className="flex items-center gap-2 shrink-0">
        <button
          type="button"
          onClick={onMenuToggle}
          className="md:hidden p-1.5 rounded-md text-txt-soft hover:bg-panel-muted transition-colors"
          aria-label="菜单"
        >
          <Menu size={20} />
        </button>
        <span className="text-base md:text-lg font-semibold text-txt whitespace-nowrap">StoryLens</span>
      </div>

      {/* 中部：当前激活书本 (移动端隐藏) */}
      <div className="flex-1 hidden sm:flex items-center justify-center">
        {activeBook ? (
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
        ) : (
          <span className="text-sm px-4 py-1.5 rounded-full bg-panel-muted/50 text-txt-faint border border-border/30 shadow-inner">未选中任何书籍</span>
        )}
      </div>

      {/* 右侧：管线状态 */}
      <div className="flex items-center gap-2 md:gap-3 shrink-0">
        <button
          type="button"
          onClick={toggleDark}
          className="p-1.5 rounded-md text-txt-soft hover:bg-panel-muted transition-colors"
          aria-label={dark ? "切换亮色模式" : "切换暗色模式"}
        >
          {dark ? <Sun size={16} /> : <Moon size={16} />}
        </button>
        <Badge label={runStatus} variant={variantMap[runStatus] ?? "default"} />
        {runStatus === "running" && hasProgress && (
          <div className="hidden sm:flex items-center gap-2">
            <div className="w-24 h-1.5 bg-border/40 rounded-full overflow-hidden">
              <div className="h-full bg-accent rounded-full transition-all duration-500 ease-out" style={{ width: `${progressPct}%` }} />
            </div>
            <span className="text-xs text-txt-soft whitespace-nowrap">{progress.completedChapters}/{progress.totalChapters} 章</span>
          </div>
        )}
        <span className="hidden md:inline text-xs text-txt-soft">{status?.model || "—"}</span>
      </div>
    </header>
  );
}
