import { useCallback } from "react";
import { api } from "../lib/api";
import type { ScanOverview, ScanReadingGuide, ScanStats } from "../lib/types";
import { usePolling } from "../lib/usePolling";
import { useRunMode } from "../lib/useRunMode";
import { Card, SectionHeader, Badge, EmptyState, KeyValue } from "../components/primitives";

export default function OverviewPage() {
  const mode = useRunMode();
  const { data: overview, loading: ovLoading } = usePolling<ScanOverview>(
    useCallback(() => api.getScanOverview(), []), 15_000,
  );
  const { data: guide } = usePolling<ScanReadingGuide>(
    useCallback(() => api.getScanReadingGuide(), []), 15_000,
  );
  const { data: stats } = usePolling<ScanStats>(
    useCallback(() => api.getScanStats(), []), 15_000,
  );

  if (!overview && ovLoading) {
    return <div className="p-6"><EmptyState message="正在加载总览..." /></div>;
  }
  if (!overview) {
    return <div className="p-6 space-y-5">
      <h1 className="text-2xl font-semibold text-txt">全书总览</h1>
      <EmptyState message="尚未生成总览数据。请先运行快速扫书。" />
    </div>;
  }

  const statItems = [
    { label: "总章节", value: overview.totalChapters },
    ...(overview.totalWords > 0 ? [{ label: "总字数", value: overview.totalWords.toLocaleString() }] : []),
    { label: "完成度", value: `${Math.round(overview.completeness * 100)}%` },
    { label: "模型调用", value: stats?.modelCalls || "-" },
  ];

  return (
    <div className="p-6 space-y-5">
      <h1 className="text-2xl font-semibold text-txt">全书总览</h1>

      {/* Title + completeness */}
      <Card>
        <SectionHeader title={overview.title || "未知书名"} extra={
          <Badge label={`完成度 ${Math.round(overview.completeness * 100)}%`} variant={overview.completeness >= 0.8 ? "success" : overview.completeness >= 0.5 ? "warning" : "danger"} />
        } />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
          {statItems.map(s => (
            <div key={s.label} className="text-center py-3">
              <div className="text-2xl font-bold text-txt">{s.value}</div>
              <div className="text-sm text-txt-soft mt-1">{s.label}</div>
            </div>
          ))}
        </div>
      </Card>

      {/* Main plotline */}
      <Card>
        <SectionHeader title="主线剧情" />
        <p className="text-sm text-txt leading-relaxed whitespace-pre-wrap">{overview.mainPlotline || "暂无"}</p>
      </Card>

      {/* Key stages + characters + open questions in grid */}
      <div className={`grid gap-5 ${overview.openQuestions.length > 0 ? "md:grid-cols-3" : "md:grid-cols-2"}`}>
        <Card>
          <SectionHeader title="关键阶段" />
          {overview.keyStages.length === 0 ? <EmptyState message="暂无" /> : (
            <ul className="space-y-1.5">
              {overview.keyStages.map((s, i) => (
                <li key={i} className="text-sm text-txt flex items-start gap-2">
                  <span className="text-accent font-bold">{i + 1}.</span> {s}
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <SectionHeader title="核心角色" />
          {overview.coreCharacters.length === 0 ? <EmptyState message="暂无" /> : (
            <div className="flex flex-wrap gap-2">
              {overview.coreCharacters.map((c, i) => (
                <Badge key={i} label={c} variant="accent" />
              ))}
            </div>
          )}
        </Card>
        {overview.openQuestions.length > 0 && (
          <Card>
            <SectionHeader title="未解悬念" />
            <ul className="space-y-1.5">
              {overview.openQuestions.map((q, i) => (
                <li key={i} className="text-sm text-txt-soft">• {q}</li>
              ))}
            </ul>
          </Card>
        )}
      </div>

      {/* Reading guide */}
      {guide && (
        <>
          <Card>
            <SectionHeader title="阅读指南" extra={
              <Badge label={`精华占比 ${Math.round(guide.estimatedEssentialRatio * 100)}%`} variant="info" />
            } />
            <p className="text-sm text-txt leading-relaxed mb-4">{guide.readingOrderSuggestion}</p>
            <div className={`grid gap-4 ${guide.skippableRanges.length > 0 ? "sm:grid-cols-2" : ""}`}>
              <div>
                <h3 className="text-sm font-semibold text-txt mb-2">必读章节</h3>
                {guide.mustReadChapters.length === 0 ? <span className="text-sm text-txt-soft">暂无</span> : (
                  <div className="flex flex-wrap gap-1.5">
                    {guide.mustReadChapters.map((c, i) => (
                      <Badge key={i} label={c} variant="success" />
                    ))}
                  </div>
                )}
              </div>
              {guide.skippableRanges.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-txt mb-2">可跳过范围</h3>
                  <div className="flex flex-wrap gap-1.5">
                    {guide.skippableRanges.map((r, i) => (
                      <Badge key={i} label={r} variant="default" />
                    ))}
                  </div>
                </div>
              )}
            </div>
          </Card>

          {guide.summaryByStage.length > 0 && (
            <Card>
              <SectionHeader title="分阶段摘要" />
              <div className="space-y-3">
                {guide.summaryByStage.map((s, i) => (
                  <div key={i} className="border-b border-border/50 pb-3 last:border-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-txt">{s.stage}</span>
                      <span className="text-xs text-txt-soft">{s.chapters}</span>
                    </div>
                    <p className="text-sm text-txt-soft">{s.summary}</p>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}

      {/* Stats */}
      {stats && (
        <Card>
          <SectionHeader title="运行统计" />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <KeyValue label="总段落" value={stats.totalSegments} />
            <KeyValue label="段落完成" value={stats.segmentsCompleted} />
            <KeyValue label="关键章节" value={stats.keyChaptersCount} />
            <KeyValue label="耗时" value={`${stats.elapsedSeconds}s`} />
          </div>
        </Card>
      )}
    </div>
  );
}
