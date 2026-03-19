import { useState, useEffect } from "react";
import { api } from "../lib/api";
import { usePolling } from "../lib/usePolling";
import { useRunMode } from "../lib/useRunMode";
import type { EpisodeDetail } from "../lib/types";
import { Card, SectionHeader, Badge, EmptyState, KeyValue } from "../components/primitives";

export default function EpisodesPage() {
  const mode = useRunMode();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showPlan, setShowPlan] = useState(false);
  const [detail, setDetail] = useState<EpisodeDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const { data: episodes } = usePolling(() => api.getEpisodes(), 10_000);
  const { data: plan } = usePolling(() => api.getEpisodePlan(), 10_000);

  useEffect(() => {
    if (!selectedId) { setDetail(null); return; }
    let cancelled = false;
    setDetailLoading(true);
    api.getEpisodeDetail(selectedId)
      .then(d => { if (!cancelled) setDetail(d); })
      .catch(() => { if (!cancelled) setDetail(null); })
      .finally(() => { if (!cancelled) setDetailLoading(false); });
    return () => { cancelled = true; };
  }, [selectedId]);

  const statusVariant: Record<string, "success" | "danger" | "warning"> = {
    completed: "success", failed: "danger", warning: "warning",
  };

  if (mode === "fast_scan" || mode === "standard_analysis") {
    return (
      <div className="p-6 space-y-5">
        <h1 className="text-2xl font-semibold text-txt">分集</h1>
        <Card>
          <div className="py-6 text-center space-y-3">
            <p className="text-txt-soft text-sm">
              当前模式不生成分集数据。
            </p>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-5">
      <h1 className="text-2xl font-semibold text-txt">分集</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Left column - list */}
        <div className="md:col-span-1">
          <Card>
            <SectionHeader
              title="分集列表"
              extra={
                <button
                  onClick={() => setShowPlan(p => !p)}
                  className="text-xs px-3 py-1 rounded bg-panel-muted text-txt-soft hover:bg-border"
                >
                  {showPlan ? "分集列表" : "企划表"}
                </button>
              }
            />
            <div className="space-y-1 max-h-[60vh] overflow-y-auto">
              {showPlan ? (
                !plan?.length ? <EmptyState message="暂无企划数据" /> :
                plan.map(p => (
                  <div key={p.id} className="p-2 rounded text-sm border border-border/50 space-y-1">
                    <div className="font-medium text-txt">{p.title}</div>
                    <div className="text-xs text-txt-soft">{p.chapterRangeLabel}</div>
                    <div className="text-xs text-txt-soft">{p.coreTheme}</div>
                  </div>
                ))
              ) : (
                !episodes?.length ? <EmptyState message="暂无分集数据" /> :
                episodes.map(ep => (
                  <button
                    key={ep.id}
                    onClick={() => setSelectedId(ep.id)}
                    className={`w-full text-left p-2 rounded text-sm flex items-center justify-between gap-2 ${
                      selectedId === ep.id ? "bg-accent-soft border border-accent" : "hover:bg-panel-muted border border-transparent"
                    }`}
                  >
                    <div className="min-w-0">
                      <span className="text-txt-soft mr-1.5">{ep.indexLabel}</span>
                      <span className="text-txt font-medium">{ep.title}</span>
                      <div className="text-xs text-txt-soft truncate">{ep.chapterRangeLabel}</div>
                    </div>
                    <Badge label={ep.status} variant={statusVariant[ep.status] ?? "default"} />
                  </button>
                ))
              )}
            </div>
          </Card>
        </div>

        {/* Right column - detail */}
        <div className="md:col-span-2">
          <Card>
            <SectionHeader title="分集详情" />
            {!selectedId ? (
              <EmptyState message="选择左侧分集查看详情" />
            ) : detailLoading ? (
              <div className="py-8 text-center text-txt-soft text-sm">加载中...</div>
            ) : !detail ? (
              <EmptyState message="无法加载详情" />
            ) : (
              <div className="space-y-0.5">
                <KeyValue label="标题" value={detail.title} />
                <KeyValue label="核心主题" value={detail.coreTheme} />
                <KeyValue label="钩子" value={detail.hook} />
                <KeyValue label="主要冲突" value={detail.mainConflict} />
                <KeyValue label="高潮" value={detail.climax} />
                <KeyValue label="结尾钩子" value={detail.endingHook} />
                <KeyValue label="摘要" value={detail.summary} />
                <KeyValue label="章节范围" value={detail.chapterRangeLabel} />
                <KeyValue
                  label="关键事件"
                  value={
                    <ul className="text-right space-y-0.5">
                      {detail.keyEvents.map((e, i) => (
                        <li key={i} className="text-sm">{e}</li>
                      ))}
                    </ul>
                  }
                />
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
