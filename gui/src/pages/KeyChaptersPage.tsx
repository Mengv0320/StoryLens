import { useState, useCallback } from "react";
import { api } from "../lib/api";
import type { ScanKeyChapter } from "../lib/types";
import { usePolling } from "../lib/usePolling";
import { Card, SectionHeader, Badge, EmptyState } from "../components/primitives";

export default function KeyChaptersPage() {
  const [retrying, setRetrying] = useState(false);
  const { data: chapters, refresh } = usePolling<ScanKeyChapter[]>(
    useCallback(() => api.getScanKeyChapters(), []), 10_000,
  );

  const completed = chapters?.filter(c => c.status === "completed") ?? [];
  const failed = chapters?.filter(c => c.status === "failed") ?? [];
  const failedCount = failed.length;

  const handleRetryKeyChapters = async () => {
    setRetrying(true);
    try {
      await api.retryMissing("key_chapters");
      refresh();
    } catch (e) {
      console.error("Retry failed:", e);
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div className="p-6 space-y-5">
      <h1 className="text-2xl font-semibold text-txt">关键章节</h1>

      {!chapters?.length ? (
        <Card><EmptyState message="尚未生成关键章节数据。请先运行快速扫书。" /></Card>
      ) : (
        <>
          <div className="flex gap-3 text-sm text-txt-soft items-center">
            <span>共 {chapters.length} 个关键章节</span>
            <span>·</span>
            <span className="text-success">完成 {completed.length}</span>
            {failed.length > 0 && <><span>·</span><span className="text-danger">失败 {failed.length}</span></>}
            {failedCount > 0 && (
              <button
                onClick={handleRetryKeyChapters}
                disabled={retrying}
                className="px-3 py-1.5 text-sm rounded bg-accent text-white hover:bg-accent/80 disabled:opacity-50"
              >
                {retrying ? "补跑中..." : `补跑 ${failedCount} 个失败章节`}
              </button>
            )}
          </div>

          <div className="space-y-4">
            {chapters.map(ch => (
              <Card key={ch.chapterId}>
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div>
                    <span className="font-semibold text-txt">{ch.chapterId}</span>
                    <Badge label={ch.importanceLevel || "high"} variant="danger" />
                  </div>
                  <Badge label={ch.status} variant={ch.status === "completed" ? "success" : "danger"} />
                </div>

                {ch.status === "failed" ? (
                  <p className="text-sm text-danger">{ch.error || "摘要生成失败"}</p>
                ) : (
                  <div className="space-y-3">
                    {ch.summary && (
                      <div>
                        <h3 className="text-xs font-semibold text-txt-soft mb-1">摘要</h3>
                        <p className="text-sm text-txt leading-relaxed">{ch.summary}</p>
                      </div>
                    )}
                    {ch.whyItMatters && (
                      <div>
                        <h3 className="text-xs font-semibold text-txt-soft mb-1">为什么重要</h3>
                        <p className="text-sm text-accent">{ch.whyItMatters}</p>
                      </div>
                    )}
                    <div className="flex flex-wrap gap-3">
                      {ch.relatedCharacters.length > 0 && (
                        <div>
                          <span className="text-xs text-txt-soft mr-1">角色:</span>
                          {ch.relatedCharacters.map((c, i) => <Badge key={i} label={c} variant="accent" />)}
                        </div>
                      )}
                      {ch.relatedThreads.length > 0 && (
                        <div>
                          <span className="text-xs text-txt-soft mr-1">线索:</span>
                          {ch.relatedThreads.map((t, i) => <Badge key={i} label={t} variant="info" />)}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
