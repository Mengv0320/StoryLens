import type {
  ProgressSnapshot, DashboardData,
  CharacterListItem, CharacterDetail, TimelineItem,
  ExportItem, FailureItem, LogItem,
  StandardAnalysisResult,
  NarrativeResult, GroupSummary, BookSynthesis,
  BookListItem, BookChapter, BookChapterDetail, BookLatestAnalysis,
} from "./types";

const BASE = "";

export function getAuthHeaders(): Record<string, string> {
  const token =
    (typeof localStorage !== "undefined" && localStorage.getItem("api_token")) ||
    import.meta.env.VITE_API_TOKEN ||
    "";
  if (token) return { Authorization: `Bearer ${token}` };
  return {};
}

async function fetchWithTimeout(
  input: string,
  init?: RequestInit,
  timeoutMs = 30_000,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (err) {
    if (controller.signal.aborted) {
      throw new Error(`请求超时 (${timeoutMs / 1000}s): ${input}`);
    }
    throw new Error("无法连接后端服务，请确认 API 服务器已启动");
  } finally {
    clearTimeout(timer);
  }
}

export async function getJson<T>(path: string, timeoutMs?: number): Promise<T> {
  const response = await fetchWithTimeout(
    `${BASE}${path}`,
    { headers: { ...getAuthHeaders() } },
    timeoutMs,
  );
  const text = await response.text();
  let data: unknown;
  try { data = JSON.parse(text); } catch {
    throw new Error(`后端返回非 JSON 响应 (HTTP ${response.status})`);
  }
  if (!response.ok) throw new Error((data as Record<string, string>).error || `Request failed: ${response.status}`);
  return data as T;
}

export async function postJson<T>(path: string, body?: object, timeoutMs?: number): Promise<T> {
  const response = await fetchWithTimeout(
    `${BASE}${path}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: body ? JSON.stringify(body) : undefined,
    },
    timeoutMs,
  );
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
    inputPath?: string;
    url?: string;
    projectName?: string;
    outputDir?: string;
    model?: string;
    mode?: "standard_analysis";
    chapterStart?: number;
    chapterEnd?: number;
    options?: any;
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
  updateSettings: (settings: Record<string, string>) =>
    postJson<{ ok: boolean; updated: string[] }>("/api/settings", settings),

  // Standard Analysis
  getStandardAnalysis: () => getJson<StandardAnalysisResult>("/api/results/standard-analysis"),
  getChapterIndex: () => getJson<Array<{ chapterId: string; title: string }>>("/api/results/chapter-index"),
  getChapterResult: (chapterId: string) => getJson<any>(`/api/results/chapters/${encodeURIComponent(chapterId)}`),

  // Narrative Analysis
  getNarrative: () => getJson<NarrativeResult>("/api/results/narrative"),
  getNarrativeGroups: () => getJson<GroupSummary[]>("/api/results/narrative/groups"),
  getNarrativeSynthesis: () => getJson<BookSynthesis>("/api/results/narrative/synthesis"),

  // Book API
  getBooks: () => getJson<BookListItem[]>("/api/books"),
  getBook: (bookId: string) => getJson<BookListItem>(`/api/books/${encodeURIComponent(bookId)}`),
  getBookChapters: (bookId: string) => getJson<BookChapter[]>(`/api/books/${encodeURIComponent(bookId)}/chapters`),
  getBookChapter: (bookId: string, chapterId: string) =>
    getJson<BookChapterDetail>(`/api/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}`),
  getBookWiki: (bookId: string, chapterId: string) =>
    getJson<{ characters: string[]; timeline: any[] }>(`/api/books/${encodeURIComponent(bookId)}/wiki/${encodeURIComponent(chapterId)}`),
  deleteBook: async (bookId: string) => {
    const r = await fetchWithTimeout(
      `/api/books/${encodeURIComponent(bookId)}`,
      { method: "DELETE", headers: { ...getAuthHeaders() } },
    );
    if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error((d as any).error || "Delete failed"); }
    return r.json();
  },
  recleanBook: (bookId: string) =>
    postJson<{ ok: boolean; cleanedChapters: number }>(`/api/books/${encodeURIComponent(bookId)}/reclean`, {}),
  getBookLatestAnalysis: (bookId: string) =>
    getJson<BookLatestAnalysis>(`/api/books/${encodeURIComponent(bookId)}/analysis/latest`),
  getBookNarrative: (bookId: string) =>
    getJson<NarrativeResult>(`/api/books/${encodeURIComponent(bookId)}/narrative`),
  getBookCharacters: (bookId: string) =>
    getJson<CharacterListItem[]>(`/api/books/${encodeURIComponent(bookId)}/characters`),
  getBookCharacterDetail: (bookId: string, charId: string) =>
    getJson<CharacterDetail>(`/api/books/${encodeURIComponent(bookId)}/characters/${encodeURIComponent(charId)}`),
  getBookTimeline: (bookId: string) =>
    getJson<TimelineItem[]>(`/api/books/${encodeURIComponent(bookId)}/timeline`),

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
