from __future__ import annotations

import argparse
import glob as globmod
import os
from pathlib import Path

from .config import ModelConfig
from .exporters import get_exporter
from .pipeline import NovelPipeline, _build_client, save_json, save_jsonl
from .runtime import RunLogger, RunPaths, StageCache, compute_book_fingerprint
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
    parser.add_argument(
        "--crawl-url",
        default=None,
        help="Fetch a novel index page, discover chapter links, and save merged chapter text instead of running extraction.",
    )
    parser.add_argument(
        "--crawl-limit",
        type=int,
        default=None,
        help="Only fetch the first N discovered chapters when using --crawl-url.",
    )
    parser.add_argument(
        "--crawl-json-output",
        type=Path,
        default=None,
        help="Optional JSON output path for crawled chapters when using --crawl-url.",
    )
    parser.add_argument(
        "--crawl-encoding",
        default=None,
        help="Optional fixed response encoding for crawl mode, such as utf-8 or gbk.",
    )
    parser.add_argument(
        "--list-chapters",
        action="store_true",
        help="Print the crawled book title and chapter list, then exit.",
    )
    parser.add_argument(
        "--chapter-start",
        type=int,
        default=None,
        help="1-based starting chapter number to export from crawl mode.",
    )
    parser.add_argument(
        "--chapter-end",
        type=int,
        default=None,
        help="1-based ending chapter number to export from crawl mode.",
    )
    parser.add_argument(
        "--context-before-chapters",
        type=int,
        default=0,
        help="When chapter range is selected, prepend this many earlier chapters as summary context.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/output.json"),
        help="Where to write the JSON result.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the model name. Defaults to OPENAI_MODEL or gpt-4.1-mini.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Optional environment file with OPENAI_API_KEY and OPENAI_MODEL.",
    )
    parser.add_argument(
        "--mode",
        choices=["excerpt", "book", "fast_scan", "deep_analysis", "standard_analysis"],
        default="excerpt",
        help="Run mode: excerpt (single), book (full novel), fast_scan (quick overview), deep_analysis (alias for book), standard_analysis (lite key-event extraction).",
    )
    parser.add_argument(
        "--chapters-per-episode",
        type=int,
        default=5,
        help="Used in book mode to group chapters into episodes.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable on-disk stage cache.",
    )
    parser.add_argument(
        "--split-strategy",
        choices=["v1", "v2"],
        default="v2",
        help="Episode split strategy: v1 (threshold-based) or v2 (multi-dimensional climax-aware).",
    )
    # Batch input
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help="Directory of .txt files to process in batch (book mode).",
    )
    parser.add_argument(
        "--glob",
        default="*.txt",
        help="Glob pattern for --input-dir file matching (default: '*.txt').",
    )
    # Resume
    parser.add_argument(
        "--resume",
        type=Path,
        default=None,
        metavar="RUN_DIR",
        help="Resume a previous run from the given output directory.",
    )
    # Export format
    parser.add_argument(
        "--export-format",
        choices=["json", "markdown", "csv", "api"],
        default=None,
        help="Additional export format (json is always written).",
    )
    # Per-stage models
    parser.add_argument("--genre-model", default=None, help="Model for genre classification stage.")
    parser.add_argument("--extraction-model", default=None, help="Model for scene split and extraction stages.")
    parser.add_argument("--analysis-model", default=None, help="Model for normalization and scoring stages.")
    parser.add_argument("--summary-model", default=None, help="Model for episode summary stage.")
    # Per-stage base URLs
    parser.add_argument("--genre-base-url", default=None, help="Base URL for genre model API.")
    parser.add_argument("--extraction-base-url", default=None, help="Base URL for extraction model API.")
    parser.add_argument("--analysis-base-url", default=None, help="Base URL for analysis model API.")
    parser.add_argument("--summary-base-url", default=None, help="Base URL for summary model API.")
    # Cost estimation
    parser.add_argument(
        "--price-per-1m-prompt",
        type=float,
        default=None,
        help="Price per 1M prompt tokens in USD (default: 0.15).",
    )
    parser.add_argument(
        "--price-per-1m-completion",
        type=float,
        default=None,
        help="Price per 1M completion tokens in USD (default: 0.60).",
    )
    # Continue from previous run
    parser.add_argument(
        "--continue-from",
        type=Path,
        default=None,
        metavar="RUN_DIR",
        help="Continue from a previous run's checkpoint. Processes only new chapters and re-plans episodes.",
    )
    parser.add_argument(
        "--project",
        default=None,
        help="Project name for cache namespace (default: input filename stem).",
    )
    parser.add_argument(
        "--stable-ids",
        action="store_true",
        help="Use content-hash based chapter IDs (auto-enabled with --continue-from).",
    )
    # Quality
    parser.add_argument(
        "--skip-quality",
        action="store_true",
        help="Skip quality assessment after book processing.",
    )
    # Concurrency
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Max parallel threads for chapter/scene/episode processing (default: 4). Set to 0 for auto-detect.",
    )
    return parser.parse_args()


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> None:
    args = parse_args()
    if args.crawl_url:
        output_path = args.output if args.output.suffix else args.output / "novel.txt"
        crawl_limit = args.crawl_limit
        if args.chapter_end is not None:
            crawl_limit = max(args.chapter_end, crawl_limit or 0)
        book = crawl_novel_book(
            args.crawl_url,
            limit=crawl_limit or None,
            encoding=args.crawl_encoding,
        )
        if args.list_chapters:
            print(format_chapter_listing(book))
            return

        context_chapters, selected_chapters = select_chapters(
            book.chapters,
            start=args.chapter_start,
            end=args.chapter_end,
            context_before=args.context_before_chapters,
        )
        if selected_chapters and (args.chapter_start is not None or args.chapter_end is not None):
            save_selected_chapters(
                book,
                context_chapters=context_chapters,
                selected_chapters=selected_chapters,
                output_path=output_path,
                json_output_path=args.crawl_json_output,
            )
            selected_range = f"{args.chapter_start or 1}-{args.chapter_end or len(book.chapters)}"
            print(f"Book: {book.title}")
            print(f"Selected chapters: {selected_range}")
            print(f"Context chapters: {len(context_chapters)}")
            print(f"Saved selected content -> {output_path}")
        else:
            save_crawled_chapters(book.chapters, output_path=output_path, json_output_path=args.crawl_json_output)
            print(f"Book: {book.title}")
            print(f"Crawled {len(book.chapters)} chapters -> {output_path}")
        if args.crawl_json_output:
            print(f"JSON -> {args.crawl_json_output}")
        return

    load_env_file(args.env_file)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required. Set it in the environment or .env file.")

    model = args.model or os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    base_url = os.environ.get("OPENAI_BASE_URL")

    # Build ModelConfig from per-stage CLI args and env vars
    model_config = ModelConfig(
        genre_model=args.genre_model or os.environ.get("GENRE_MODEL"),
        genre_base_url=args.genre_base_url or os.environ.get("GENRE_BASE_URL"),
        extraction_model=args.extraction_model or os.environ.get("EXTRACTION_MODEL"),
        extraction_base_url=args.extraction_base_url or os.environ.get("EXTRACTION_BASE_URL"),
        analysis_model=args.analysis_model or os.environ.get("ANALYSIS_MODEL"),
        analysis_base_url=args.analysis_base_url or os.environ.get("ANALYSIS_BASE_URL"),
        summary_model=args.summary_model or os.environ.get("SUMMARY_MODEL"),
        summary_base_url=args.summary_base_url or os.environ.get("SUMMARY_BASE_URL"),
    )
    has_per_stage = any([
        model_config.genre_model, model_config.extraction_model,
        model_config.analysis_model, model_config.summary_model,
    ])

    # Auto-detect client type: Anthropic if ANTHROPIC_API_KEY is set or base_url uses Anthropic-format endpoint
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    use_anthropic = bool(anthropic_key) or (base_url and "openai" not in (base_url or "").lower())
    provider = os.environ.get("LLM_PROVIDER", "").lower()
    if provider == "anthropic" or anthropic_key:
        use_anthropic = True
    elif provider == "openai":
        use_anthropic = False

    # Build per-stage clients if any per-stage model is configured
    clients_by_stage: dict[str, LLMClient] = {}
    if has_per_stage:
        effective_key = (anthropic_key or api_key) if use_anthropic else api_key
        for stage in ("genre", "scene_split", "scene_extraction", "normalized_events", "causal_analysis", "scores", "episode"):
            clients_by_stage[stage] = _build_client(effective_key, model, base_url, stage, model_config, use_anthropic=use_anthropic)

    # Build stats tracker
    token_prices = {}
    if args.price_per_1m_prompt is not None:
        token_prices["prompt"] = args.price_per_1m_prompt / 1_000_000
    if args.price_per_1m_completion is not None:
        token_prices["completion"] = args.price_per_1m_completion / 1_000_000
    stats = PipelineStats(token_prices=token_prices if token_prices else None)

    if use_anthropic:
        effective_key = anthropic_key or api_key
        default_client = AnthropicLLMClient(api_key=effective_key, model=model, base_url=base_url or "https://api.anthropic.com")
    else:
        default_client = OpenAILLMClient(api_key=api_key, model=model, base_url=base_url)

    # --- Batch directory mode ---
    if args.input_dir:
        input_dir = args.input_dir.resolve()
        if not input_dir.is_dir():
            raise RuntimeError(f"--input-dir is not a directory: {input_dir}")
        pattern = args.glob
        files = sorted(input_dir.glob(pattern))
        if not files:
            raise RuntimeError(f"No files matching '{pattern}' in {input_dir}")
        print(f"Batch mode: {len(files)} file(s) found in {input_dir}")
        for txt_file in files:
            book_name = txt_file.stem
            output_dir = args.output.parent / f"run_{book_name}" if args.output else Path(f"data/processed/run_{book_name}")
            run_paths = RunPaths.from_output(output_dir / "output.json")
            run_paths.ensure()
            logger = RunLogger(run_paths.logs_dir / "run.jsonl")
            book_stats = PipelineStats(token_prices=token_prices if token_prices else None)
            print(f"Processing: {txt_file.name}")
            text = txt_file.read_text(encoding="utf-8")
            book_fp = compute_book_fingerprint(text)
            base_cache = Path("data/cache")
            cache = None if args.no_cache else StageCache.for_book(base_cache, book_fp, model)
            pipeline = NovelPipeline(
                client=default_client,
                cache=cache,
                logger=logger,
                artifacts_dir=run_paths.artifacts_dir,
                stats=book_stats,
                skip_quality=args.skip_quality,
                clients_by_stage=clients_by_stage if has_per_stage else None,
                max_workers=args.max_workers,
            )
            try:
                result = pipeline.run_book(
                    text,
                    chapters_per_episode=args.chapters_per_episode,
                    split_strategy=args.split_strategy,
                    stable_ids=args.stable_ids,
                )
                save_json(result, run_paths.output_dir / "book_output.json")
                save_jsonl(result["chapters"], run_paths.output_dir / "chapters.jsonl")
                save_jsonl(result["episodes"], run_paths.output_dir / "episodes.jsonl")
                save_jsonl(result["episode_plan"], run_paths.output_dir / "episode_plan.jsonl")
                save_jsonl(result["failures"], run_paths.output_dir / "failures.jsonl")
                if args.export_format and args.export_format != "json":
                    exporter = get_exporter(args.export_format)
                    exporter.export(result, run_paths.output_dir / f"export_{args.export_format}")
                print(f"  Done: {txt_file.name} -> {run_paths.output_dir}")
            except Exception as exc:
                print(f"  FAILED: {txt_file.name}: {type(exc).__name__}: {exc}")
        return

    # --- Resume mode ---
    if args.resume:
        resume_dir = args.resume.resolve()
        if not resume_dir.is_dir():
            raise RuntimeError(f"--resume directory does not exist: {resume_dir}")
        if not args.input:
            raise RuntimeError("--resume requires the original input file as positional argument.")
        text = args.input.read_text(encoding="utf-8")
        book_fp = compute_book_fingerprint(text)
        base_cache = Path("data/cache")
        run_paths = RunPaths.from_output(resume_dir / "output.json")
        run_paths.ensure()
        cache = None if args.no_cache else StageCache.for_book(base_cache, book_fp, model)
        logger = RunLogger(run_paths.logs_dir / "run.jsonl")
        pipeline = NovelPipeline(
            client=default_client,
            cache=cache,
            logger=logger,
            artifacts_dir=run_paths.artifacts_dir,
            stats=stats,
            skip_quality=args.skip_quality,
            clients_by_stage=clients_by_stage if has_per_stage else None,
            max_workers=args.max_workers,
        )
        result = pipeline.run_book_resume(
            text,
            run_dir=resume_dir,
            chapters_per_episode=args.chapters_per_episode,
            split_strategy=args.split_strategy,
        )
        save_json(result, run_paths.output_dir / "book_output.json")
        save_jsonl(result["chapters"], run_paths.output_dir / "chapters.jsonl")
        save_jsonl(result["episodes"], run_paths.output_dir / "episodes.jsonl")
        save_jsonl(result["episode_plan"], run_paths.output_dir / "episode_plan.jsonl")
        save_jsonl(result["failures"], run_paths.output_dir / "failures.jsonl")
        if args.export_format and args.export_format != "json":
            exporter = get_exporter(args.export_format)
            exporter.export(result, run_paths.output_dir / f"export_{args.export_format}")
        return

    # --- Continue-from mode (incremental) ---
    if args.continue_from:
        continue_dir = args.continue_from.resolve()
        if not continue_dir.is_dir():
            raise RuntimeError(f"--continue-from directory does not exist: {continue_dir}")
        if not args.input:
            raise RuntimeError("--continue-from requires the input file as positional argument.")
        text = args.input.read_text(encoding="utf-8")
        project_name = args.project or args.input.stem
        book_fp = compute_book_fingerprint(text)
        base_cache = Path("data/cache")
        # Use project-level cache namespace for cross-run cache sharing
        cache = None if args.no_cache else StageCache.for_project(base_cache, project_name, model)
        # Create new run directory
        run_paths = RunPaths.from_output(args.output)
        run_paths.ensure()
        logger = RunLogger(run_paths.logs_dir / "run.jsonl")
        pipeline = NovelPipeline(
            client=default_client,
            cache=cache,
            logger=logger,
            artifacts_dir=run_paths.artifacts_dir,
            stats=stats,
            skip_quality=args.skip_quality,
            clients_by_stage=clients_by_stage if has_per_stage else None,
            max_workers=args.max_workers,
        )
        result = pipeline.run_book_continue(
            text,
            continue_from=continue_dir,
            chapters_per_episode=args.chapters_per_episode,
            split_strategy=args.split_strategy,
        )
        save_json(result, run_paths.output_dir / "book_output.json")
        save_jsonl(result["chapters"], run_paths.output_dir / "chapters.jsonl")
        save_jsonl(result["episodes"], run_paths.output_dir / "episodes.jsonl")
        save_jsonl(result["episode_plan"], run_paths.output_dir / "episode_plan.jsonl")
        save_jsonl(result["failures"], run_paths.output_dir / "failures.jsonl")
        if args.export_format and args.export_format != "json":
            exporter = get_exporter(args.export_format)
            exporter.export(result, run_paths.output_dir / f"export_{args.export_format}")
        print(f"Continue-from completed: {run_paths.output_dir}")
        return

    # --- Single file mode ---
    if not args.input:
        raise RuntimeError("Positional argument 'input' is required unless --input-dir is used.")
    text = args.input.read_text(encoding="utf-8")

    book_fp = compute_book_fingerprint(text)
    base_cache = Path("data/cache")
    run_paths = RunPaths.from_output(args.output)
    run_paths.ensure()
    cache = None if args.no_cache else StageCache.for_book(base_cache, book_fp, model)
    logger = RunLogger(run_paths.logs_dir / "run.jsonl")

    # --- fast_scan mode ---
    if args.mode == "fast_scan":
        from .fast_scan import run_fast_scan
        result = run_fast_scan(
            text=text,
            output_dir=str(run_paths.output_dir),
            client=default_client,
            project_name=args.output.stem if args.output else "novel",
            cache=cache,
            run_logger=logger,
        )
        print(f"Fast scan completed: {result['output_dir']}")
        print(f"  Segments: {result['stats']['segments_completed']}/{result['stats']['total_segments']}")
        print(f"  Key chapters: {result['stats']['key_chapters_completed']}/{result['stats']['key_chapters_count']}")
        print(f"  Elapsed: {result['stats']['elapsed_seconds']}s")
        return

    # --- standard_analysis mode ---
    if args.mode == "standard_analysis":
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
        ch_ok = sum(1 for c in result.get("chapters", []) if c.get("status") == "ok")
        ch_total = len(result.get("chapters", []))
        print(f"Standard analysis completed: {run_paths.output_dir}")
        print(f"  Genre: {result.get('genre', {}).get('primary_genre', 'unknown')}")
        print(f"  Chapters: {ch_ok}/{ch_total} succeeded")
        return

    # deep_analysis is an alias for book mode
    effective_mode = "book" if args.mode == "deep_analysis" else args.mode

    pipeline = NovelPipeline(
        client=default_client,
        cache=cache,
        logger=logger,
        artifacts_dir=run_paths.artifacts_dir,
        stats=stats,
        skip_quality=args.skip_quality,
        clients_by_stage=clients_by_stage if has_per_stage else None,
        max_workers=args.max_workers,
    )
    if effective_mode == "book":
        result = pipeline.run_book(
            text,
            chapters_per_episode=args.chapters_per_episode,
            split_strategy=args.split_strategy,
            stable_ids=getattr(args, "stable_ids", False),
        )
        save_json(result, run_paths.output_dir / "book_output.json")
        save_jsonl(result["chapters"], run_paths.output_dir / "chapters.jsonl")
        save_jsonl(result["episodes"], run_paths.output_dir / "episodes.jsonl")
        save_jsonl(result["episode_plan"], run_paths.output_dir / "episode_plan.jsonl")
        save_jsonl(result["failures"], run_paths.output_dir / "failures.jsonl")
        if args.export_format and args.export_format != "json":
            exporter = get_exporter(args.export_format)
            exporter.export(result, run_paths.output_dir / f"export_{args.export_format}")
        return

    result = pipeline.run_excerpt(text)
    save_json(result, args.output)


if __name__ == "__main__":
    main()
