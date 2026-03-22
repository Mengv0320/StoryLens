import { useState, useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import CrawlWorkflow from "../components/tasks/CrawlWorkflow";
import { api } from "../lib/api";
import type { PipelineStatusResponse } from "../lib/api";
import type { BookListItem } from "../lib/types";
import { usePolling } from "../lib/usePolling";
import { useSessionState } from "../lib/useSessionState";
import { Card, SectionHeader, EmptyState, Badge } from "../components/primitives";
import { BookOpen, Search, Library, X, CheckCircle } from "lucide-react";

type BookSource = "library" | "crawl";
type SelectedBook = { title: string; author?: string | null; sourceUrl: string; bookId?: string };

export default function TasksPage() {
  const [pipelineInputPath, setPipelineInputPath] = useSessionState("task:inputPath", "");
  const [pipelineModel, setPipelineModel] = useSessionState("task:model", "deepseek-v3");
  const [isStarting, setIsStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [selectedBook, setSelectedBook] = useSessionState<SelectedBook | null>("task:selectedBook", null);
  const [bookSource, setBookSource] = useSessionState<BookSource>("task:bookSource", "library");
  const [libraryFilter, setLibraryFilter] = useState("");
  const [refinementIntensity, setRefinementIntensity] = useSessionState<"minimal" | "standard" | "detailed">("task:refinementIntensity", "standard");

  // --- Library book list ---
  const booksFetcher = useCallback(() => api.getBooks(), []);
  const { data: libraryBooks, error: booksError } = usePolling<BookListItem[]>(booksFetcher, 15_000);

  const filteredBooks = useMemo(() => {
    if (!libraryBooks) return [];
    if (!libraryFilter.trim()) return libraryBooks;
    const q = libraryFilter.trim().toLowerCase();
    return libraryBooks.filter(
      (b) => b.title.toLowerCase().includes(q) || b.author?.toLowerCase().includes(q),
    );
  }, [libraryBooks, libraryFilter]);

  // --- Pipeline status ---
  const statusFetcher = useCallback(() => api.getPipelineStatus(), []);
  const { data: status, error: statusError } = usePolling<PipelineStatusResponse>(statusFetcher, 3000);

  const handleExportComplete = useCallback((result: { textOutput: string; jsonOutput: string; title: string }) => {
    setPipelineInputPath(result.textOutput);
  }, []);

  const handleBookChange = useCallback((book: { title: string; author?: string | null; sourceUrl: string } | null) => {
    if (book) {
      setSelectedBook(book);
    } else {
      setSelectedBook(null);
    }
    setPipelineInputPath("");
  }, []);

  function handleSelectLibraryBook(book: BookListItem) {
    setSelectedBook({ title: book.title, author: book.author, sourceUrl: book.sourceUrl, bookId: book.bookId });
    setPipelineInputPath("");
  }

  function handleClearBook() {
    setSelectedBook(null);
    setPipelineInputPath("");
  }

  async function handleStart() {
    if (!pipelineInputPath.trim() && !selectedBook?.sourceUrl) { 
        setStartError("请先设置输入文件路径或选择一本书籍"); 
        return; 
    }
    setIsStarting(true);
    setStartError(null);
    try {
      await api.startPipeline({
        inputPath: pipelineInputPath || undefined,
        url: !pipelineInputPath ? selectedBook?.sourceUrl : undefined,
        model: pipelineModel,
        mode: "standard_analysis",
        options: { refinement_intensity: refinementIntensity },
      });
    } catch (err) {
      setStartError(err instanceof Error ? err.message : "启动失败");
    } finally {
      setIsStarting(false);
    }
  }

  const pipelineStatus = status?.status;
  const progress = status?.progress;
  const startButtonLabel = isStarting
    ? "正在启动..."
    : pipelineStatus === "completed" || pipelineStatus === "failed"
      ? "重新启动标准分析"
      : "启动标准分析";

  return (
    <div className="p-6 space-y-5">
      <h1 className="text-2xl font-semibold text-txt">任务中心</h1>

      {/* ── 已选中书的提示 ── */}
      {selectedBook ? (
        <div className="flex items-center gap-4 rounded-xl border border-accent/20 bg-accent-soft/50 px-5 py-4 transition-all">
          <BookOpen size={16} className="text-accent shrink-0" />
          <div className="flex-1 min-w-0">
            <span className="text-sm text-txt-soft">当前目标：</span>
            <span className="ml-1 text-sm font-medium text-accent truncate">{selectedBook.title}</span>
            {selectedBook.author && (
              <span className="ml-2 text-xs text-txt-faint">作者：{selectedBook.author}</span>
            )}
          </div>
          <button
            type="button"
            onClick={handleClearBook}
            className="flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-xs text-txt-soft hover:bg-panel-soft transition-colors"
          >
            <X size={12} /> 更换
          </button>
        </div>
      ) : (
        /* ── 书源选择器（未选中书时显示） ── */
        <Card>
          <SectionHeader title="选择书籍" />
          {/* Tab 切换 */}
          <div className="flex gap-1 rounded-lg bg-panel-soft p-1 mb-4">
            <button
              type="button"
              onClick={() => setBookSource("library")}
              className={[
                "flex-1 flex items-center justify-center gap-2 rounded-md px-4 py-2.5 text-sm font-medium transition-all",
                bookSource === "library"
                  ? "bg-white text-accent shadow-sm"
                  : "text-txt-soft hover:text-txt",
              ].join(" ")}
            >
              <Library size={15} /> 从书架选择
            </button>
            <button
              type="button"
              onClick={() => setBookSource("crawl")}
              className={[
                "flex-1 flex items-center justify-center gap-2 rounded-md px-4 py-2.5 text-sm font-medium transition-all",
                bookSource === "crawl"
                  ? "bg-white text-accent shadow-sm"
                  : "text-txt-soft hover:text-txt",
              ].join(" ")}
            >
              <Search size={15} /> 抓取新书
            </button>
          </div>

          {/* 书架列表 */}
          {bookSource === "library" && (
            <div className="space-y-3">
              <input
                value={libraryFilter}
                onChange={(e) => setLibraryFilter(e.target.value)}
                className="h-10 w-full rounded-md border border-border bg-white px-3 text-sm outline-none focus:border-accent"
                placeholder="搜索书名或作者..."
              />
              {booksError && !libraryBooks && (
                <div className="text-sm text-txt-soft">无法加载书架，请确认后端已启动。</div>
              )}
              {libraryBooks && filteredBooks.length === 0 && (
                <EmptyState message={libraryFilter ? "没有匹配的书籍。" : "书架为空，请先抓取新书。"} />
              )}
              <div className="grid gap-2 max-h-[400px] overflow-y-auto pr-1">
                {filteredBooks.map((book) => (
                  <button
                    key={book.bookId}
                    type="button"
                    onClick={() => handleSelectLibraryBook(book)}
                    className="flex items-center gap-3 rounded-lg border border-border bg-white px-4 py-3 text-left hover:border-accent hover:bg-accent-soft/30 transition-all group"
                  >
                    <BookOpen size={16} className="text-txt-soft group-hover:text-accent shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-txt truncate">{book.title}</div>
                      <div className="text-xs text-txt-faint">
                        {book.author || "未知作者"} · {book.chapterCount} 章
                        {book.latestStatus && (
                          <span className="ml-2">
                            · <Badge label={book.latestStatus} variant={book.latestStatus === "completed" ? "success" : book.latestStatus === "failed" ? "danger" : "default"} />
                          </span>
                        )}
                      </div>
                    </div>
                    <CheckCircle size={14} className="text-transparent group-hover:text-accent shrink-0 transition-colors" />
                  </button>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}

      {/* ── 抓取新书流程（crawl tab 或已选中书后继续操作） ── */}
      {(bookSource === "crawl" && !selectedBook) || selectedBook ? (
        <CrawlWorkflow onExportComplete={handleExportComplete} onBookChange={handleBookChange} />
      ) : null}

      {/* ── 管线处理 ── */}
      <Card>
        <SectionHeader title="管线处理" extra={pipelineStatus ? <Badge label={pipelineStatus} variant={pipelineStatus === "completed" ? "success" : pipelineStatus === "failed" ? "danger" : pipelineStatus === "running" ? "accent" : "default"} /> : undefined} />
        {!pipelineInputPath && !selectedBook ? (
          <EmptyState message="先完成小说的抓取或选择，再启动管线处理。" />
        ) : (
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <label className="flex flex-col gap-1.5">
                <span className="text-sm text-txt-soft">数据源</span>
                <input value={pipelineInputPath ? "本地文件: " + pipelineInputPath : "在线抓取: " + selectedBook?.title} readOnly title={pipelineInputPath || selectedBook?.sourceUrl || ""} className="h-10 rounded-md border border-border bg-panel-soft px-3 text-sm text-txt-soft truncate" />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-sm text-txt-soft">模型</span>
                <input value={pipelineModel} onChange={(e) => setPipelineModel(e.target.value)} className="h-10 rounded-md border border-border bg-white px-3 text-sm" />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-sm text-txt-soft">运行模式</span>
                <input value="标准分析" readOnly className="h-10 rounded-md border border-border bg-panel-soft px-3 text-sm text-txt-soft" />
              </label>
              <p className="text-xs text-txt-soft col-span-full">标准分析：逐章提取关键事件并评分，不做场景拆分和因果分析。</p>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-txt">精炼强度 (去水等级)</label>
              <div className="flex items-center gap-2">
                {(["minimal", "standard", "detailed"] as const).map((level) => (
                  <button
                    key={level}
                    type="button"
                    onClick={() => setRefinementIntensity(level)}
                    className={`flex-1 py-1.5 text-xs font-medium rounded-md border transition-colors ${
                      refinementIntensity === level
                        ? "bg-accent text-accent-fg border-accent shadow-sm"
                        : "bg-panel border-border text-txt-soft hover:border-accent/50"
                    }`}
                  >
                    {level === "minimal" && "骨干提取 (极简)"}
                    {level === "standard" && "标准精炼 (推荐)"}
                    {level === "detailed" && "深度保留 (详尽)"}
                  </button>
                ))}
              </div>
              <p className="text-xs text-txt-faint">
                {refinementIntensity === "minimal" && "仅保留核心主线事件，去除所有次要描写与支线。"}
                {refinementIntensity === "standard" && "平衡剧情主次，适合二次创作或快速补书。"}
                {refinementIntensity === "detailed" && "保留较多环境描写与人物心境，适合沉浸式听书。"}
              </p>
            </div>

            {pipelineStatus !== "running" && (
              <button
                type="button"
                disabled={isStarting}
                onClick={handleStart}
                className="h-11 rounded-md bg-accent px-6 text-sm font-semibold text-white shadow-sm hover:bg-accent-hover hover:-translate-y-0.5 disabled:opacity-60 disabled:hover:translate-y-0 transition-all duration-200"
              >
                {startButtonLabel}
              </button>
            )}

            {startError && (
              <div className="rounded-md border border-danger/20 bg-danger-soft/70 p-3 text-sm text-danger">{startError}</div>
            )}
            {statusError && (
              <div className="rounded-md border border-danger/20 bg-danger-soft/70 p-3 text-sm text-danger">{statusError}</div>
            )}

            {pipelineStatus === "running" && progress && (
              <div className="space-y-3">
                <div className="h-2 rounded-full bg-panel-soft overflow-hidden">
                  <div
                    className="h-full bg-accent transition-all duration-500 animate-pulse"
                    style={{ width: progress.totalChapters > 0 ? `${(progress.completedChapters / progress.totalChapters) * 100}%` : "5%" }}
                  />
                </div>
                <div className="text-sm text-txt-soft">
                  标准分析进行中 — {progress.currentStage || "准备中"}
                  {progress.totalChapters > 0 && (
                    <span className="ml-2 text-txt">({progress.completedChapters}/{progress.totalChapters} 章节)</span>
                  )}
                </div>
              </div>
            )}

            {pipelineStatus === "completed" && (
              <div className="rounded-md border border-success/30 bg-success-soft p-4 text-sm text-txt">
                <div className="font-medium text-success">管线处理完成</div>
                <div className="mt-1 text-txt-soft">
                  前往{" "}
                  <Link to="/chapter-analysis" className="text-accent hover:underline">章节分析</Link>
                  {" "}查看结果，或回到{" "}
                  <Link to="/library" className="text-accent hover:underline">书架</Link>
                  {" "}查看书籍详情。
                </div>
              </div>
            )}

            {pipelineStatus === "failed" && (
              <div className="rounded-md border border-danger/20 bg-danger-soft/70 p-4 text-sm text-danger">
                <div className="font-medium">管线处理失败</div>
                <div className="mt-1">{status?.error || "未知错误"}</div>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
