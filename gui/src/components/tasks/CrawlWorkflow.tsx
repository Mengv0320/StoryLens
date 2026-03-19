import { startTransition, useDeferredValue, useState } from "react";
import type { FormEvent } from "react";
import { Card, EmptyState, SectionHeader, Badge } from "../primitives";
import { postJson } from "../../lib/api";
import { useSessionState } from "../../lib/useSessionState";

type ChapterPreview = {
  chapter_id: string;
  index: number;
  title: string;
  url: string;
};

type BookPreview = {
  title: string;
  author?: string | null;
  source_url: string;
  chapters: ChapterPreview[];
};

type ExportResult = {
  title: string;
  author?: string | null;
  selected_start: number;
  selected_end: number;
  context_count: number;
  selected_count: number;
  text_output: string;
  json_output: string;
  selected_titles: string[];
};

type Props = {
  onExportComplete?: (result: { textOutput: string; jsonOutput: string; title: string }) => void;
};

export default function CrawlWorkflow(props: Props) {
  const [bookUrl, setBookUrl] = useSessionState("crawl:bookUrl", "https://www.bqg128.cc/book/17322/");
  const [contextBefore, setContextBefore] = useSessionState("crawl:contextBefore", 3);
  const [outputDir, setOutputDir] = useSessionState("crawl:outputDir", "data/exports");
  const [inspectLoading, setInspectLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [book, setBook] = useSessionState<BookPreview | null>("crawl:book", null);
  const [chapterStart, setChapterStart] = useSessionState("crawl:chapterStart", 1);
  const [chapterEnd, setChapterEnd] = useSessionState("crawl:chapterEnd", 1);
  const [chapterFilter, setChapterFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [exportResult, setExportResult] = useSessionState<ExportResult | null>("crawl:exportResult", null);

  const deferredFilter = useDeferredValue(chapterFilter.trim());
  const filteredChapters = !book
    ? []
    : !deferredFilter
      ? book.chapters
      : book.chapters.filter((chapter) => chapter.title.includes(deferredFilter));

  async function handleInspect(event: FormEvent) {
    event.preventDefault();
    setInspectLoading(true);
    setError(null);
    setExportResult(null);
    try {
      const preview = await postJson<BookPreview>("/api/crawl/inspect", { book_url: bookUrl });
      startTransition(() => {
        setBook(preview);
        setChapterStart(1);
        setChapterEnd(Math.min(5, preview.chapters.length || 1));
      });
    } catch (err) {
      setBook(null);
      setError(err instanceof Error ? err.message : "检查书链接失败");
    } finally {
      setInspectLoading(false);
    }
  }

  async function handleExport() {
    setExportLoading(true);
    setError(null);
    setExportResult(null);
    try {
      const result = await postJson<ExportResult>("/api/crawl/export", {
        book_url: bookUrl,
        chapter_start: chapterStart,
        chapter_end: chapterEnd,
        context_before_chapters: contextBefore,
        output_dir: outputDir,
      });
      startTransition(() => {
        setExportResult(result);
      });
      props.onExportComplete?.({ textOutput: result.text_output, jsonOutput: result.json_output, title: result.title });
    } catch (err) {
      setError(err instanceof Error ? err.message : "导出失败");
    } finally {
      setExportLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <Card className="overflow-hidden bg-gradient-to-br from-panel via-panel to-accent-soft/40">
        <SectionHeader
          title="小说抓取与选章"
          extra={<Badge label="本地 API" variant="accent" />}
        />
        <form className="space-y-4" onSubmit={handleInspect}>
          <div className="grid gap-4 md:grid-cols-[1.6fr_0.8fr]">
            <label className="flex flex-col gap-1.5">
              <span className="text-sm text-txt-soft">书籍目录链接</span>
              <input
                value={bookUrl}
                onChange={(event) => setBookUrl(event.target.value)}
                className="h-11 rounded-md border border-border bg-white px-3 text-sm outline-none focus:border-accent"
                placeholder="https://www.bqg128.cc/book/17322/"
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-sm text-txt-soft">导出目录</span>
              <input
                value={outputDir}
                onChange={(event) => setOutputDir(event.target.value)}
                className="h-11 rounded-md border border-border bg-white px-3 text-sm outline-none focus:border-accent"
                placeholder="data/exports"
              />
            </label>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={inspectLoading}
              className="h-11 rounded-md bg-accent px-5 text-sm font-semibold text-white disabled:opacity-60"
            >
              {inspectLoading ? "正在读取章节..." : "获取书名和章节"}
            </button>
            <span className="self-center text-sm text-txt-soft">
              先检测目录，再选择章节范围和前情提要长度。
            </span>
          </div>
        </form>
      </Card>

      {error ? (
        <Card className="border-danger/20 bg-danger-soft/70">
          <div className="text-sm text-danger">{error}</div>
        </Card>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-[0.92fr_1.08fr]">
        <Card>
          <SectionHeader title="选择范围" />
          {!book ? (
            <EmptyState message="先输入 book 链接并获取章节目录。" />
          ) : (
            <div className="space-y-4">
              <div className="rounded-md border border-border bg-panel-soft p-4">
                <div className="text-xl font-semibold text-txt">{book.title}</div>
                <div className="mt-1 text-sm text-txt-soft">
                  {book.author ? `作者：${book.author}` : "作者未知"} | 共 {book.chapters.length} 章
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                <label className="flex flex-col gap-1.5">
                  <span className="text-sm text-txt-soft">开始章节</span>
                  <select
                    value={chapterStart}
                    onChange={(event) => setChapterStart(Number(event.target.value))}
                    className="h-10 rounded-md border border-border bg-white px-3 text-sm"
                  >
                    {book.chapters.map((chapter) => (
                      <option key={chapter.chapter_id} value={chapter.index}>
                        第 {chapter.index} 章
                      </option>
                    ))}
                  </select>
                </label>

                <label className="flex flex-col gap-1.5">
                  <span className="text-sm text-txt-soft">结束章节</span>
                  <select
                    value={chapterEnd}
                    onChange={(event) => setChapterEnd(Number(event.target.value))}
                    className="h-10 rounded-md border border-border bg-white px-3 text-sm"
                  >
                    {book.chapters.map((chapter) => (
                      <option key={chapter.chapter_id} value={chapter.index}>
                        第 {chapter.index} 章
                      </option>
                    ))}
                  </select>
                </label>

                <label className="flex flex-col gap-1.5">
                  <span className="text-sm text-txt-soft">前情提要章节数</span>
                  <input
                    type="number"
                    min={0}
                    value={contextBefore}
                    onChange={(event) => setContextBefore(Number(event.target.value))}
                    className="h-10 rounded-md border border-border bg-white px-3 text-sm"
                  />
                </label>
              </div>

              <div className="rounded-md border border-border bg-bg-elevated/60 p-4 text-sm text-txt-soft">
                将导出第 {chapterStart} 到第 {chapterEnd} 章，并额外补入前 {contextBefore} 章作为前情提要上下文。
              </div>

              <button
                type="button"
                disabled={exportLoading || chapterEnd < chapterStart}
                onClick={handleExport}
                className="h-11 rounded-md bg-success px-5 text-sm font-semibold text-white disabled:opacity-60"
              >
                {exportLoading ? "正在导出正文..." : "导出选中章节"}
              </button>

              {exportResult ? (
                <div className="rounded-md border border-success/30 bg-success-soft p-4 text-sm text-txt">
                  <div className="font-medium">导出完成</div>
                  <div className="mt-1 text-txt-soft">文本：{exportResult.text_output}</div>
                  <div className="text-txt-soft">JSON：{exportResult.json_output}</div>
                  <div className="text-txt-soft">
                    已选 {exportResult.selected_count} 章，补入前文 {exportResult.context_count} 章。
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </Card>

        <Card className="min-h-[560px]">
          <SectionHeader
            title="章节目录"
            extra={
              <input
                value={chapterFilter}
                onChange={(event) => setChapterFilter(event.target.value)}
                className="h-9 w-52 rounded-md border border-border bg-white px-3 text-sm outline-none focus:border-accent"
                placeholder="筛选章节标题"
              />
            }
          />
          {!book ? (
            <EmptyState message="检测成功后，这里会显示章节列表。" />
          ) : (
            <div className="space-y-2 overflow-y-auto pr-1 max-h-[640px]">
              {filteredChapters.map((chapter) => {
                const isContext = chapter.index >= Math.max(1, chapterStart - contextBefore) && chapter.index < chapterStart;
                const isSelected = chapter.index >= chapterStart && chapter.index <= chapterEnd;
                return (
                  <div
                    key={chapter.chapter_id}
                    className={[
                      "rounded-md border px-3 py-2.5 transition-colors",
                      isSelected
                        ? "border-accent bg-accent-soft/70"
                        : isContext
                          ? "border-warning/30 bg-warning-soft/80"
                          : "border-border bg-panel-soft/40",
                    ].join(" ")}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-medium text-txt">
                        {String(chapter.index).padStart(4, "0")}. {chapter.title}
                      </div>
                      {isSelected ? (
                        <Badge label="选中" variant="accent" />
                      ) : isContext ? (
                        <Badge label="前情提要" variant="warning" />
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
