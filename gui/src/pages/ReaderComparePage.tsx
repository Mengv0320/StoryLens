import { useState, useRef, useMemo, useCallback, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import ChapterSidebar from "../components/reader/ChapterSidebar";
import ContentPanel from "../components/reader/ContentPanel";
import AnalysisPanel from "../components/reader/AnalysisPanel";
import WikiPanel from "../components/reader/WikiPanel";
import { usePolling } from "../lib/usePolling";
import { api } from "../lib/api";
import type { BookChapter, BookChapterDetail } from "../lib/types";
import type { Chapter, AnalysisResult } from "../features/reader/types";

export default function ReaderComparePage() {
  const { bookId } = useParams<{ bookId: string }>();
  const [selectedId, setSelectedId] = useState<string>("");
  const [activeEventId, setActiveEventId] = useState<string | null>(null);
  const [rightPanelTab, setRightPanelTab] = useState<"analysis" | "wiki">("analysis");
  const contentRef = useRef<HTMLDivElement>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [wikiError, setWikiError] = useState<string | null>(null);

  const chaptersFetcher = useCallback(
    () => (bookId ? api.getBookChapters(bookId) : Promise.reject("no id")),
    [bookId],
  );
  const { data: apiChapters } = usePolling<BookChapter[]>(chaptersFetcher, 30_000, !!bookId);

  const chapters: Chapter[] = useMemo(() => {
    if (apiChapters && apiChapters.length > 0) {
      return apiChapters.map((c, i) => ({
        id: c.chapterId,
        index: i + 1,
        title: c.title,
        analyzed: c.status === "ok" || c.importanceScore > 0,
        wordCount: 0,
      }));
    }
    return [];
  }, [apiChapters]);

  useEffect(() => {
    if (chapters.length > 0 && !selectedId) {
      // Restore reading progress from localStorage
      const saved = localStorage.getItem(`reader:${bookId}:lastChapter`);
      if (saved && chapters.some((c) => c.id === saved)) {
        setSelectedId(saved);
      } else {
        setSelectedId(chapters[0].id);
      }
    }
  }, [chapters, selectedId, bookId]);

  // Fetch chapter detail directly — swaps atomically on selectedId change, no flash
  const [apiDetail, setApiDetail] = useState<BookChapterDetail | null>(null);
  useEffect(() => {
    if (!bookId || !selectedId) return;
    let cancelled = false;
    setDetailError(null);
    api.getBookChapter(bookId, selectedId).then((data) => {
      if (!cancelled) setApiDetail(data);
    }).catch((err) => {
      console.error('Failed to load chapter detail:', err);
      if (!cancelled) setDetailError(err.message || 'Failed to load chapter detail');
    });
    return () => { cancelled = true; };
  }, [bookId, selectedId]);

  const [wikiData, setWikiData] = useState<{characters: string[], timeline: any[]}>({ characters: [], timeline: [] });
  useEffect(() => {
    if (!bookId || !selectedId || rightPanelTab !== "wiki") return;
    let cancelled = false;
    setWikiError(null);
    api.getBookWiki(bookId, selectedId).then((data) => {
      if (!cancelled) setWikiData(data);
    }).catch((err) => {
      console.error('Failed to load wiki data:', err);
      if (!cancelled) setWikiError(err.message || 'Failed to load wiki data');
    });
    return () => { cancelled = true; };
  }, [bookId, selectedId, rightPanelTab]);

  const content = apiDetail?.rawText ?? "";
  const chapter = chapters.find((c) => c.id === selectedId);

  const analysis: AnalysisResult | null = useMemo(() => {
    if (apiDetail && apiDetail.keyEvents) {
      return {
        chapterId: apiDetail.chapterId,
        importanceScore: apiDetail.importanceScore,
        importanceReason: apiDetail.importanceReason,
        summary: apiDetail.chapterSummary,
        keyEvents: apiDetail.keyEvents.map((ev) => ({
          id: ev.eventId,
          description: ev.description,
          importance: ev.importance,
          characters: ev.characters,
          anchorOffset: ev.anchorOffset ?? 0,
        })),
      };
    }
    return null;
  }, [apiDetail, selectedId]);

  const highlights = useMemo(() => {
    if (!analysis) return [];
    return analysis.keyEvents.map((ev) => ({
      offset: ev.anchorOffset,
      length: 50,
      eventId: ev.id,
    }));
  }, [analysis]);

  const handleChapterSelect = (id: string) => {
    setSelectedId(id);
    setActiveEventId(null);
    if (bookId) localStorage.setItem(`reader:${bookId}:lastChapter`, id);
  };

  const handleEventClick = (eventId: string) => {
    setActiveEventId((prev) => (prev === eventId ? null : eventId));
  };

  // Keyboard navigation: ArrowLeft/ArrowRight to switch chapters
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!chapters.length) return;
      const idx = chapters.findIndex((c) => c.id === selectedId);
      if (e.key === "ArrowLeft" && idx > 0) {
        handleChapterSelect(chapters[idx - 1].id);
      } else if (e.key === "ArrowRight" && idx < chapters.length - 1) {
        handleChapterSelect(chapters[idx + 1].id);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [chapters, selectedId]);

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border bg-panel shrink-0">
        <Link to={bookId ? `/book/${bookId}` : "/library"} className="text-txt-soft hover:text-accent transition-colors">
          <ArrowLeft size={18} />
        </Link>
        <span className="text-sm font-medium text-txt">原文对照阅读</span>
      </div>
      <div className="flex flex-1 min-h-0 overflow-hidden">
        <ChapterSidebar
          chapters={chapters}
          selectedId={selectedId}
          onSelect={handleChapterSelect}
        />
        <div className="flex-1 flex flex-col min-w-0">
          {detailError && (
            <div className="px-4 py-2 bg-danger-soft/30 text-danger text-xs border-b border-danger/20">
              加载章节失败：{detailError}
            </div>
          )}
          <ContentPanel
            title={chapter?.title ?? ""}
            content={content}
            highlights={highlights}
            activeEventId={activeEventId}
            contentRef={contentRef}
          />
        </div>
        <div className="w-80 shrink-0 flex flex-col border-l border-border bg-panel">
          <div className="flex items-center gap-1 p-2 border-b border-border bg-panel-muted/50">
            <button
              onClick={() => setRightPanelTab("analysis")}
              className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-colors ${rightPanelTab === "analysis" ? "bg-accent text-accent-fg shadow-sm" : "text-txt-soft hover:bg-black/5"}`}
            >
              本章解析
            </button>
            <button
              onClick={() => setRightPanelTab("wiki")}
              className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-colors ${rightPanelTab === "wiki" ? "bg-accent text-accent-fg shadow-sm" : "text-txt-soft hover:bg-black/5"}`}
            >
              前情 Wiki
            </button>
          </div>
          <div className="flex-1 overflow-hidden">
            {rightPanelTab === "analysis" ? (
              <AnalysisPanel
                analysis={analysis}
                activeEventId={activeEventId}
                onEventClick={handleEventClick}
              />
            ) : wikiError ? (
              <div className="p-4 text-xs text-danger">{wikiError}</div>
            ) : (
              <WikiPanel characters={wikiData.characters} timeline={wikiData.timeline} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
