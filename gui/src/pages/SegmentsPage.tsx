import { useState, useCallback } from "react";
import { api } from "../lib/api";
import type { ScanSegment } from "../lib/types";
import { usePolling } from "../lib/usePolling";
import { Card, SectionHeader, Badge, EmptyState, KeyValue } from "../components/primitives";

export default function SegmentsPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const { data: segments, refresh } = usePolling<ScanSegment[]>(
    useCallback(() => api.getScanSegments(), []), 10_000,
  );

  const handleRetrySegments = async () => {
    setRetrying(true);
    try {
      await api.retryMissing("segments");
      refresh();
    } catch (e) {
      console.error("Retry failed:", e);
    } finally {
      setRetrying(false);
    }
  };

  const selected = segments?.find(s => s.segmentId === selectedId) ?? null;

  const statusVariant: Record<string, "success" | "danger" | "warning" | "default"> = {
    completed: "success", failed: "danger", pending: "warning",
  };

  return (
    <div className="p-6 space-y-5">
      <h1 className="text-2xl font-semibold text-txt">分段浏览</h1>
      {!segments?.length ? (
        <Card><EmptyState message="尚未生成分段数据。请先运行快速扫书。" /></Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Left - list */}
          <div className="md:col-span-1">
            <Card>
              <SectionHeader title={`段落列表 (${segments.length})`} />
              <div className="space-y-1 max-h-[65vh] overflow-y-auto">
                {segments.map(seg => (
                  <button
                    key={seg.segmentId}
                    onClick={() => setSelectedId(seg.segmentId)}
                    className={`w-full text-left p-2.5 rounded text-sm flex items-center justify-between gap-2 ${
                      selectedId === seg.segmentId ? "bg-accent-soft border border-accent" : "hover:bg-panel-muted border border-transparent"
                    }`}
                  >
                    <div className="min-w-0">
                      <span className="text-txt font-medium">{seg.segmentId}</span>
                      <div className="text-xs text-txt-soft truncate">{seg.chapterRange}</div>
                      <div className="text-xs text-txt-soft truncate mt-0.5">{seg.mainPlot?.slice(0, 60) || seg.summary?.slice(0, 60) || ""}</div>
                    </div>
                    <div className="flex flex-col items-end gap-1 flex-shrink-0">
                      <Badge label={seg.status} variant={statusVariant[seg.status] ?? "default"} />
                      <Badge label={seg.estimatedPriority ?? "normal"} variant={seg.estimatedPriority === "high" ? "danger" : seg.estimatedPriority === "normal" ? "info" : "default"} />
                    </div>
                  </button>
                ))}
              </div>
            </Card>
          </div>

          {/* Right - detail */}
          <div className="md:col-span-2">
            <Card>
              <SectionHeader title="段落详情" />
              {!selected ? (
                <EmptyState message="选择左侧段落查看详情" />
              ) : selected.status === "failed" ? (
                <div className="space-y-2">
                  <Badge label="失败" variant="danger" />
                  <p className="text-sm text-danger">{selected.error || "未知错误"}</p>
                  <button
                    onClick={handleRetrySegments}
                    disabled={retrying}
                    className="mt-2 px-3 py-1.5 text-sm rounded bg-accent text-white hover:bg-accent/80 disabled:opacity-50"
                  >
                    {retrying ? "补跑中..." : "补跑失败分段"}
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="space-y-0.5">
                    <KeyValue label="段落 ID" value={selected.segmentId} />
                    <KeyValue label="章节范围" value={selected.chapterRange} />
                    <KeyValue label="章节数" value={selected.chapterIds?.length ?? 0} />
                    <KeyValue label="候选章节" value={selected.candidateChapters?.length ?? 0} />
                    <KeyValue label="优先级" value={<Badge label={selected.estimatedPriority ?? "normal"} variant={selected.estimatedPriority === "high" ? "danger" : "info"} />} />
                  </div>

                  {selected.summary && (
                    <div>
                      <h3 className="text-sm font-semibold text-txt mb-1">摘要</h3>
                      <p className="text-sm text-txt-soft leading-relaxed whitespace-pre-wrap">{selected.summary}</p>
                    </div>
                  )}

                  {selected.mainPlot && (
                    <div>
                      <h3 className="text-sm font-semibold text-txt mb-1">主线</h3>
                      <p className="text-sm text-txt-soft leading-relaxed">{selected.mainPlot}</p>
                    </div>
                  )}

                  {(selected.keyCharacters?.length ?? 0) > 0 && (
                    <div>
                      <h3 className="text-sm font-semibold text-txt mb-1">关键角色</h3>
                      <div className="flex flex-wrap gap-1.5">
                        {selected.keyCharacters!.map((c, i) => <Badge key={i} label={c} variant="accent" />)}
                      </div>
                    </div>
                  )}

                  {(selected.mustReadChapters?.length ?? 0) > 0 && (
                    <div>
                      <h3 className="text-sm font-semibold text-txt mb-1">必读章节</h3>
                      <div className="flex flex-wrap gap-1.5">
                        {selected.mustReadChapters!.map((c, i) => <Badge key={i} label={c} variant="success" />)}
                      </div>
                    </div>
                  )}

                  {(selected.skippableRanges?.length ?? 0) > 0 && (
                    <div>
                      <h3 className="text-sm font-semibold text-txt mb-1">可跳过</h3>
                      <div className="flex flex-wrap gap-1.5">
                        {selected.skippableRanges!.map((r, i) => <Badge key={i} label={r} variant="default" />)}
                      </div>
                    </div>
                  )}

                  {(selected.openThreads?.length ?? 0) > 0 && (
                    <div>
                      <h3 className="text-sm font-semibold text-txt mb-1">未解悬念</h3>
                      <ul className="space-y-1">
                        {selected.openThreads!.map((t, i) => (
                          <li key={i} className="text-sm text-txt-soft">• {t}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
