import { api } from "../../lib/api";
import { usePolling } from "../../lib/usePolling";
import { Badge } from "../primitives";

export default function TopBar() {
  const { data: status } = usePolling(() => api.getPipelineStatus(), 5_000);
  const runStatus = status?.status ?? "idle";
  const variantMap: Record<string, "default" | "success" | "warning" | "danger" | "accent"> = {
    idle: "default", running: "accent", completed: "success", failed: "danger",
  };

  return (
    <header className="h-16 flex-shrink-0 border-b border-border bg-panel flex items-center justify-between px-6">
      <span className="text-lg font-semibold text-txt">History Pipeline</span>
      <span className="text-sm text-txt-soft">{status?.projectName || "—"}</span>
      <div className="flex items-center gap-3">
        {(status as any)?.mode && (
          <span className="text-xs px-2 py-0.5 rounded bg-panel-muted text-txt-soft">
            {(status as any).mode === "standard_analysis" ? "标准分析" : (status as any).mode}
          </span>
        )}
        <Badge label={runStatus} variant={variantMap[runStatus] ?? "default"} />
        <span className="text-xs text-txt-soft">{status?.model || "—"}</span>
      </div>
    </header>
  );
}
