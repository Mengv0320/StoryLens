import { useState, useCallback, useEffect } from "react";
import { api } from "../lib/api";
import type { StandardAnalysisResult, StandardChapterResult } from "../lib/types";
import { usePolling } from "../lib/usePolling";
import { useActiveBook } from "../lib/useActiveBook";
import { Card, SectionHeader, EmptyState, Badge, SkeletonCard } from "../components/primitives";
import { displayEventType } from "../lib/eventTypes";
import { useShowMore } from "../hooks/useShowMore";

const IMPORTANCE_COLORS: Record<number, string> = {
  5: "bg-danger/20 text-danger",
  4: "bg-warning/20 text-warning",
  3: "bg-accent/20 text-accent",
  2: "bg-panel-soft text-txt-soft",
  1: "bg-panel-soft text-txt-soft",
};

function ImportanceBadge({ score }: { score: number }) {
  const cls = IMPORTANCE_COLORS[score] || "bg-panel-soft text-txt-soft";
  return <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{score}/5</span>;
}

function ChapterCard({ chapter }: { chapter: StandardChapterResult }) {
  const [expanded, setExpanded] = useState(false);
  const events = chapter.keyEvents || [];
  const tags: string[] = [];
  if (events.some(e => e.eventType === "转折" || e.eventType === "turning_point")) tags.push("转折点");
  if (events.some(e => e.involvesIdentityReveal)) tags.push("身份揭露");
  if (events.some(e => e.involvesProtagonist)) tags.push("主角相关");

  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-medium text-txt truncate">{chapter.title || chapter.chapterId}</h3>
            <ImportanceBadge score={chapter.importanceScore} />
            {tags.map((t) => (
              <span key={t} className="px-1.5 py-0.5 rounded bg-accent/10 text-accent text-xs">{t}</span>
            ))}
            {chapter.status !== "ok" && chapter.status !== "completed" && (
              <Badge label={chapter.status} variant="danger" />
            )}
          </div>
          <p className="mt-1.5 text-sm text-txt-soft line-clamp-2">{chapter.chapterSummary}</p>
          <p className="mt-1 text-xs text-txt-soft">{chapter.importanceReason}</p>
        </div>
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="shrink-0 text-xs text-accent hover:underline"
        >
          {expanded ? "收起" : `${events.length} 个事件`}
        </button>
      </div>
      {expanded && events.length > 0 && (
        <div className="mt-3 border-t border-border pt-3 space-y-2">
          {events.map((ev) => (
            <div key={ev.eventId} className="text-sm">
              <div className="flex items-center gap-2">
                <span className="px-1.5 py-0.5 rounded bg-panel-soft text-xs text-txt-soft">{displayEventType(ev.eventType)}</span>
                <span className="font-medium text-txt">{ev.title}</span>
                <span className="text-xs text-txt-soft">重要性 {ev.importance}</span>
              </div>
              <p className="mt-0.5 text-txt-soft">{ev.description}</p>
              {ev.characters.length > 0 && (
                <p className="mt-0.5 text-xs text-txt-soft">角色：{ev.characters.join("、")}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export default function ChapterAnalysisPage() {
  const [minScore, setMinScore] = useState(1);
  const { activeBook } = useActiveBook();
  const fetcher = useCallback(
    () => activeBook
      ? api.getBookLatestAnalysis(activeBook.bookId) as Promise<StandardAnalysisResult>
      : api.getStandardAnalysis(),
    [activeBook?.bookId],
  );
  const { data, error } = usePolling<StandardAnalysisResult>(fetcher, 10_000);

  const filtered = data ? data.chapters.filter((ch) => ch.importanceScore >= minScore) : [];
  const { visible: visibleChapters, hasMore, showMore, reset, total } = useShowMore(filtered, 30);

  useEffect(() => { reset(); }, [activeBook?.bookId, reset]);

  if (error) return <div className="p-4 md:p-6"><EmptyState message="暂无章节分析数据，请先前往「任务」页面完成标准分析。" /></div>;
  if (!data) return (
    <div className="p-4 md:p-6 space-y-5">
      <h1 className="text-2xl font-semibold text-txt">章节分析</h1>
      <div className="space-y-3">
        {Array.from({ length: 4 }, (_, i) => <SkeletonCard key={i} />)}
      </div>
    </div>
  );

  const genre = data.genre;

  return (
    <div className="p-4 md:p-6 space-y-5">
      <h1 className="text-2xl font-semibold text-txt">章节分析</h1>

      <Card>
        <SectionHeader title="分析概况" />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <div><div className="text-txt-soft">类型</div><div className="font-medium text-txt">{genre.primaryGenre}{genre.subgenre ? ` / ${genre.subgenre}` : ""}</div></div>
          <div><div className="text-txt-soft">总章节</div><div className="font-medium text-txt">{data.chapters.length}</div></div>
          <div><div className="text-txt-soft">失败</div><div className="font-medium text-txt">{data.failures.length}</div></div>
          <div><div className="text-txt-soft">LLM 调用</div><div className="font-medium text-txt">{data.stats?.calls?.length ?? "—"} 次</div></div>
        </div>
      </Card>

      <div className="flex items-center gap-3">
        <span className="text-sm text-txt-soft">最低重要性</span>
        <select value={minScore} onChange={(e) => setMinScore(Number(e.target.value))} className="h-8 rounded border border-border bg-panel px-2 text-sm">
          <option value={1}>全部 (1+)</option>
          <option value={2}>2+</option>
          <option value={3}>3+</option>
          <option value={4}>4+ 重要</option>
          <option value={5}>5 关键</option>
        </select>
        <span className="text-xs text-txt-soft">{filtered.length} / {data.chapters.length} 章</span>
      </div>

      <div className="space-y-3">
        {filtered.length === 0 ? (
          <EmptyState message="没有符合筛选条件的章节。" />
        ) : (<>
          {visibleChapters.map((ch) => <ChapterCard key={ch.chapterId} chapter={ch} />)}
          {hasMore && (
            <button type="button" onClick={showMore} className="w-full py-2 text-sm text-accent hover:underline">
              加载更多（已显示 {visibleChapters.length}/{total}）
            </button>
          )}
        </>)}
      </div>
    </div>
  );
}
