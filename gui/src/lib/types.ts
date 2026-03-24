// --- Run ---
export type RunStatus = "idle" | "running" | "completed" | "failed";

// --- Progress ---
// Source: api_server.py RunManager._read_progress()
export type ProgressSnapshot = {
  currentStage: string;
  currentChapterLabel?: string;
  completedChapters: number;
  totalChapters: number;
  cacheHits: number;
  failedCount: number;
};

// --- Character ---
export type CharacterListItem = {
  id: string;
  name: string;
  faction?: string;
  aliasCount: number;
  eventCount: number;
  latestChapterLabel?: string;
};

export type CharacterRelationship = {
  targetId?: string;
  targetName: string;
  relationType: "hostile" | "suspicious" | "allied" | "subordinate" | "mentor" | "family" | "romantic" | "unknown";
  note?: string;
};

export type CharacterDetail = {
  id: string;
  name: string;
  aliases: string[];
  identity?: string;
  faction?: string;
  currentGoal?: string;
  description?: string;
  recentEvents: string[];
  relationships: CharacterRelationship[];
};

// --- Timeline ---
export type TimelineItem = {
  id: string;
  title: string;
  chapterRangeLabel: string;
  eventType: string;
  eventGroup: string;
  importance: number;
  characters: string[];
  summary: string;
};

// --- Log ---
// Source: api_server.py _read_logs() — includes episodeId from run.jsonl
export type LogItem = {
  timestamp: string;
  event: string;
  stage?: string;
  chapterId?: string;
  episodeId?: string;
  errorType?: string;
  error?: string;
};

// --- Failure ---
// Source: api_server.py _read_failures() — includes chapterIds for episode failures
export type FailureItem = {
  type: string;
  id: string;
  title?: string;
  chapterIds?: string[];
  errorType: string;
  error: string;
};

// --- Export ---
export type ExportItem = {
  id: string;
  label: string;
  format: "json" | "jsonl";
  path: string;
  exists: boolean;
  description: string;
};

// --- Standard Analysis ---
// Source: models.py ChapterKeyEvent (camelized by api_server)
export type StandardChapterKeyEvent = {
  eventId: string;
  eventType: string;
  title: string;
  description: string;
  characters: string[];
  cause: string;
  consequence: string;
  involvesProtagonist: boolean;
  involvesIdentityReveal: boolean;
  involvesFactionChange: boolean;
  involvesDeathOrBreakthrough: boolean;
  involvesRelationshipChange: boolean;
  importance: number;
  anchorText?: string;
  anchorOffset?: number;
};

// Source: standard_analysis.py _process_chapter() + score_chapter() (camelized)
export type StandardChapterResult = {
  chapterId: string;
  title: string;
  rawText?: string;
  chapterSummary: string;
  keyEvents: StandardChapterKeyEvent[];
  status: string;
  importanceScore: number;
  importanceReason: string;
};

// Source: stats.py PipelineStats.to_dict() (camelized)
export type PipelineStatsDict = {
  calls: Array<{
    stage: string;
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
    durationSeconds: number;
    model: string;
    chapterId: string;
    episodeId: string;
  }>;
  byStage: Array<{
    stage: string;
    callCount: number;
    totalPromptTokens: number;
    totalCompletionTokens: number;
    totalTokens: number;
    totalDurationSeconds: number;
  }>;
  byChapter: Record<string, {
    stage: string;
    callCount: number;
    totalPromptTokens: number;
    totalCompletionTokens: number;
    totalTokens: number;
    totalDurationSeconds: number;
  }>;
  byEpisode: Record<string, {
    stage: string;
    callCount: number;
    totalPromptTokens: number;
    totalCompletionTokens: number;
    totalTokens: number;
    totalDurationSeconds: number;
  }>;
  costEstimate: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
    promptCostUsd: number;
    completionCostUsd: number;
    totalCostUsd: number;
  };
};

// Source: standard_analysis.py run_standard_analysis() output (camelized)
export type StandardAnalysisResult = {
  mode: string;
  genre: {
    primaryGenre: string;
    subgenre: string;
    secondaryGenres: string[];
    confidence: number;
    signals: string[];
  };
  chapters: StandardChapterResult[];
  failures: Array<{
    chapterId: string;
    title: string;
    error: string;
  }>;
  stats: PipelineStatsDict;
};

// --- Dashboard (standard_analysis) ---
export type DashboardSummary = {
  status: string;
  chapterCount: number;
  failureCount: number;
  modelCalls: number;
};

export type DashboardData = {
  summary: DashboardSummary;
  progress: ProgressSnapshot;
  latestFailures: FailureItem[];
};

// --- Narrative Analysis ---
// Source: narrative_types.py GroupSummary.character_arcs items (camelized)
export type NarrativeCharacterArc = {
  name: string;
  development: string;
};

export type NarrativeCausality = {
  cause: string;
  effect: string;
};

// Source: narrative_types.py GroupSummary (camelized via NarrativeResult.to_dict -> asdict)
export type GroupSummary = {
  groupId: string;
  chapterRange: string;
  chapterIds: string[];
  plotProgress: string;
  newForeshadowing: string[];
  resolvedForeshadowing: string[];
  openQuestions: string[];
  subplotThreads: string[];
  characterArcs: NarrativeCharacterArc[];
  keyCausality: NarrativeCausality[];
  tensionLevel: number;
};

// Source: narrative_types.py BookSynthesis.subplot_summary items (camelized)
export type SubplotSummary = {
  thread: string;
  summary: string;
  status: "active" | "resolved" | string;
};

// Source: narrative_types.py BookSynthesis.foreshadowing_tracker items (camelized)
export type ForeshadowingItem = {
  setup: string;
  setupGroup: string;
  resolvedGroup: string | null;
};

// Source: narrative_types.py BookSynthesis.character_arcs items (camelized)
export type BookCharacterArc = {
  name: string;
  arcSummary: string;
  keyMoments: string[];
};

export type TensionPoint = {
  groupId: string;
  level: number;
  reason: string;
};

// Source: narrative_types.py BookSynthesis (camelized)
export type BookSynthesis = {
  title: string;
  mainPlotline: string;
  subplotSummary: SubplotSummary[];
  foreshadowingTracker: ForeshadowingItem[];
  characterArcs: BookCharacterArc[];
  tensionCurve: TensionPoint[];
  themes: string[];
  openQuestions: string[];
  qualityNotes: string[];
};

// Source: narrative_types.py NarrativeResult.to_dict() (camelized)
export type NarrativeResult = {
  groupSummaries: GroupSummary[];
  bookSynthesis: BookSynthesis | null;
};

// --- Segments / Reading Guide ---
export type Segment = {
  segmentId: string;
  chapterRange: string;
  summary: string;
  mainPlot: string;
  keyCharacters: string[];
  mustReadChapters: string[];
  estimatedPriority: string;
};

export type ReadingGuide = {
  mustReadChapters: string[];
  skippableRanges: string[];
  readingOrderSuggestion: string;
  estimatedEssentialRatio: number;
  summaryByStage: string[];
};

// --- Book API ---
// Source: book_types.py BookMeta.to_dict()
export type BookListItem = {
  bookId: string;
  title: string;
  author: string;
  sourceUrl: string;
  chapterCount: number;
  latestRunId: string;
  latestMode: string;
  latestStatus: string;
  updatedAt?: string;
  runs: Array<{ runId: string; hasStandard: boolean; hasBookResult: boolean; hasIndex: boolean }>;
};

// Source: book_index.py BookIndex.get_chapters()
export type BookChapter = {
  chapterId: string;
  title: string;
  status: string;
  importanceScore: number;
  importanceReason: string;
  eventCount: number;
};

// Source: book_index.py BookIndex.get_chapter_detail() — returns _camelize(ch) from standard_output
export type BookChapterDetail = {
  chapterId: string;
  title: string;
  rawText?: string;
  chapterSummary: string;
  importanceScore: number;
  importanceReason: string;
  keyEvents: StandardChapterKeyEvent[];
  status: string;
};

// Source: book_index.py BookIndex.get_latest_analysis() — _camelize(standard_output) + enriched
export type BookLatestAnalysis = {
  bookId?: string;
  title?: string;
  author?: string;
  mode: string;
  genre: {
    primaryGenre: string;
    subgenre: string;
    secondaryGenres: string[];
    confidence: number;
    signals: string[];
  };
  chapters: StandardChapterResult[];
  failures: Array<{
    chapterId: string;
    title: string;
    error: string;
  }>;
  stats: PipelineStatsDict;
};
