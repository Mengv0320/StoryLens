import { useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { PipelineStatusResponse } from "../lib/api";
import { usePolling } from "../lib/usePolling";
import type { DashboardData, NarrativeResult } from "../lib/types";
import { Card, SectionHeader, Badge, EmptyState, KeyValue } from "../components/primitives";
import { RecentViews } from "../components/quick-actions/RecentViews";
import type { RecentViewItem } from "../components/quick-actions/RecentViews";

export default function DashboardPage() {
  const navigate = useNavigate();
  const statusFetcher = useCallback(() => api.getPipelineStatus(), []);
  const { data: status } = usePolling<PipelineStatusResponse>(statusFetcher, 5000);

  const pipelineStatus = status?.status;

  const dashInterval = pipelineStatus === "running" ? 3000 : 60000;
  const dashEnabled = !!status && pipelineStatus !== "idle";
  const dashFetcher = useCallback(() => api.getDashboard(), []);
  const { data: dash, loading: dashLoading } = usePolling<DashboardData>(dashFetcher, dashInterval, dashEnabled);

  const narrativeFetcher = useCallback(() => api.getNarrative(), []);
  const narrativeEnabled = !!status && pipelineStatus === "completed";
  const { data: narrative } = usePolling<NarrativeResult>(narrativeFetcher, 30_000, narrativeEnabled);

  const handleRecentViewNav = useCallback(
    (item: RecentViewItem) => {
      if (item.path) {
        navigate(item.path);
      } else if (item.type === "chapter") {
        navigate("/chapter-analysis");
      } else if (item.type === "character") {
        navigate("/characters");
      }
    },
    [navigate],
  );

  if (!status || (pipelineStatus === "idle" && !dash)) {
    return (
      <div className="p-6 space-y-5">
        <h1 className="text-2xl font-semibold text-txt">仪表盘</h1>
        <EmptyState message="尚未运行任何任务。前往「书架」选择书籍，或前往「任务」页面开始处理。" />
      </div>
    );
  }

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

  const { summary, progress, latestFailures } = dash;

  const stats = [
    { label: "章节数", value: summary.chapterCount },
    { label: "失败数", value: summary.failureCount },
    { label: "模型调用", value: summary.modelCalls || "-" },
  ];

  return (
    <div className="p-6 space-y-5">
      <h1 className="text-2xl font-semibold text-txt">仪表盘</h1>

      <SectionHeader
        title="标准分析总览"
        extra={<Badge label={summary.status} variant={summary.status === "completed" ? "success" : summary.status === "failed" ? "danger" : summary.status === "running" ? "accent" : "default"} />}
      />

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        {stats.map((s) => (
          <Card key={s.label} className="text-center py-4">
            <div className="text-2xl font-bold text-txt">{s.value}</div>
            <div className="text-sm text-txt-soft mt-1">{s.label}</div>
          </Card>
        ))}
      </div>

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

      {narrative && narrative.bookSynthesis && (
        <Card>
          <SectionHeader title="叙事分析" extra={<Badge label={`${narrative.groupSummaries?.length ?? 0} 组`} variant="accent" />} />
          <div className="space-y-2 text-sm">
            <KeyValue label="书名" value={narrative.bookSynthesis.title} />
            <KeyValue label="主题" value={narrative.bookSynthesis.themes?.join("、") || "-"} />
            <KeyValue label="未解悬念" value={narrative.bookSynthesis.openQuestions?.length ?? 0} />
            <Link to="/narrative" className="inline-block mt-2 text-sm text-accent hover:underline">
              查看完整叙事分析 →
            </Link>
          </div>
        </Card>
      )}

      <RecentViews maxItems={8} onNavigate={handleRecentViewNav} />
    </div>
  );
}
