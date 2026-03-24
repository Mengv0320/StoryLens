import { useCallback } from "react";
import { api } from "../../lib/api";
import { usePolling } from "../../lib/usePolling";
import { useActiveBook } from "../../lib/useActiveBook";
import { Card, SectionHeader, Badge, EmptyState } from "../primitives";
import type { Segment, ReadingGuide } from "../../lib/types";

export default function SegmentPlan({ bookId: propBookId }: { bookId?: string }) {
  const { activeBook } = useActiveBook();
  const bookId = propBookId ?? activeBook?.bookId;

  const segFetcher = useCallback(
    () => (bookId ? api.getSegments(bookId) : Promise.reject("no book")),
    [bookId],
  );
  const guideFetcher = useCallback(
    () => (bookId ? api.getReadingGuide(bookId) : Promise.reject("no book")),
    [bookId],
  );

  const { data: segments } = usePolling<Segment[]>(segFetcher, 30_000, !!bookId);
  const { data: guide } = usePolling<ReadingGuide>(guideFetcher, 30_000, !!bookId);

  if (!bookId) return null;
  if (!segments?.length && !guide) return <EmptyState message="暂无阅读计划数据" />;

  const priorityVariant = (p: string) => {
    if (p === "high" || p === "必读") return "danger" as const;
    if (p === "medium" || p === "推荐") return "warning" as const;
    return "default" as const;
  };

  return (
    <div className="space-y-4">
      {guide && (
        <Card>
          <SectionHeader title="阅读指南" />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <div>
              <div className="text-txt-soft">必读章节</div>
              <div className="font-medium text-txt">{guide.mustReadChapters.length} 章</div>
            </div>
            <div>
              <div className="text-txt-soft">精华比例</div>
              <div className="font-medium text-txt">{Math.round(guide.estimatedEssentialRatio * 100)}%</div>
            </div>
            <div>
              <div className="text-txt-soft">可跳过段落</div>
              <div className="font-medium text-txt">{guide.skippableRanges.length} 段</div>
            </div>
            <div>
              <div className="text-txt-soft">推荐阅读序</div>
              <div className="font-medium text-txt">{guide.readingOrderSuggestion || "顺序"}</div>
            </div>
          </div>
          {guide.summaryByStage && guide.summaryByStage.length > 0 && (
            <div className="mt-3 space-y-1">
              <h4 className="text-sm font-medium text-txt">分阶段概览</h4>
              {guide.summaryByStage.map((s, i) => (
                <p key={i} className="text-sm text-txt-soft">· {s}</p>
              ))}
            </div>
          )}
        </Card>
      )}

      {segments && segments.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-txt">分段概览</h3>
          {segments.map((seg) => (
            <Card key={seg.segmentId}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-txt">{seg.chapterRange}</span>
                    <Badge label={seg.estimatedPriority} variant={priorityVariant(seg.estimatedPriority)} />
                  </div>
                  <p className="mt-1 text-sm text-txt-soft">{seg.summary}</p>
                  {seg.mainPlot && <p className="mt-1 text-xs text-txt-soft">主线：{seg.mainPlot}</p>}
                </div>
              </div>
              {seg.keyCharacters.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {seg.keyCharacters.map((c) => (
                    <span key={c} className="px-2 py-0.5 rounded bg-accent/10 text-accent text-xs">{c}</span>
                  ))}
                </div>
              )}
              {seg.mustReadChapters.length > 0 && (
                <div className="mt-1 text-xs text-txt-faint">
                  必读：{seg.mustReadChapters.join("、")}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
