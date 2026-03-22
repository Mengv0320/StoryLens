import type { AnalysisStatus, AnalysisMode } from "./types";

type BadgeVariant = "default" | "success" | "warning" | "danger" | "info" | "accent";

const statusMap: Record<AnalysisStatus, { label: string; variant: BadgeVariant }> = {
  idle:            { label: "未分析",   variant: "default" },
  running:         { label: "分析中",   variant: "accent" },
  completed:       { label: "已完成",   variant: "success" },
  partial_failure: { label: "部分失败", variant: "warning" },
  failed:          { label: "失败",     variant: "danger" },
};

const modeLabels: Record<AnalysisMode, string> = {
  standard_analysis: "标准分析",
  fast_scan:         "快速扫描",
  deep_analysis:     "深度分析",
  excerpt:           "片段模式",
  book:              "全书模式",
};

export function getStatusBadge(status: string): { label: string; variant: BadgeVariant } {
  if (status === "partial") return statusMap["partial_failure"];
  return statusMap[status as AnalysisStatus] ?? { label: status, variant: "default" };
}

export function getModeLabel(mode: string | null): string {
  if (!mode) return "—";
  return modeLabels[mode as AnalysisMode] ?? mode;
}

export function formatTime(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
