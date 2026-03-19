// --- Run ---
export type RunStatus = "idle" | "running" | "completed" | "failed";

export type RunSummary = {
  runId: string;
  projectName: string;
  inputName: string;
  model: string;
  status: RunStatus;
  chapterCount: number;
  sceneCount: number;
  eventCount: number;
  characterCount: number;
  episodeCount: number;
  failureCount: number;
  outputDir: string;
  startedAt?: string;
  updatedAt?: string;
};

// --- Progress ---
export type ProgressSnapshot = {
  currentStage: string;
  currentChapterLabel?: string;
  completedChapters: number;
  totalChapters: number;
  cacheHits: number;
  failedCount: number;
};

// --- Episode ---
export type EpisodeListItem = {
  id: string;
  indexLabel: string;
  title: string;
  chapterRangeLabel: string;
  status: "completed" | "failed" | "warning";
};

export type EpisodeDetail = {
  id: string;
  title: string;
  chapterIds: string[];
  chapterTitles: string[];
  chapterRangeLabel: string;
  coreTheme: string;
  hook: string;
  mainConflict: string;
  keyEvents: string[];
  climax: string;
  endingHook: string;
  summary: string;
  characterIds?: string[];
  eventCount?: number;
  riskLevel?: "low" | "medium" | "high";
};

export type EpisodePlanItem = {
  id: string;
  title: string;
  chapterIds: string[];
  chapterRangeLabel: string;
  coreTheme: string;
  mainConflict: string;
  climax: string;
  endingHook: string;
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

// --- Task ---
export type TaskConfig = {
  inputPath: string;
  outputPath: string;
  model: string;
  episodeStrategy: "dynamic" | "fixed";
  targetChaptersPerEpisode: number;
  useCache: boolean;
  useCharacterMemory: boolean;
  useQualityCheck: boolean;
};

export type TaskRuntime = {
  status: RunStatus;
  currentStage: string;
  currentChapter?: string;
  completedChapters: number;
  totalChapters: number;
  cacheHits: number;
  failures: number;
  tokenUsage?: number;
  averageLatencyMs?: number;
};

// --- Log ---
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
export type FailureItem = {
  type: "chapter" | "episode";
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

// --- Dashboard ---
export type DashboardData = {
  summary: RunSummary;
  latestEpisodes: EpisodeListItem[];
  latestFailures: FailureItem[];
  progress: ProgressSnapshot;
  recentLogs: LogItem[];
};

// --- Fast Scan ---
export type ScanOverview = {
  title: string;
  totalChapters: number;
  totalWords: number;
  mainPlotline: string;
  keyStages: string[];
  coreCharacters: string[];
  openQuestions: string[];
  completeness: number;
};

export type ScanSegment = {
  segmentId: string;
  chapterIds: string[];
  chapterRange: string;
  candidateChapters: string[];
  estimatedPriority: string;
  summary: string;
  mainPlot: string;
  keyCharacters: string[];
  mustReadChapters: string[];
  skippableRanges: string[];
  openThreads: string[];
  status: "completed" | "failed" | "pending";
  error?: string;
};

export type ScanKeyChapter = {
  chapterId: string;
  importanceLevel: string;
  summary: string;
  whyItMatters: string;
  relatedCharacters: string[];
  relatedThreads: string[];
  status: "completed" | "failed";
  error?: string;
};

export type ScanReadingGuide = {
  mustReadChapters: string[];
  skippableRanges: string[];
  readingOrderSuggestion: string;
  estimatedEssentialRatio: number;
  summaryByStage: Array<{
    stage: string;
    chapters: string;
    summary: string;
  }>;
};

export type ScanChapterIndex = {
  chapterId: string;
  title: string;
  wordCount: number;
  featureTags: string[];
  importanceScore: number;
  candidateReason: string;
  isCandidate: boolean;
};

export type ScanStats = {
  totalChapters: number;
  totalSegments: number;
  segmentsCompleted: number;
  segmentsFailed: number;
  keyChaptersCount: number;
  keyChaptersCompleted: number;
  keyChaptersFailed: number;
  elapsedSeconds: number;
  modelCalls: number;
};

// --- Standard Analysis ---
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
};

export type StandardChapterResult = {
  chapterId: string;
  title: string;
  chapterSummary: string;
  keyEvents: StandardChapterKeyEvent[];
  status: string;
  importanceScore: number;
  importanceReason: string;
  eventCount: number;
  hasProtagonistEvent: boolean;
  hasTurningPoint: boolean;
  hasIdentityReveal: boolean;
};

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
  stats: {
    totalCalls: number;
    totalPromptTokens: number;
    totalCompletionTokens: number;
    totalTokens: number;
    estimatedCostUsd: number;
    cacheHits: number;
  };
};
