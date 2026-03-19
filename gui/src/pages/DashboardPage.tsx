import { useCallback } from "react";
import { api } from "../lib/api";
import type { PipelineStatusResponse } from "../lib/api";
import { usePolling } from "../lib/usePolling";
import type { DashboardData, ScanOverview, ScanStats } from "../lib/types";
import { Card, SectionHeader, Badge, EmptyState, KeyValue } from "../components/primitives";

export default function DashboardPage() {
  const statusFetcher = useCallback(() => api.getPipelineStatus(), []);
  const { data: status } = usePolling<PipelineStatusResponse>(statusFetcher, 5000);

  const pipelineStatus = status?.status;
  const pipelineMode = status?.mode;

  // Deep analysis dashboard
  const dashEnabled = !!status && pipelineMode !== "fast_scan" && pipelineMode !== "standard_analysis";
  const dashInterval = pipelineStatus === "running" ? 3000 : 60000;
  const dashFetcher = useCallback(() => api.getDashboard(), []);
  const { data: dash, loading: dashLoading } = usePolling<DashboardData>(dashFetcher, dashInterval, dashEnabled);

  // Fast scan / standard_analysis dashboard
  const scanEnabled = pipelineStatus !== "idle" && (pipelineMode === "fast_scan" || pipelineMode === "standard_analysis");
  const overviewFetcher = useCallback(() => api.getScanOverview(), []);
  const { data: overview } = usePolling<ScanOverview>(overviewFetcher, 10_000, scanEnabled && (pipelineStatus === "completed" || pipelineStatus === "running"));
  const statsFetcher = useCallback(() => api.getScanStats(), []);
  const { data: scanStats } = usePolling<ScanStats>(statsFetcher, 5_000, scanEnabled);

  // Idle state — no run yet
  if (!status || (pipelineStatus === "idle" && !dash && !scanStats)) {
    return (
      <div className="p-6 space-y-5">
        <h1 className="text-2xl font-semibold text-txt">仪表盘</h1>
        <EmptyState message="尚未运行任何任务，请前往「任务」页面开始处理。" />
      </div>
    );
  }

  // === Fast Scan / Standard Analysis Dashboard ===
  if (pipelineMode === "fast_scan" || pipelineMode === "standard_analysis") {
    const modeLabel = pipelineMode === "standard_analysis" ? "标准分析总览" : "快速扫书总览";
    return (
      <div className="p-6 space-y-5">
        <h1 className="text-2xl font-semibold text-txt">仪表盘</h1>

        <SectionHeader
          title={modeLabel}
          extra={<Badge label={pipelineStatus || "unknown"} variant={pipelineStatus === "completed" ? "success" : pipelineStatus === "failed" ? "danger" : pipelineStatus === "running" ? "accent" : "default"} />}
        />

        {/* Stats row */}
        {scanStats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Card className="text-center py-4">
              <div className="text-2xl font-bold text-txt">{scanStats.totalChapters}</div>
              <div className="text-sm text-txt-soft mt-1">总章节数</div>
            </Card>
            <Card className="text-center py-4">
              <div className="text-2xl font-bold text-txt">{scanStats.totalSegments}</div>
              <div className="text-sm text-txt-soft mt-1">总段落数</div>
            </Card>
            <Card className="text-center py-4">
              <div className="text-2xl font-bold text-txt">{scanStats.keyChaptersCount}</div>
              <div className="text-sm text-txt-soft mt-1">关键章节数</div>
            </Card>
            <Card className="text-center py-4">
              <div className="text-2xl font-bold text-txt">
                {scanStats.totalSegments > 0 ? Math.round((scanStats.segmentsCompleted / scanStats.totalSegments) * 100) : 0}%
              </div>
              <div className="text-sm text-txt-soft mt-1">完成度</div>
            </Card>
          </div>
        )}

        {/* Overview content — only after completed */}
        {overview && (
          <>
            <Card>
              <SectionHeader title="主线摘要" />
              <div className="space-y-3">
                <KeyValue label="书名" value={overview.title} />
                {overview.totalWords > 0 && <KeyValue label="总字数" value={overview.totalWords.toLocaleString()} />}
                <KeyValue label="完整度" value={`${Math.round(overview.completeness * 100)}%`} />
                <div>
                  <div className="text-sm text-txt-soft mb-1">主线剧情</div>
                  <div className="text-sm text-txt">{overview.mainPlotline}</div>
                </div>
                {overview.keyStages.length > 0 && (
                  <div>
                    <div className="text-sm text-txt-soft mb-1">关键阶段</div>
                    <div className="flex flex-wrap gap-1.5">
                      {overview.keyStages.map((s, i) => (
                        <Badge key={i} label={s} variant="default" />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </Card>

            <div className="grid gap-5 md:grid-cols-2">
              <Card>
                <SectionHeader title="核心角色" />
                {overview.coreCharacters.length === 0 ? (
                  <EmptyState message="暂无角色数据。" />
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {overview.coreCharacters.map((c, i) => (
                      <Badge key={i} label={c} variant="accent" />
                    ))}
                  </div>
                )}
              </Card>

              <Card>
                <SectionHeader title="未解悬念" />
                {overview.openQuestions.length === 0 ? (
                  <EmptyState message="暂无未解悬念。" />
                ) : (
                  <ul className="space-y-1.5">
                    {overview.openQuestions.map((q, i) => (
                      <li key={i} className="text-sm text-txt flex gap-2">
                        <span className="text-txt-soft shrink-0">{i + 1}.</span>
                        <span>{q}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>
          </>
        )}

        {/* Running but no overview yet */}
        {!overview && pipelineStatus === "running" && (
          <EmptyState message="快速扫书进行中，完成后将显示总览..." />
        )}

        {/* Completed but overview failed to load */}
        {!overview && pipelineStatus === "completed" && (
          <EmptyState message="正在加载扫书结果..." />
        )}
      </div>
    );
  }

  // === Deep Analysis Dashboard (original) ===
  if (!dash && dashLoading) {
    return (
      <div className="p-6 space-y-5">
        <h1 className="text-2xl font-semibold text-txt">仪表盘</h1>
        <EmptyState message="正在加载数据..." />
      </div>
    );
  }

  if (!dash) {
    return (
      <div className="p-6 space-y-5">
        <h1 className="text-2xl font-semibold text-txt">仪表盘</h1>
        <EmptyState message="暂无数据。" />
      </div>
    );
  }

  const { summary, progress, latestEpisodes, latestFailures } = dash;

  const stats = [
    { label: "章节数", value: summary.chapterCount },
    { label: "分集数", value: summary.episodeCount },
    { label: "角色数", value: summary.characterCount },
    { label: "失败数", value: summary.failureCount },
  ];

  return (
    <div className="p-6 space-y-5">
      <h1 className="text-2xl font-semibold text-txt">仪表盘</h1>

      <SectionHeader
        title="运行概览"
        extra={<Badge label={summary.status} variant={summary.status === "completed" ? "success" : summary.status === "failed" ? "danger" : summary.status === "running" ? "accent" : "default"} />}
      />

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {stats.map((s) => (
          <Card key={s.label} className="text-center py-4">
            <div className="text-2xl font-bold text-txt">{s.value}</div>
            <div className="text-sm text-txt-soft mt-1">{s.label}</div>
          </Card>
        ))}
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <Card>
          <SectionHeader title="处理进度" />
          <div className="space-y-3">
            <KeyValue label="当前阶段" value={progress.currentStage || "-"} />
            <KeyValue label="章节进度" value={`${progress.completedChapters} / ${progress.totalChapters}`} />
            <div className="h-2 rounded-full bg-panel-soft overflow-hidden">
              <div
                className="h-full bg-accent transition-all duration-500"
                style={{ width: progress.totalChapters > 0 ? `${(progress.completedChapters / progress.totalChapters) * 100}%` : "0%" }}
              />
            </div>
            <KeyValue label="缓存命中" value={progress.cacheHits} />
            <KeyValue label="失败数" value={progress.failedCount} />
          </div>
        </Card>

        <Card>
          <SectionHeader title="最近分集" />
          {latestEpisodes.length === 0 ? (
            <EmptyState message="暂无分集数据。" />
          ) : (
            <div className="space-y-2">
              {latestEpisodes.slice(0, 5).map((ep) => (
                <div key={ep.id} className="flex items-center justify-between rounded-md border border-border px-3 py-2">
                  <div className="text-sm">
                    <span className="font-medium text-txt">{ep.indexLabel}</span>
                    <span className="ml-2 text-txt-soft">{ep.title}</span>
                  </div>
                  <Badge label={ep.status} variant={ep.status === "completed" ? "success" : ep.status === "failed" ? "danger" : "warning"} />
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {latestFailures.length > 0 && (
        <Card>
          <SectionHeader title="失败记录" />
          <div className="space-y-2">
            {latestFailures.map((f) => (
              <div key={f.id} className="rounded-md border border-danger/20 bg-danger-soft/30 px-3 py-2 text-sm">
                <div className="flex gap-2">
                  <Badge label={f.type} variant="danger" />
                  <span className="font-medium text-txt">{f.id}</span>
                </div>
                <div className="mt-1 text-txt-soft">{f.error}</div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
