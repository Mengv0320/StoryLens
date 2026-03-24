export type Book = {
  id: string;
  title: string;
  chapterCount: number;
  analyzedCount: number;
  status: "idle" | "partial" | "completed" | "failed";
  lastAnalysis?: {
    date: string;
    summary: string;
  };
  genre?: string;
};

export type Chapter = {
  id: string;
  index: number;
  title: string;
  analyzed: boolean;
  wordCount: number;
};

export type KeyEvent = {
  id: string;
  description: string;
  importance: number;
  characters: string[];
  anchorText?: string;
  anchorOffset: number;
};

export type AnalysisResult = {
  chapterId: string;
  importanceScore: number;
  importanceReason: string;
  summary: string;
  keyEvents: KeyEvent[];
};
