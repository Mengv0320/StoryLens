import type {
  ProgressSnapshot, DashboardData, RunSummary,
  EpisodeListItem, EpisodeDetail, EpisodePlanItem,
  CharacterListItem, CharacterDetail, TimelineItem,
  ExportItem, FailureItem, LogItem,
  ScanOverview, ScanSegment, ScanKeyChapter, ScanReadingGuide, ScanChapterIndex, ScanStats,
  StandardAnalysisResult,
} from "./types";

const BASE = "";

async function getJson<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`);
  } catch {
    throw new Error("无法连接后端服务，请确认 API 服务器已启动");
  }
  const text = await response.text();
  let data: unknown;
  try { data = JSON.parse(text); } catch {
    throw new Error(`后端返回非 JSON 响应 (HTTP ${response.status})`);
  }
  if (!response.ok) throw new Error((data as Record<string, string>).error || `Request failed: ${response.status}`);
  return data as T;
}

export async function postJson<T>(path: string, body?: object): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("无法连接后端服务，请确认 API 服务器已启动");
  }
  const text = await response.text();
  let data: unknown;
  try { data = JSON.parse(text); } catch {
    throw new Error(`后端返回非 JSON 响应 (HTTP ${response.status})`);
  }
  if (!response.ok) throw new Error((data as Record<string, string>).error || `Request failed: ${response.status}`);
  return data as T;
}

export type PipelineStatusResponse = {
  status: string;
  runId: string;
  progress?: ProgressSnapshot;
  projectName: string;
  model: string;
  startedAt?: string;
  error?: string;
  mode?: string;
};

export const api = {
  // Pipeline
  startPipeline: (config: {
    inputPath: string;
    outputDir?: string;
    model?: string;
    chaptersPerEpisode?: number;
    splitStrategy?: string;
    skipQuality?: boolean;
    useCache?: boolean;
    mode?: "fast_scan" | "deep_analysis" | "standard_analysis";
  }) => postJson<{ runId: string; status: string }>("/api/pipeline/start", config),
  getPipelineStatus: () => getJson<PipelineStatusResponse>("/api/pipeline/status"),

  // Results
  getDashboard: () => getJson<DashboardData>("/api/results/dashboard"),
  getSummary: () => getJson<RunSummary>("/api/results/summary"),
  getEpisodes: () => getJson<EpisodeListItem[]>("/api/results/episodes"),
  getEpisodeDetail: (id: string) => getJson<EpisodeDetail>(`/api/results/episodes/${id}`),
  getEpisodePlan: () => getJson<EpisodePlanItem[]>("/api/results/episode-plan"),
  getCharacters: () => getJson<CharacterListItem[]>("/api/results/characters"),
  getCharacterDetail: (id: string) => getJson<CharacterDetail>(`/api/results/characters/${id}`),
  getTimeline: () => getJson<TimelineItem[]>("/api/results/timeline"),
  getExports: () => getJson<ExportItem[]>("/api/results/exports"),
  getFailures: () => getJson<FailureItem[]>("/api/results/failures"),
  getLogs: () => getJson<LogItem[]>("/api/results/logs"),
  getSettings: () => getJson<Record<string, unknown>>("/api/settings"),

  // Scan (fast_scan mode)
  getScanOverview: () => getJson<ScanOverview>("/api/scan/overview"),
  getScanSegments: () => getJson<ScanSegment[]>("/api/scan/segments"),
  getScanSegmentDetail: (id: string) => getJson<ScanSegment>(`/api/scan/segments/${id}`),
  getScanKeyChapters: () => getJson<ScanKeyChapter[]>("/api/scan/key-chapters"),
  getScanReadingGuide: () => getJson<ScanReadingGuide>("/api/scan/reading-guide"),
  getScanChapterIndex: () => getJson<ScanChapterIndex[]>("/api/scan/chapter-index"),
  getScanStats: () => getJson<ScanStats>("/api/scan/stats"),
  retryMissing: (type: "segments" | "key_chapters") => postJson<{ status: string; retried: number }>("/api/pipeline/retry", { type }),

  // Standard Analysis
  getStandardAnalysis: () => getJson<StandardAnalysisResult>("/api/results/standard-analysis"),
};
