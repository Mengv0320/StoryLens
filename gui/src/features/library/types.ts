/** 书架本地类型 */

export type AnalysisStatus =
  | "idle"
  | "running"
  | "completed"
  | "partial_failure"
  | "failed";

export type AnalysisMode =
  | "standard_analysis"
  | "fast_scan"
  | "deep_analysis"
  | "excerpt"
  | "book";
