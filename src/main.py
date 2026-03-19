from __future__ import annotations

import argparse
import os
from pathlib import Path

from .config import ModelConfig
from .runtime import RunLogger, RunPaths, StageCache, compute_book_fingerprint, save_json
from .stages import AnthropicLLMClient, LLMClient, OpenAILLMClient
from .stats import PipelineStats
from .web_crawler import (
    crawl_novel_book,
    format_chapter_listing,
    save_crawled_chapters,
    save_selected_chapters,
    select_chapters,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the web novel extraction pipeline.")
    parser.add_argument("input", type=Path, nargs="?", default=None, help="Path to a UTF-8 text file.")
    parser.add_argument("--crawl-url", default=None, help="Fetch a novel index page and save merged chapter text.")
    parser.add_argument("--crawl-limit", type=int, default=None, help="Only fetch the first N chapters.")
    parser.add_argument("--crawl-json-output", type=Path, default=None, help="JSON output path for crawled chapters.")
    parser.add_argument("--crawl-encoding", default=None, help="Fixed response encoding for crawl mode.")
    parser.add_argument("--list-chapters", action="store_true", help="Print chapter list then exit.")
    parser.add_argument("--chapter-start", type=int, default=None, help="1-based starting chapter number.")
    parser.add_argument("--chapter-end", type=int, default=None, help="1-based ending chapter number.")
    parser.add_argument("--context-before-chapters", type=int, default=0, help="Prepend N earlier chapters as context.")
    parser.add_argument("--output", type=Path, default=Path("data/processed/output.json"), help="JSON result path.")
    parser.add_argument("--model", default=None, help="Override model name.")
    parser.add_argument("--base-url", default=None, help="Override OpenAI-compatible base URL.")
    parser.add_argument("--use-anthropic", action="store_true", help="Use Anthropic API.")
    parser.add_argument("--model-config", type=Path, default=None, help="Per-stage model config JSON.")
    parser.add_argument("--use-cache", action="store_true", default=True, help="Enable LLM response caching.")
    parser.add_argument("--no-cache", action="store_true", help="Disable LLM response caching.")
    parser.add_argument("--project", default=None, help="Project name for cache namespace.")
    parser.add_argument("--max-workers", type=int, default=4, help="Max concurrent workers.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # ── Crawl mode ──
    if args.crawl_url:
        encoding = args.crawl_encoding or None
        book = crawl_novel_book(args.crawl_url, limit=args.crawl_limit, encoding=encoding)
        if args.list_chapters:
            print(format_chapter_listing(book))
            return
        if args.chapter_start or args.chapter_end:
            selected = select_chapters(
                book, start=args.chapter_start, end=args.chapter_end,
                context_before=args.context_before_chapters,
            )
            save_selected_chapters(selected, args.output, json_output=args.crawl_json_output)
        else:
            save_crawled_chapters(book, args.output, json_output=args.crawl_json_output)
        return

    # ── Standard analysis ──
    if not args.input:
        print("Error: input file is required when not using --crawl-url")
        return

    api_key = os.environ.get("OPENAI_API_KEY", "")
    model = args.model or os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    base_url = args.base_url or os.environ.get("OPENAI_BASE_URL")
    use_anthropic = args.use_anthropic or os.environ.get("USE_ANTHROPIC", "").lower() in ("1", "true")
    use_cache = args.use_cache and not args.no_cache

    stats = PipelineStats()

    if use_anthropic:
        default_client: LLMClient = AnthropicLLMClient(api_key=api_key, model=model)
    else:
        default_client = OpenAILLMClient(api_key=api_key, model=model, base_url=base_url)

    text = args.input.read_text(encoding="utf-8")

    run_paths = RunPaths.create("data/runs", project_name=args.project)
    fingerprint = compute_book_fingerprint(text)
    cache = StageCache.for_book(Path("data/cache"), fingerprint, model) if use_cache else None
    logger = RunLogger(run_paths.log_dir / "run.jsonl")

    from .standard_analysis import run_standard_analysis

    result = run_standard_analysis(
        text=text,
        client=default_client,
        cache=cache,
        logger=logger,
        artifacts_dir=run_paths.artifacts_dir,
        stats=stats,
        max_workers=args.max_workers,
    )

    save_json(result, run_paths.output_dir / "standard_output.json")

    ch_total = len(result.get("chapters", []))
    ch_ok = sum(1 for c in result.get("chapters", []) if c.get("status") == "ok")
    print(f"Standard analysis complete -> {run_paths.output_dir}")
    print(f"  Genre: {result.get('genre', {}).get('primary_genre', 'unknown')}")
    print(f"  Chapters: {ch_ok}/{ch_total} succeeded")

    if stats:
        summary = stats.to_dict()
        print(f"  Model calls: {len(summary.get('calls', []))}")


if __name__ == "__main__":
    main()
