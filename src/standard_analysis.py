"""Standard analysis mode: Genre -> Chapter split -> Key event extraction (LLM) -> Rule scoring -> Output.

Standard analysis mode. Genre classification, chapter splitting, per-chapter key event extraction,
causal_analysis, and episode generation.
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .chaptering import split_into_chapters
from .config import Paths
from .models import ChapterKeyEvent, ChapterKeyEventSet, GenreClassification, JsonDict
from .prompt_loader import load_prompt, render_prompt
from .rule_scoring import score_chapter
from .runtime import RunLogger, StageCache, write_artifact
from .schema_validator import SchemaValidationError, SchemaValidator
from .stages import GenreClassifier, LLMClient
from .stats import PipelineStats

_log = logging.getLogger(__name__)


class ChapterKeyEventExtractor:
    """LLM stage: extract key events directly at chapter level."""

    _max_tokens = 4096

    def __init__(
        self,
        client: LLMClient,
        paths: Paths,
        validator: SchemaValidator,
        max_retries: int = 2,
    ) -> None:
        self.client = client
        self.paths = paths
        self.validator = validator
        self.max_retries = max_retries

    def run(self, chapter_text: str, genre_hint: str = "") -> ChapterKeyEventSet:
        prompt = self._build_prompt(chapter_text, genre_hint)
        result = self._complete_validated(prompt, "chapter_key_events.schema.json")
        events = [ChapterKeyEvent(**e) for e in result.get("events", [])]
        return ChapterKeyEventSet(
            events=events,
            chapter_summary=result.get("chapter_summary", ""),
        )

    def _build_prompt(self, chapter_text: str, genre_hint: str) -> str:
        template = load_prompt(self.paths.prompts_dir / "chapter_key_events.md")
        hint_block = f"流派提示：{genre_hint}\n" if genre_hint else ""
        return render_prompt(template, genre_hint=hint_block, text=chapter_text)

    def _complete_validated(self, prompt: str, schema_name: str) -> JsonDict:
        current_prompt = prompt
        for attempt in range(self.max_retries + 1):
            result = self.client.complete_json(current_prompt, max_tokens=self._max_tokens)
            try:
                self.validator.validate(schema_name, result)
                return result
            except SchemaValidationError as exc:
                if attempt >= self.max_retries:
                    raise
                current_prompt = (
                    f"{prompt}\n\n"
                    "Your previous response did not match the required JSON shape.\n"
                    f"Validation error: {exc}\n"
                    "Return corrected JSON only."
                )
        raise RuntimeError("Unreachable")


def _process_chapter(
    chapter_id: str,
    chapter_title: str,
    chapter_text: str,
    extractor: ChapterKeyEventExtractor,
    genre_hint: str,
    cache: StageCache | None,
    stats: PipelineStats | None,
) -> dict[str, Any]:
    """Process a single chapter: cache check -> LLM extract -> return result dict."""
    cache_payload = {"chapter_text": chapter_text[:500], "genre": genre_hint}

    # Cache hit?
    if cache is not None:
        cached = cache.get("chapter_key_events", cache_payload)
        if cached is not None:
            return cached

    # LLM call
    event_set = extractor.run(chapter_text, genre_hint=genre_hint)

    # Record token usage
    if stats is not None:
        usage = getattr(extractor.client, "last_usage", None)
        if usage and isinstance(usage, dict):
            stats.record_call(
                stage="chapter_key_events",
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                duration_seconds=0.0,
                chapter_id=chapter_id,
            )

    result = {
        "chapter_id": chapter_id,
        "title": chapter_title,
        "chapter_summary": event_set.chapter_summary,
        "key_events": [asdict(e) for e in event_set.events],
        "status": "ok",
    }

    # Write to cache
    if cache is not None:
        cache.set("chapter_key_events", cache_payload, result)

    return result


def run_standard_analysis(
    text: str,
    client: LLMClient,
    cache: StageCache | None = None,
    logger: RunLogger | None = None,
    artifacts_dir: Path | None = None,
    stats: PipelineStats | None = None,
    max_workers: int = 4,
) -> dict[str, Any]:
    """Run the standard analysis pipeline.

    Genre -> Chapter split -> Per-chapter key event extraction (LLM, concurrent)
    -> Rule scoring -> Output dict.
    """
    paths = Paths.discover()
    validator = SchemaValidator(paths.schemas_dir)

    # 1. Chapter split
    chapters = split_into_chapters(text)
    if logger:
        logger.log("standard_chapters_split", count=len(chapters))

    if not chapters:
        return {
            "mode": "standard_analysis",
            "genre": {},
            "chapters": [],
            "failures": [],
            "stats": stats.to_dict() if stats else {},
        }

    # 2. Genre classification (use first chapter text)
    genre_classifier = GenreClassifier(client, paths, validator)
    try:
        genre_result = genre_classifier.run(chapters[0].text)
        genre_hint = genre_result.primary_genre
        if stats is not None:
            usage = getattr(client, "last_usage", None)
            if usage and isinstance(usage, dict):
                stats.record_call(
                    stage="genre",
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    duration_seconds=0.0,
                )
    except Exception as exc:
        _log.warning("Genre classification failed, proceeding without: %s", exc)
        genre_result = GenreClassification(primary_genre="unknown", subgenre="unknown")
        genre_hint = ""

    if logger:
        logger.log("standard_genre", genre=genre_hint)

    # 3. Concurrent key event extraction
    extractor = ChapterKeyEventExtractor(client, paths, validator)
    chapter_results: list[dict[str, Any]] = [{}] * len(chapters)
    failures: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_idx = {}
        for idx, ch in enumerate(chapters):
            fut = pool.submit(
                _process_chapter,
                ch.chapter_id,
                ch.title,
                ch.text,
                extractor,
                genre_hint,
                cache,
                stats,
            )
            future_to_idx[fut] = idx

        for fut in as_completed(future_to_idx):
            idx = future_to_idx[fut]
            ch = chapters[idx]
            try:
                chapter_results[idx] = fut.result()
            except Exception as exc:
                _log.warning("Chapter %s failed: %s", ch.chapter_id, exc)
                failure_entry = {
                    "chapter_id": ch.chapter_id,
                    "title": ch.title,
                    "error": str(exc),
                }
                failures.append(failure_entry)
                chapter_results[idx] = {
                    "chapter_id": ch.chapter_id,
                    "title": ch.title,
                    "chapter_summary": "",
                    "key_events": [],
                    "status": "error",
                }
                if logger:
                    logger.log("standard_chapter_error", chapter_id=ch.chapter_id, error=str(exc))

    # 4. Rule scoring
    for ch_result in chapter_results:
        if ch_result.get("status") != "ok":
            ch_result["importance_score"] = 0
            ch_result["importance_reason"] = ""
            continue
        # Reconstruct ChapterKeyEventSet from raw dicts for the scorer
        event_objs = [ChapterKeyEvent(**e) for e in ch_result.get("key_events", [])]
        event_set = ChapterKeyEventSet(
            events=event_objs,
            chapter_summary=ch_result.get("chapter_summary", ""),
        )
        score_out = score_chapter(event_set)
        ch_result["importance_score"] = score_out["importance_score"]
        ch_result["importance_reason"] = score_out["importance_reason"]

    # 5. Write artifacts
    if artifacts_dir is not None:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        write_artifact(artifacts_dir / "genre.json", asdict(genre_result))
        chapters_dir = artifacts_dir / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)
        for ch_result in chapter_results:
            cid = ch_result.get("chapter_id", "unknown")
            write_artifact(chapters_dir / f"{cid}.json", ch_result)
        if logger:
            logger.log("standard_artifacts_written", dir=str(artifacts_dir))

    # 6. Build output
    output = {
        "mode": "standard_analysis",
        "genre": asdict(genre_result),
        "chapters": chapter_results,
        "failures": failures,
        "stats": stats.to_dict() if stats else {},
    }

    if logger:
        logger.log(
            "standard_analysis_complete",
            total_chapters=len(chapters),
            ok_chapters=sum(1 for c in chapter_results if c.get("status") == "ok"),
            failed_chapters=len(failures),
        )

    return output
