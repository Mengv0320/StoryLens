"""Layered narrative analysis engine.

Takes standard_analysis chapter results and produces:
  - Layer 1: GroupSummary per chapter group (rolling context)
  - Layer 2: BookSynthesis across all groups
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from typing import Any

from .config import Paths
from .narrative_types import (
    BookSynthesis,
    GroupSummary,
    NarrativeResult,
    default_book_synthesis,
    default_group_summary,
)
from .prompt_loader import load_prompt, render_prompt
from .runtime import RunLogger, StageCache
from .schema_validator import SchemaValidator
from .stages import LLMClient
from .stats import PipelineStats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _group_chapters(
    chapter_results: list[dict],
    group_size: int,
) -> list[list[dict]]:
    """Split chapter_results into consecutive groups of *group_size*."""
    return [
        chapter_results[i : i + group_size]
        for i in range(0, len(chapter_results), group_size)
    ]


def _cache_key_for_group(chapter_ids: list[str]) -> dict[str, Any]:
    """Deterministic cache payload based on sorted chapter IDs."""
    return {"chapter_ids": sorted(chapter_ids)}


def _chapter_range_label(chapters: list[dict]) -> str:
    """Build a human-readable range like '第1章 ~ 第5章'."""
    if not chapters:
        return ""
    first_title = chapters[0].get("title", "")
    last_title = chapters[-1].get("title", "")
    return f"{first_title} ~ {last_title}"


def _chapters_data_json(chapters: list[dict]) -> str:
    """Serialize chapter list to compact JSON for prompt injection."""
    slim = []
    for ch in chapters:
        slim.append({
            "chapter_id": ch.get("chapter_id", ""),
            "title": ch.get("title", ""),
            "chapter_summary": ch.get("chapter_summary", ""),
            "key_events": ch.get("key_events", []),
            "importance_score": ch.get("importance_score", 1),
        })
    return json.dumps(slim, ensure_ascii=False)


def _safe_int(value: Any, default: int = 0) -> int:
    """Convert value to int with fallback on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _parse_group_summary(raw: dict, group_id: str, chapter_range: str,
                         chapter_ids: list[str]) -> GroupSummary:
    """Convert LLM JSON dict to GroupSummary dataclass."""
    return GroupSummary(
        group_id=group_id,
        chapter_range=chapter_range,
        chapter_ids=chapter_ids,
        plot_progress=raw.get("plot_progress", ""),
        new_foreshadowing=raw.get("new_foreshadowing", []),
        resolved_foreshadowing=raw.get("resolved_foreshadowing", []),
        open_questions=raw.get("open_questions", []),
        subplot_threads=raw.get("subplot_threads", []),
        character_arcs=raw.get("character_arcs", []),
        key_causality=raw.get("key_causality", []),
        tension_level=_safe_int(raw.get("tension_level", 1), default=1),
    )


def _parse_book_synthesis(raw: dict, book_title: str = "未知") -> BookSynthesis:
    """Convert LLM JSON dict to BookSynthesis dataclass."""
    return BookSynthesis(
        title=book_title,
        main_plotline=raw.get("main_plotline", ""),
        subplot_summary=raw.get("subplot_summary", []),
        foreshadowing_tracker=raw.get("foreshadowing_tracker", []),
        character_arcs=raw.get("character_arcs", []),
        tension_curve=raw.get("tension_curve", []),
        themes=raw.get("themes", []),
        open_questions=raw.get("open_questions", []),
        quality_notes=raw.get("quality_notes", []),
    )


# ---------------------------------------------------------------------------
# Layer 1 – Group summaries (sequential, rolling context)
# ---------------------------------------------------------------------------

def _summarize_group(
    group_index: int,
    total_groups: int,
    chapters: list[dict],
    genre_hint: str,
    previous_summary: str,
    client: LLMClient,
    paths: Paths,
    validator: SchemaValidator,
    cache: StageCache | None,
    logger: RunLogger | None,
    stats: PipelineStats | None,
) -> GroupSummary:
    """Produce a GroupSummary for one chapter group via LLM."""
    chapter_ids = [ch.get("chapter_id", "") for ch in chapters]
    group_id = f"grp_{group_index + 1:03d}"
    chapter_range = _chapter_range_label(chapters)

    # --- cache check ---
    cache_payload = _cache_key_for_group(chapter_ids)
    if cache:
        hit = cache.get("narrative_summary", cache_payload)
        if hit is not None:
            if logger:
                logger.log("cache_hit", stage="narrative_summary",
                           group_id=group_id)
            return _parse_group_summary(hit, group_id, chapter_range,
                                        chapter_ids)

    # --- build prompt ---
    template = load_prompt(paths.prompts_dir / "narrative_summary.md")
    prompt = render_prompt(
        template,
        previous_summary=previous_summary or "无（这是第一组）",
        chapters_data=_chapters_data_json(chapters),
        genre_hint=genre_hint,
        group_index=str(group_index + 1),
        total_groups=str(total_groups),
    )

    # --- LLM call ---
    t0 = time.time()
    raw = client.complete_json(prompt, max_tokens=4096)
    elapsed = time.time() - t0

    # --- validate ---
    validation_failed = False
    try:
        validator.validate("narrative_summary.schema.json", raw)
    except Exception as exc:
        validation_failed = True
        if logger:
            logger.log("validation_warning", stage="narrative_summary",
                       group_id=group_id, error=str(exc))
        # If raw is missing the critical 'plot_progress' field, use defaults
        if not isinstance(raw, dict) or not raw.get("plot_progress"):
            return default_group_summary(group_id, chapter_range, chapter_ids)

    # --- stats (read from client.last_usage, not from raw JSON) ---
    if stats:
        usage = getattr(client, "last_usage", None) or {}
        stats.record_call(
            stage="narrative_summary",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            duration_seconds=elapsed,
        )

    # --- cache write (skip if validation failed) ---
    if cache and not validation_failed:
        cache.set("narrative_summary", cache_payload, raw)

    return _parse_group_summary(raw, group_id, chapter_range, chapter_ids)


# ---------------------------------------------------------------------------
# Layer 2 – Book synthesis
# ---------------------------------------------------------------------------

def _synthesize_book(
    group_summaries: list[GroupSummary],
    genre: dict,
    total_chapters: int,
    book_title: str,
    client: LLMClient,
    paths: Paths,
    validator: SchemaValidator,
    cache: StageCache | None,
    logger: RunLogger | None,
    stats: PipelineStats | None,
) -> BookSynthesis:
    """Produce a BookSynthesis from all group summaries via LLM."""
    # --- cache check ---
    group_ids = [g.group_id for g in group_summaries]
    cache_payload = {"group_ids": sorted(group_ids)}
    if cache:
        hit = cache.get("book_synthesis", cache_payload)
        if hit is not None:
            if logger:
                logger.log("cache_hit", stage="book_synthesis")
            return _parse_book_synthesis(hit)

    # --- build prompt ---
    summaries_json = json.dumps(
        [asdict(g) for g in group_summaries], ensure_ascii=False,
    )
    template = load_prompt(paths.prompts_dir / "book_synthesis.md")
    prompt = render_prompt(
        template,
        group_summaries=summaries_json,
        genre=json.dumps(genre, ensure_ascii=False),
        total_chapters=str(total_chapters),
        total_groups=str(len(group_summaries)),
        book_title=book_title,
    )

    # --- LLM call ---
    t0 = time.time()
    raw = client.complete_json(prompt, max_tokens=8192)
    elapsed = time.time() - t0

    # --- validate ---
    validation_failed = False
    try:
        validator.validate("book_synthesis.schema.json", raw)
    except Exception as exc:
        validation_failed = True
        if logger:
            logger.log("validation_warning", stage="book_synthesis",
                       error=str(exc))
        # If raw is missing the critical 'main_plotline' field, use defaults
        if not isinstance(raw, dict) or not raw.get("main_plotline"):
            return default_book_synthesis()

    # --- stats (read from client.last_usage, not from raw JSON) ---
    if stats:
        usage = getattr(client, "last_usage", None) or {}
        stats.record_call(
            stage="book_synthesis",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            duration_seconds=elapsed,
        )

    # --- cache write (skip if validation failed) ---
    if cache and not validation_failed:
        cache.set("book_synthesis", cache_payload, raw)

    return _parse_book_synthesis(raw, book_title)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_narrative_analysis(
    chapter_results: list[dict],
    genre: dict,
    book_title: str,
    client: LLMClient,
    paths: Paths,
    validator: SchemaValidator,
    cache: StageCache | None = None,
    logger: RunLogger | None = None,
    stats: PipelineStats | None = None,
    group_size: int = 5,
) -> NarrativeResult:
    """Run two-layer narrative analysis on standard_analysis chapter data.

    Layer 1: sequential group summaries with rolling context.
    Layer 2: book-level synthesis from all group summaries.
    """
    result = NarrativeResult()

    # --- edge case: no chapters ---
    if not chapter_results:
        result.book_synthesis = default_book_synthesis()
        return result

    # --- filter to ok chapters only ---
    ok_chapters = [
        ch for ch in chapter_results
        if ch.get("status") == "ok"
    ]
    if not ok_chapters:
        result.book_synthesis = default_book_synthesis()
        return result

    genre_hint = genre.get("primary_genre", "未知")

    # --- Layer 1: group summaries (sequential) ---
    groups = _group_chapters(ok_chapters, group_size)
    total_groups = len(groups)
    previous_summary = ""

    for idx, group_chapters in enumerate(groups):
        try:
            gs = _summarize_group(
                group_index=idx,
                total_groups=total_groups,
                chapters=group_chapters,
                genre_hint=genre_hint,
                previous_summary=previous_summary,
                client=client,
                paths=paths,
                validator=validator,
                cache=cache,
                logger=logger,
                stats=stats,
            )
            result.group_summaries.append(gs)
            # rolling context for next group
            previous_summary = gs.plot_progress
        except Exception as exc:
            chapter_ids = [ch.get("chapter_id", "") for ch in group_chapters]
            group_id = f"grp_{idx + 1:03d}"
            chapter_range = _chapter_range_label(group_chapters)
            if logger:
                logger.log("group_summary_failed", group_id=group_id,
                           error=str(exc))
            result.group_summaries.append(
                default_group_summary(group_id, chapter_range, chapter_ids)
            )
            # keep previous_summary unchanged so next group still has context

    # --- Layer 2: book synthesis ---
    try:
        result.book_synthesis = _synthesize_book(
            group_summaries=result.group_summaries,
            genre=genre,
            total_chapters=len(chapter_results),
            book_title=book_title,
            client=client,
            paths=paths,
            validator=validator,
            cache=cache,
            logger=logger,
            stats=stats,
        )
    except Exception as exc:
        if logger:
            logger.log("book_synthesis_failed", error=str(exc))
        result.book_synthesis = default_book_synthesis()

    return result
