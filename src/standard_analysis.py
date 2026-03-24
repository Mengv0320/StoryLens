"""Standard analysis mode: Genre -> Chapter split -> Key event extraction (LLM) -> Rule scoring -> Output.

Standard analysis mode. Genre classification, chapter splitting, per-chapter key event extraction,
causal_analysis, and episode generation.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .chaptering import split_into_chapters
from .config import Paths, ModelConfig
from .models import ChapterKeyEvent, ChapterKeyEventSet, GenreClassification, JsonDict
from .prompt_loader import load_prompt, render_prompt
from .rule_scoring import score_chapter
from .runtime import RunLogger, StageCache, write_artifact
from .schema_validator import SchemaValidationError, SchemaValidator
from .stages import GenreClassifier, LLMClient
from .stats import PipelineStats
from .story_memory import (
    StoryMemory,
    format_memory_for_prompt,
    normalize_character_names,
    memory_content_hash,
)

_log = logging.getLogger(__name__)


from contextlib import contextmanager

@contextmanager
def _stage_model(client: LLMClient, model_config: "ModelConfig | None", stage: str, default_model: str):
    """Temporarily switch client model for a specific pipeline stage."""
    if model_config is None:
        yield client
        return
    stage_model, _ = model_config.resolve(stage, default_model)
    original_model = getattr(client, "model", None)
    if stage_model != default_model and hasattr(client, "model"):
        client.model = stage_model  # type: ignore[attr-defined]
        _log.info("Stage '%s' using model override: %s", stage, stage_model)
    try:
        yield client
    finally:
        if original_model is not None and hasattr(client, "model"):
            client.model = original_model  # type: ignore[attr-defined]


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

    def run(self, chapter_text: str, genre_hint: str = "", story_memory_text: str = "") -> ChapterKeyEventSet:
        prompt = self._build_prompt(chapter_text, genre_hint, story_memory_text)
        result = self._complete_validated(prompt, "chapter_key_events.schema.json")
        events = [ChapterKeyEvent(**e) for e in result.get("events", [])]
        return ChapterKeyEventSet(
            events=events,
            chapter_summary=result.get("chapter_summary", ""),
            filler_ratio=result.get("filler_ratio", 0.0),
            filler_type=result.get("filler_type", "none"),
        )

    def _build_prompt(self, chapter_text: str, genre_hint: str, story_memory_text: str = "") -> str:
        template = load_prompt(self.paths.prompts_dir / "chapter_key_events.md")
        hint_block = f"流派提示：{genre_hint}\n" if genre_hint else ""
        refinement_block = self._REFINEMENT_INSTRUCTIONS.get(self.refinement_intensity, "")
        return render_prompt(
            template,
            genre_hint=hint_block + refinement_block,
            story_memory=story_memory_text,
            text=chapter_text,
        )

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
    story_memory_text: str = "",
    memory_hash: str = "",
) -> dict[str, Any]:
    """Process a single chapter: cache check -> LLM extract -> return result dict."""
    text_hash = hashlib.sha256(chapter_text.encode()).hexdigest()[:32]
    cache_payload = {"chapter_text_hash": text_hash, "genre": genre_hint, "memory_hash": memory_hash}

    # Cache hit?
    if cache is not None:
        cached = cache.get("chapter_key_events", cache_payload)
        if cached is not None:
            if "raw_text" not in cached:
                cached["raw_text"] = chapter_text
            return cached

    # LLM call
    call_start = time.time()
    event_set = extractor.run(chapter_text, genre_hint=genre_hint, story_memory_text=story_memory_text)
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
        "filler_ratio": event_set.filler_ratio,
        "filler_type": event_set.filler_type,
    }

    # Write to cache
    if cache is not None:
        cache.set("chapter_key_events", cache_payload, result)

    return result


def _update_memory(
    memory: StoryMemory,
    chapter_result: dict[str, Any],
    client: LLMClient,
    paths: Paths,
    validator: SchemaValidator,
    stats: PipelineStats | None,
) -> StoryMemory:
    """Call LLM to incrementally update story memory after a chapter extraction."""
    template = load_prompt(paths.prompts_dir / "memory_update.md")
    prompt = render_prompt(
        template,
        current_memory=json.dumps(memory.to_dict(), ensure_ascii=False),
        chapter_id=chapter_result.get("chapter_id", ""),
        chapter_title=chapter_result.get("title", ""),
        chapter_summary=chapter_result.get("chapter_summary", ""),
        chapter_events=json.dumps(chapter_result.get("key_events", []), ensure_ascii=False),
        genre_hint="",
    )

    t0 = time.time()
    raw = client.complete_json(prompt, max_tokens=4096)
    elapsed = time.time() - t0

    # 验证（宽容模式：验证失败时返回原记忆）
    try:
        validator.validate("memory_update.schema.json", raw)
    except Exception as exc:
        _log.warning("Memory update validation failed for %s: %s",
                     chapter_result.get("chapter_id"), exc)
        memory.last_chapter_id = chapter_result.get("chapter_id", "")
        memory.last_chapter_title = chapter_result.get("title", "")
        memory.total_chapters_processed += 1
        return memory

    # 统计
    if stats:
        usage = getattr(client, "last_usage", None) or {}
        if isinstance(usage, dict):
            stats.record_call(
                stage="memory_update",
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                duration_seconds=elapsed,
                chapter_id=chapter_result.get("chapter_id", ""),
            )

    return StoryMemory.from_dict(raw)


def _update_memory_batch(
    memory: StoryMemory,
    batch_results: list[dict[str, Any]],
    client: LLMClient,
    paths: Paths,
    validator: SchemaValidator,
    stats: PipelineStats | None,
) -> StoryMemory:
    """Call LLM to update story memory after a batch of chapters (single LLM call)."""
    if not batch_results:
        return memory

    template = load_prompt(paths.prompts_dir / "memory_update.md")

    # 合并 batch 内所有章节信息
    chapter_ids = ", ".join(r.get("chapter_id", "") for r in batch_results)
    chapter_titles = " / ".join(r.get("title", "") for r in batch_results)
    summaries = "\n".join(
        f"- {r.get('chapter_id', '')}「{r.get('title', '')}」: {r.get('chapter_summary', '')}"
        for r in batch_results
    )
    all_events: list[dict[str, Any]] = []
    for r in batch_results:
        for ev in r.get("key_events", []):
            ev_copy = dict(ev)
            ev_copy["_from_chapter"] = r.get("chapter_id", "")
            all_events.append(ev_copy)

    prompt = render_prompt(
        template,
        current_memory=json.dumps(memory.to_dict(), ensure_ascii=False),
        chapter_id=chapter_ids,
        chapter_title=chapter_titles,
        chapter_summary=summaries,
        chapter_events=json.dumps(all_events, ensure_ascii=False),
        genre_hint="",
    )

    t0 = time.time()
    raw = client.complete_json(prompt, max_tokens=8192)
    elapsed = time.time() - t0

    try:
        validator.validate("memory_update.schema.json", raw)
    except Exception as exc:
        _log.warning("Batch memory update validation failed for %s: %s", chapter_ids, exc)
        memory.last_chapter_id = batch_results[-1].get("chapter_id", "")
        memory.last_chapter_title = batch_results[-1].get("title", "")
        memory.total_chapters_processed += len(batch_results)
        return memory

    if stats:
        usage = getattr(client, "last_usage", None) or {}
        if isinstance(usage, dict):
            stats.record_call(
                stage="memory_update",
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                duration_seconds=elapsed,
                chapter_id=chapter_ids,
            )

    return StoryMemory.from_dict(raw)


def run_standard_analysis(
    text: str,
    client: LLMClient,
    cache: StageCache | None = None,
    logger: RunLogger | None = None,
    artifacts_dir: Path | None = None,
    stats: PipelineStats | None = None,
    max_workers: int = 4,
    refinement_intensity: str = "standard",
    enable_story_memory: bool = False,
    initial_memory: StoryMemory | None = None,
    stop_event: "threading.Event | None" = None,
    model_config: "ModelConfig | None" = None,
) -> dict[str, Any]:
    """Run the standard analysis pipeline.

    Genre -> Chapter split -> Per-chapter key event extraction (LLM, fully concurrent)
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
    default_model = getattr(client, "model", "")
    with _stage_model(client, model_config, "genre", default_model) as genre_client:
        genre_classifier = GenreClassifier(genre_client, paths, validator)
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

    # 3. Key event extraction — apply per-stage model override
    _saved_extract_model = getattr(client, "model", None)
    if model_config:
        _ext_model, _ = model_config.resolve("scene_extraction", default_model)
        if _ext_model != default_model and hasattr(client, "model"):
            client.model = _ext_model
            _log.info("Extraction stage using model override: %s", _ext_model)

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

    memory: StoryMemory | None = None

    if enable_story_memory:
        # ========== 批量并行记忆分支 ==========
        # 每 BATCH_SIZE 章为一批，批内并行提取（共享冻结记忆），批间串行更新记忆
        memory = initial_memory or StoryMemory.empty()
        BATCH_SIZE = 10

        if artifacts_dir is not None:
            snapshots_dir = artifacts_dir / "memory_snapshots"
            snapshots_dir.mkdir(parents=True, exist_ok=True)
        else:
            snapshots_dir = None

        batches = [chapters[i:i + BATCH_SIZE] for i in range(0, len(chapters), BATCH_SIZE)]
        global_offset = 0

        for batch_num, batch in enumerate(batches):
            # Check for stop request
            if stop_event is not None and stop_event.is_set():
                _log.info("Pipeline stop requested, aborting after batch %d", batch_num)
                break
            # 冻结当前记忆快照，整个 batch 共享（只读）
            memory_text = format_memory_for_prompt(memory)
            mem_hash = memory_content_hash(memory)
            frozen_memory = memory

            def _extract_with_memory(args, _mt=memory_text, _mh=mem_hash, _fm=frozen_memory):
                """Batch-parallel extraction with frozen memory (thread-safe)."""
                g_idx, ch = args
                try:
                    ch_result = _process_chapter(
                        ch.chapter_id, ch.title, ch.text,
                        extractor, genre_hint, cache, stats,
                        story_memory_text=_mt,
                        memory_hash=_mh,
                    )
                    # 别名归一化（基于冻结记忆）
                    if _fm.characters:
                        ch_result["key_events"] = [
                            asdict(e) if not isinstance(e, dict) else e
                            for e in normalize_character_names(
                                ch_result.get("key_events", []), _fm,
                            )
                        ]
                    # 规则评分
                    if ch_result.get("status") == "ok":
                        event_objs = [ChapterKeyEvent(**e) for e in ch_result.get("key_events", [])]
                        event_set = ChapterKeyEventSet(
                            events=event_objs,
                            chapter_summary=ch_result.get("chapter_summary", ""),
                        )
                        score_out = score_chapter(event_set)
                        ch_result["importance_score"] = score_out["importance_score"]
                        ch_result["importance_reason"] = score_out["importance_reason"]
                    else:
                        ch_result["importance_score"] = 0
                        ch_result["importance_reason"] = ""
                    return g_idx, ch_result, None
                except Exception as exc:
                    _log.warning("Chapter %s failed: %s", ch.chapter_id, exc)
                    ch_result = {
                        "chapter_id": ch.chapter_id, "title": ch.title,
                        "chapter_summary": "", "key_events": [], "status": "error",
                        "importance_score": 0, "importance_reason": "",
                        "filler_ratio": 0.0, "filler_type": "none",
                    }
                    if logger:
                        logger.log("standard_chapter_error", chapter_id=ch.chapter_id, error=str(exc))
                    return g_idx, ch_result, {"chapter_id": ch.chapter_id, "title": ch.title, "error": str(exc)}

            # 并行提取 batch 内所有章节
            batch_ok_results: list[tuple[int, dict[str, Any]]] = []
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                tasks = [(global_offset + j, ch) for j, ch in enumerate(batch)]
                futures = {pool.submit(_extract_with_memory, t): t for t in tasks}
                for future in as_completed(futures):
                    g_idx, ch_result, failure_entry = future.result()
                    chapter_results[g_idx] = ch_result
                    if failure_entry:
                        failures.append(failure_entry)
                    if ch_result.get("status") == "ok":
                        batch_ok_results.append((g_idx, ch_result))
                    if chapters_dir is not None:
                        write_artifact(chapters_dir / f"{chapters[g_idx].chapter_id}.json", ch_result)

            # 按章节顺序排列，确保记忆更新的确定性
            batch_ok_results.sort(key=lambda x: x[0])

            # 一次 LLM 调用更新整个 batch 的记忆
            if batch_ok_results:
                try:
                    memory = _update_memory_batch(
                        memory, [r for _, r in batch_ok_results],
                        client, paths, validator, stats,
                    )
                except Exception as exc:
                    _log.warning("Batch memory update failed for batch %d: %s", batch_num + 1, exc)

            # 保存记忆快照（以 batch 最后一章命名）
            if snapshots_dir is not None:
                try:
                    memory.save(snapshots_dir / f"{batch[-1].chapter_id}_memory.json")
                except Exception as exc:
                    _log.warning("Memory snapshot save failed after batch %d: %s", batch_num + 1, exc)

            if logger:
                logger.log("standard_batch_done_with_memory",
                           batch_num=batch_num + 1, total_batches=len(batches),
                           chapters_in_batch=len(batch),
                           memory_chars=len(memory.characters))

            global_offset += len(batch)
    else:
        # ========== 原有并行分支（完全不变）==========
        def _extract_one(idx: int, ch):
            """Extract key events for a single chapter (thread-safe)."""
            try:
                ch_result = _process_chapter(
                    ch.chapter_id, ch.title, ch.text,
                    extractor, genre_hint, cache, stats,
                )
                if ch_result.get("status") == "ok":
                    event_objs = [ChapterKeyEvent(**e) for e in ch_result.get("key_events", [])]
                    event_set = ChapterKeyEventSet(
                        events=event_objs,
                        chapter_summary=ch_result.get("chapter_summary", ""),
                    )
                    score_out = score_chapter(event_set)
                    ch_result["importance_score"] = score_out["importance_score"]
                    ch_result["importance_reason"] = score_out["importance_reason"]
                else:
                    ch_result["importance_score"] = 0
                    ch_result["importance_reason"] = ""
                return idx, ch_result, None
            except Exception as exc:
                _log.warning("Chapter %s failed: %s", ch.chapter_id, exc)
                failure_entry = {"chapter_id": ch.chapter_id, "title": ch.title, "error": str(exc)}
                ch_result = {
                    "chapter_id": ch.chapter_id, "title": ch.title,
                    "chapter_summary": "", "key_events": [], "status": "error",
                    "importance_score": 0, "importance_reason": "",
                }
                if logger:
                    logger.log("standard_chapter_error", chapter_id=ch.chapter_id, error=str(exc))
                return idx, ch_result, failure_entry

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_extract_one, i, ch): i for i, ch in enumerate(chapters)}
            for future in as_completed(futures):
                idx, ch_result, failure_entry = future.result()
                chapter_results[idx] = ch_result
                if failure_entry:
                    failures.append(failure_entry)
                if chapters_dir is not None:
                    write_artifact(chapters_dir / f"{chapters[idx].chapter_id}.json", ch_result)
                # Check for stop request — cancel remaining futures
                if stop_event is not None and stop_event.is_set():
                    _log.info("Pipeline stop requested, cancelling remaining chapter extractions")
                    for f in futures:
                        f.cancel()
                    break

    # Restore model after extraction stage
    if _saved_extract_model is not None and hasattr(client, "model"):
        client.model = _saved_extract_model

    if logger and artifacts_dir is not None:
        logger.log("standard_artifacts_written", dir=str(artifacts_dir))

    # -- 记忆持久化 --
    if enable_story_memory and memory is not None and artifacts_dir is not None:
        knowledge_dir = artifacts_dir.parent / "knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        try:
            memory.save(knowledge_dir / "story_memory.json")
            if logger:
                logger.log("story_memory_saved",
                           path=str(knowledge_dir / "story_memory.json"),
                           characters=len(memory.characters),
                           relationships=len(memory.relationships))
        except Exception as exc:
            _log.warning("Failed to save final story memory: %s", exc)

    # 6. Build output
    output: dict[str, Any] = {
        "mode": "standard_analysis",
        "genre": asdict(genre_result),
        "chapters": chapter_results,
        "failures": failures,
        "stats": stats.to_dict() if stats else {},
    }
    if enable_story_memory and memory is not None:
        output["story_memory"] = memory.to_dict()

    if logger:
        logger.log(
            "standard_analysis_complete",
            total_chapters=len(chapters),
            ok_chapters=sum(1 for c in chapter_results if c.get("status") == "ok"),
            failed_chapters=len(failures),
        )

    return output
