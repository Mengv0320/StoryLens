import type {
  ProgressSnapshot, DashboardData,
  CharacterListItem, CharacterDetail, TimelineItem,
  ExportItem, FailureItem, LogItem,
  StandardAnalysisResult,
  NarrativeResult, GroupSummary, BookSynthesis,
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
    mode?: "standard_analysis";
  }) => postJson<{ runId: string; status: string }>("/api/pipeline/start", config),
  getPipelineStatus: () => getJson<PipelineStatusResponse>("/api/pipeline/status"),

  // Dashboard
  getDashboard: () => getJson<DashboardData>("/api/results/dashboard"),

  // Results
  getCharacters: () => getJson<CharacterListItem[]>("/api/results/characters"),
  getCharacterDetail: (id: string) => getJson<CharacterDetail>(`/api/results/characters/${id}`),
  getTimeline: () => getJson<TimelineItem[]>("/api/results/timeline"),
  getExports: () => getJson<ExportItem[]>("/api/results/exports"),
  getFailures: () => getJson<FailureItem[]>("/api/results/failures"),
  getLogs: () => getJson<LogItem[]>("/api/results/logs"),
  getSettings: () => getJson<Record<string, unknown>>("/api/settings"),

  // Standard Analysis
  getStandardAnalysis: () => getJson<StandardAnalysisResult>("/api/results/standard-analysis"),

  // Narrative Analysis
  getNarrative: () => getJson<NarrativeResult>("/api/results/narrative"),
  getNarrativeGroups: () => getJson<GroupSummary[]>("/api/results/narrative/groups"),
  getNarrativeSynthesis: () => getJson<BookSynthesis>("/api/results/narrative/synthesis"),

  // Crawl
  crawlInspect: (bookUrl: string) =>
    postJson<{ title: string; author?: string | null; source_url: string; chapters: Array<{ chapter_id: string; index: number; title: string; url: string }> }>(
      "/api/crawl/inspect", { book_url: bookUrl }
    ),
  crawlExport: (params: {
    book_url: string;
    chapter_start: number;
    chapter_end: number;
    context_before_chapters: number;
    output_dir: string;
  }) => postJson<{
    title: string; author?: string | null;
    selected_start: number; selected_end: number;
    context_count: number; selected_count: number;
    text_output: string; json_output: string;
    selected_titles: string[];
  }>("/api/crawl/export", params),
};
