import { useCallback, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { BookOpen, ArrowLeft, CheckCircle2 } from "lucide-react";
import { Card, SectionHeader, Badge, KeyValue, EmptyState } from "../components/primitives";
import { usePolling } from "../lib/usePolling";
import { api } from "../lib/api";
import type { BookListItem, BookChapter } from "../lib/types";
import { useActiveBook } from "../lib/useActiveBook";
import { recordRecentView } from "../components/quick-actions/RecentViews";

const statusMap: Record<string, { label: string; variant: "default" | "success" | "warning" | "danger" }> = {
  idle: { label: "未分析", variant: "default" },
  running: { label: "分析中", variant: "warning" },
  completed: { label: "已完成", variant: "success" },
  failed: { label: "失败", variant: "danger" },
  partial_failure: { label: "部分失败", variant: "warning" },
};

export default function BookDetailPage() {
  const { bookId } = useParams<{ bookId: string }>();
  const { activeBook, setActiveBook } = useActiveBook();

  const bookFetcher = useCallback(() => (bookId ? api.getBook(bookId) : Promise.reject("no id")), [bookId]);
  const chaptersFetcher = useCallback(() => (bookId ? api.getBookChapters(bookId) : Promise.reject("no id")), [bookId]);

  const { data: apiBook } = usePolling<BookListItem>(bookFetcher, 30_000, !!bookId);
  const { data: apiChapters } = usePolling<BookChapter[]>(chaptersFetcher, 30_000, !!bookId);

  const title = apiBook?.title || "加载中...";
  const chapterCount = apiBook?.chapterCount ?? 0;
  const latestStatus = apiBook?.latestStatus ?? "idle";
  const latestMode = apiBook?.latestMode ?? "";
  const st = statusMap[latestStatus] ?? statusMap.idle;

  const chapters = apiChapters ?? null;

  const analyzedCount = chapters?.filter((c) => c.status === "ok" || c.importanceScore > 0).length ?? 0;
  const progress = chapterCount > 0 ? Math.round((analyzedCount / chapterCount) * 100) : 0;

  // 书名加载后自动激活为当前书本（书名是"加载中"时不写入）
  useEffect(() => {
    if (bookId && title && title !== "加载中...") {
      setActiveBook({ bookId, title });
      recordRecentView({ type: "chapter", id: bookId, label: title, path: `/book/${bookId}` });
    }
  }, [bookId, title, setActiveBook]);

  const isCurrentActive = activeBook?.bookId === bookId;

  return (
    <div className="p-6 space-y-5">
      {/* Back + Title */}
      <div className="flex items-center gap-3">
        <Link to="/library" className="text-txt-soft hover:text-accent transition-colors">
          <ArrowLeft size={20} />
        </Link>
        <h1 className="text-2xl font-semibold text-txt">{title}</h1>
        {latestMode && <Badge label={latestMode === "standard_analysis" ? "标准分析" : latestMode} variant="accent" />}
        <Badge label={st.label} variant={st.variant} />
      </div>

      {/* Overview */}
      <Card>
        <SectionHeader title="书籍概览" />
        <div className="space-y-2">
          <KeyValue label="总章节数" value={`${chapterCount} 章`} />
          <KeyValue label="已分析" value={`${analyzedCount} 章`} />
          <div className="flex items-center gap-3 py-2">
            <span className="text-sm text-txt-soft w-20 shrink-0">分析进度</span>
            <div className="flex-1 h-2 rounded-full bg-panel-soft">
              <div className="h-full bg-accent rounded-full transition-all" style={{ width: `${progress}%` }} />
            </div>
            <span className="text-sm text-txt-soft">{progress}%</span>
          </div>
        </div>
      </Card>

      {/* Actions */}
      <div className="flex items-center gap-3 flex-wrap">
        {bookId && (
          <Link
            to={`/reader/${bookId}`}
            className="flex items-center gap-2 px-4 py-2 rounded-md border border-border/50 bg-white text-txt-soft text-sm shadow-sm hover:bg-panel-soft hover:text-txt transition-all duration-200"
          >
            <BookOpen className="w-4 h-4" />
            打开阅读器
          </Link>
        )}
        {/* 激活状态标识 */}
        {isCurrentActive ? (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent-soft border border-accent/20 text-sm text-accent">
            <CheckCircle2 size={14} />
            当前分析目标
          </div>
        ) : bookId && title !== "加载中..." ? (
          <button
            type="button"
            onClick={() => setActiveBook({ bookId, title })}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border bg-white text-txt-soft text-sm shadow-sm hover:bg-panel-soft hover:text-txt transition-all duration-200"
          >
            <CheckCircle2 size={14} />
            设为当前分析目标
          </button>
        ) : null}
      </div>

      {/* Chapter list */}
      {!chapters ? (
        <EmptyState message="加载章节中..." />
      ) : (
        <Card>
          <SectionHeader title="章节目录" extra={<Badge label={`${chapters.length} 章`} variant="default" />} />
          <div className="divide-y divide-border/50 max-h-[600px] overflow-y-auto">
            {chapters.map((ch, i) => (
              <div key={ch.chapterId} className="flex items-center gap-3 py-2 text-sm">
                <span className="w-8 text-txt-faint text-right">{i + 1}</span>
                <span className={`w-2 h-2 rounded-full shrink-0 ${ch.status === "ok" || ch.importanceScore > 0 ? "bg-success" : "bg-panel-muted"}`} />
                <span className="flex-1 text-txt truncate">{ch.title}</span>
                {ch.importanceScore > 0 && (
                  <Badge label={`${ch.importanceScore}/5`} variant={ch.importanceScore >= 4 ? "success" : ch.importanceScore >= 3 ? "warning" : "default"} />
                )}
                <span className="text-txt-faint text-xs">{ch.eventCount} 事件</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
