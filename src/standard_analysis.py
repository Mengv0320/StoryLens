"""Standard analysis mode: Genre -> Chapter split -> Key event extraction (LLM) -> Rule scoring -> Output.

Standard analysis mode. Genre classification, chapter splitting, per-chapter key event extraction,
causal_analysis, and episode generation.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
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

    # Refinement intensity → prompt injection mapping
    _REFINEMENT_INSTRUCTIONS: dict[str, str] = {
        "minimal": (
            "\n\n【精炼强度：精简模式】\n"
            "只提取最核心的关键事件（重要度≥4），忽略次要情节。"
            "每章最多提取3个事件，优先保留：身份揭示、死亡/突破、阵营变动。\n"
        ),
        "standard": "",  # default — no extra instruction
        "detailed": (
            "\n\n【精炼强度：详细模式】\n"
            "尽可能全面地提取事件，包括次要情节线索和伏笔。"
            "每章可提取最多10个事件，注意捕捉：人物心理变化、环境描写暗示、"
            "伏笔铺垫、关系微妙变化等。\n"
        ),
    }

    def __init__(
        self,
        client: LLMClient,
        paths: Paths,
        validator: SchemaValidator,
        max_retries: int = 2,
        refinement_intensity: str = "standard",
    ) -> None:
        self.client = client
        self.paths = paths
        self.validator = validator
        self.max_retries = max_retries
        self.refinement_intensity = refinement_intensity

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
        refinement_block = self._REFINEMENT_INSTRUCTIONS.get(self.refinement_intensity, "")
        return render_prompt(template, genre_hint=hint_block + refinement_block, text=chapter_text)

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
    text_hash = hashlib.sha256(chapter_text.encode()).hexdigest()[:32]
    cache_payload = {"chapter_text_hash": text_hash, "genre": genre_hint}

    # Cache hit?
    if cache is not None:
        cached = cache.get("chapter_key_events", cache_payload)
        if cached is not None:
            if "raw_text" not in cached:
                cached["raw_text"] = chapter_text
            return cached

    # LLM call
    call_start = time.time()
    event_set = extractor.run(chapter_text, genre_hint=genre_hint)
    call_duration = time.time() - call_start

    # Record token usage
    if stats is not None:
        usage = getattr(extractor.client, "last_usage", None)
        if usage and isinstance(usage, dict):
            stats.record_call(
                stage="chapter_key_events",
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                duration_seconds=call_duration,
                chapter_id=chapter_id,
            )

    result = {
        "chapter_id": chapter_id,
        "title": chapter_title,
        "raw_text": chapter_text,
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
    max_workers: int = 4,  # Reserved for future parallel execution; currently sequential
    refinement_intensity: str = "standard",
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

    if artifacts_dir is not None:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        idx_data = [{"chapter_id": ch.chapter_id, "title": ch.title} for ch in chapters]
        write_artifact(artifacts_dir / "chapters_index.json", idx_data)

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
        genre_start = time.time()
        genre_result = genre_classifier.run(chapters[0].text)
        genre_duration = time.time() - genre_start
        genre_hint = genre_result.primary_genre
        if stats is not None:
            usage = getattr(client, "last_usage", None)
            if usage and isinstance(usage, dict):
                stats.record_call(
                    stage="genre",
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    duration_seconds=genre_duration,
                )
    except Exception as exc:
        _log.warning("Genre classification failed, proceeding without: %s", exc)
        genre_result = GenreClassification(primary_genre="unknown", subgenre="unknown")
        genre_hint = ""

    if logger:
        logger.log("standard_genre", genre=genre_hint)

    # 3. Sequential key event extraction with Sliding Window Context & Stream Output
    extractor = ChapterKeyEventExtractor(client, paths, validator, refinement_intensity=refinement_intensity)
    chapter_results: list[dict[str, Any]] = [{} for _ in chapters]
    failures: list[dict[str, Any]] = []

    if artifacts_dir is not None:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        write_artifact(artifacts_dir / "genre.json", asdict(genre_result))
        chapters_dir = artifacts_dir / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)
    else:
        chapters_dir = None

    sliding_window = []

    for idx, ch in enumerate(chapters):
        try:
            # Build sliding window context
            prompt_context = genre_hint
            if sliding_window:
                prompt_context += "\n\n【前文提要（防止逻辑断层）】\n" + "\n".join(sliding_window)

            ch_result = _process_chapter(
                ch.chapter_id,
                ch.title,
                ch.text,
                extractor,
                prompt_context,
                cache,
                stats,
            )
            
            # Rule scoring for single chapter
            if ch_result.get("status") == "ok":
                event_objs = [ChapterKeyEvent(**e) for e in ch_result.get("key_events", [])]
                event_set = ChapterKeyEventSet(
                    events=event_objs,
                    chapter_summary=ch_result.get("chapter_summary", ""),
                )
                score_out = score_chapter(event_set)
                ch_result["importance_score"] = score_out["importance_score"]
                ch_result["importance_reason"] = score_out["importance_reason"]
                
                # Update sliding window (keep last 3 chapters)
                ch_sum = ch_result.get("chapter_summary", "").strip()
                if ch_sum:
                    sliding_window.append(f"[{ch.title}] {ch_sum}")
                    if len(sliding_window) > 3:
                        sliding_window.pop(0)
            else:
                ch_result["importance_score"] = 0
                ch_result["importance_reason"] = ""

            chapter_results[idx] = ch_result
            
            # Incremental write
            if chapters_dir is not None:
                write_artifact(chapters_dir / f"{ch.chapter_id}.json", ch_result)

        except Exception as exc:
                _log.warning("Chapter %s failed: %s", ch.chapter_id, exc)
                failure_entry = {
                    "chapter_id": ch.chapter_id,
                    "title": ch.title,
                    "error": str(exc),
                }
                failures.append(failure_entry)
                ch_result = {
                    "chapter_id": ch.chapter_id,
                    "title": ch.title,
                    "chapter_summary": "",
                    "key_events": [],
                    "status": "error",
                    "importance_score": 0,
                    "importance_reason": "",
                }
                chapter_results[idx] = ch_result
                if chapters_dir is not None:
                    write_artifact(chapters_dir / f"{ch.chapter_id}.json", ch_result)
                if logger:
                    logger.log("standard_chapter_error", chapter_id=ch.chapter_id, error=str(exc))

    if logger and artifacts_dir is not None:
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
