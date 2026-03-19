import { useState, useCallback } from "react";
import CrawlWorkflow from "../components/tasks/CrawlWorkflow";
import { api } from "../lib/api";
import type { PipelineStatusResponse } from "../lib/api";
import { usePolling } from "../lib/usePolling";
import { useSessionState } from "../lib/useSessionState";
import { Card, SectionHeader, EmptyState, Badge } from "../components/primitives";

export default function TasksPage() {
  const [pipelineInputPath, setPipelineInputPath] = useSessionState("task:inputPath", "");
  const [pipelineModel, setPipelineModel] = useSessionState("task:model", "deepseek-v3");
  const [isStarting, setIsStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const statusFetcher = useCallback(() => api.getPipelineStatus(), []);
  const { data: status, error: statusError } = usePolling<PipelineStatusResponse>(
    statusFetcher, 3000,
  );

  const handleExportComplete = useCallback((result: { textOutput: string; jsonOutput: string; title: string }) => {
    setPipelineInputPath(result.textOutput);
  }, []);

  async function handleStart() {
    if (!pipelineInputPath.trim()) { setStartError("请先完成导出以设置输入文件路径"); return; }
    setIsStarting(true);
    setStartError(null);
    try {
      await api.startPipeline({
        inputPath: pipelineInputPath,
        model: pipelineModel,
        mode: "standard_analysis",
      });
    } catch (err) {
      setStartError(err instanceof Error ? err.message : "启动失败");
    } finally {
      setIsStarting(false);
    }
  }

  const pipelineStatus = status?.status;
  const progress = status?.progress;
  const startButtonLabel = isStarting
    ? "正在启动..."
    : pipelineStatus === "completed" || pipelineStatus === "failed"
      ? "重新启动标准分析"
      : "启动标准分析";

  return (
    <div className="p-6 space-y-5">
      <h1 className="text-2xl font-semibold text-txt">任务</h1>
      <CrawlWorkflow onExportComplete={handleExportComplete} />

      <Card>
        <SectionHeader title="管线处理" extra={pipelineStatus ? <Badge label={pipelineStatus} variant={pipelineStatus === "completed" ? "success" : pipelineStatus === "failed" ? "danger" : pipelineStatus === "running" ? "accent" : "default"} /> : undefined} />
        {!pipelineInputPath ? (
          <EmptyState message="先完成上方的小说抓取与导出，再启动管线处理。" />
        ) : (
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <label className="flex flex-col gap-1.5">
                <span className="text-sm text-txt-soft">输入文件</span>
                <input value={pipelineInputPath} readOnly className="h-10 rounded-md border border-border bg-panel-soft px-3 text-sm text-txt-soft" />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-sm text-txt-soft">模型</span>
                <input value={pipelineModel} onChange={(e) => setPipelineModel(e.target.value)} className="h-10 rounded-md border border-border bg-white px-3 text-sm" />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-sm text-txt-soft">运行模式</span>
                <input value="标准分析" readOnly className="h-10 rounded-md border border-border bg-panel-soft px-3 text-sm text-txt-soft" />
              </label>
              <p className="text-xs text-txt-soft col-span-full">标准分析：逐章提取关键事件并评分，不做场景拆分和因果分析。</p>
            </div>

            {pipelineStatus !== "running" && (
              <button
                type="button"
                disabled={isStarting}
                onClick={handleStart}
                className="h-11 rounded-md bg-accent px-5 text-sm font-semibold text-white disabled:opacity-60"
              >
                {startButtonLabel}
              </button>
            )}

            {startError && (
              <div className="rounded-md border border-danger/20 bg-danger-soft/70 p-3 text-sm text-danger">{startError}</div>
            )}
            {statusError && (
              <div className="rounded-md border border-danger/20 bg-danger-soft/70 p-3 text-sm text-danger">{statusError}</div>
            )}

            {pipelineStatus === "running" && progress && (
              <div className="space-y-3">
                <div className="h-2 rounded-full bg-panel-soft overflow-hidden">
                  <div
                    className="h-full bg-accent transition-all duration-500 animate-pulse"
                    style={{ width: progress.totalChapters > 0 ? `${(progress.completedChapters / progress.totalChapters) * 100}%` : "5%" }}
                  />
                </div>
                <div className="text-sm text-txt-soft">
                  标准分析进行中 — {progress.currentStage || "准备中"}
                  {progress.totalChapters > 0 && (
                    <span className="ml-2 text-txt">({progress.completedChapters}/{progress.totalChapters} 章节)</span>
                  )}
                </div>
              </div>
            )}

            {pipelineStatus === "completed" && (
              <div className="rounded-md border border-success/30 bg-success-soft p-4 text-sm text-txt">
                <div className="font-medium text-success">管线处理完成</div>
                <div className="mt-1 text-txt-soft">前往「章节分析」查看结果。</div>
              </div>
            )}

            {pipelineStatus === "failed" && (
              <div className="rounded-md border border-danger/20 bg-danger-soft/70 p-4 text-sm text-danger">
                <div className="font-medium">管线处理失败</div>
                <div className="mt-1">{status?.error || "未知错误"}</div>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
