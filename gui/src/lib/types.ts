// --- Run ---
export type RunStatus = "idle" | "running" | "completed" | "failed";

// --- Progress ---
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
export type LogItem = {
  timestamp: string;
  event: string;
  stage?: string;
  chapterId?: string;
  errorType?: string;
  error?: string;
};

// --- Failure ---
export type FailureItem = {
  type: string;
  id: string;
  title?: string;
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
export type NarrativeCharacterArc = {
  name: string;
  development: string;
};

export type NarrativeCausality = {
  cause: string;
  effect: string;
};

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

export type SubplotSummary = {
  thread: string;
  summary: string;
  status: "active" | "resolved" | string;
};

export type ForeshadowingItem = {
  setup: string;
  setupGroup: string;
  resolvedGroup: string | null;
};

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

export type NarrativeResult = {
  groupSummaries: GroupSummary[];
  bookSynthesis: BookSynthesis | null;
};
