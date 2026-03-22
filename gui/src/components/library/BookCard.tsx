import { Link } from "react-router-dom";
import { Badge, Card, KeyValue } from "../primitives";
import { getStatusBadge, getModeLabel, formatTime } from "../../features/library/utils";
import type { BookListItem } from "../../lib/types";
import { BookOpen, Play, RotateCw, Trash2, Sparkles } from "lucide-react";
import { api } from "../../lib/api";

type Props = {
  book: BookListItem;
  onAction?: (bookId: string, action: string) => void;
};

export default function BookCard({ book, onAction }: Props) {
  const status = book.latestStatus || "idle";
  const badge = getStatusBadge(status);

  return (
    <Card className="flex flex-col gap-3">
      {/* header — clickable title links to detail */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <BookOpen size={18} className="shrink-0 text-txt-soft" />
          <Link to={`/book/${book.bookId}`} className="text-base font-semibold text-txt truncate hover:text-accent transition-colors">
            {book.title}
          </Link>
        </div>
        <Badge label={badge.label} variant={badge.variant} />
      </div>

      {/* meta */}
      <div className="space-y-0.5">
        <KeyValue label="章节数" value={book.chapterCount} />
        <KeyValue label="分析模式" value={getModeLabel(book.latestMode || null)} />
        {book.updatedAt && <KeyValue label="更新时间" value={formatTime(book.updatedAt)} />}
      </div>

      {/* actions */}
      <div className="flex gap-2 mt-auto pt-2 border-t border-border/50">
        {status === "idle" && (
          <ActionBtn icon={<Play size={14} />} label="开始分析" onClick={() => onAction?.(book.bookId, "start")} />
        )}
        {(status === "failed" || status === "partial_failure") && (
          <ActionBtn icon={<RotateCw size={14} />} label="重试" onClick={() => onAction?.(book.bookId, "retry")} />
        )}
        {status === "completed" && (
          <Link
            to={`/book/${book.bookId}`}
            className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-txt-soft hover:bg-panel-soft transition-colors"
          >
            <BookOpen size={14} />
            查看结果
          </Link>
        )}
        {status === "running" && (
          <span className="text-xs text-txt-faint py-1">分析进行中…</span>
        )}
        <button
          type="button"
          onClick={async () => {
            try {
              const res = await api.recleanBook(book.bookId);
              alert(`清洗完成，处理了 ${res.cleanedChapters} 章`);
              onAction?.(book.bookId, "recleaned");
            } catch (err) {
              alert(`清洗失败：${err instanceof Error ? err.message : '未知错误'}`);
            }
          }}
          className="flex items-center gap-1 rounded-md px-2 py-1.5 text-xs text-txt-soft hover:text-accent hover:bg-panel-soft transition-colors"
          title="清洗水印"
        >
          <Sparkles size={13} />
        </button>
        <button
          type="button"
          onClick={async () => {
            if (!confirm(`确定删除「${book.title}」的所有数据吗？此操作不可恢复。`)) return;
            try {
              await api.deleteBook(book.bookId);
              onAction?.(book.bookId, "deleted");
            } catch (err) {
              console.error('Failed to delete book:', err);
              alert(`删除失败：${err instanceof Error ? err.message : '未知错误'}`);
            }
          }}
          className="ml-auto flex items-center gap-1 rounded-md px-2 py-1.5 text-xs text-danger/70 hover:text-danger hover:bg-danger-soft/50 transition-colors"
          title="删除书籍"
        >
          <Trash2 size={13} />
        </button>
      </div>
    </Card>
  );
}

function ActionBtn({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick?: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-txt-soft hover:bg-panel-soft transition-colors"
    >
      {icon}
      {label}
    </button>
  );
}
