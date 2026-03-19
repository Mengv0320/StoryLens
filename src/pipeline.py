from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

import time

from .alias_memory import CharacterAliasMemory
from .causal_engine import CausalEngine
from .chaptering import Chapter, compute_chapter_id, split_into_chapters
from .config import ModelConfig, Paths
from .episode_planner import build_episode_plan_entry, plan_episode_chunks
from .knowledge import KnowledgeManager
from .quality import QualityAssessor
from .runtime import RunLogger, RunPaths, StageCache, load_state_checkpoint, write_artifact, write_state_checkpoint
from .schema_validator import SchemaValidator
from .serialization import causal_analysis_from_dict, extraction_from_dict, genre_from_dict, normalized_events_from_dict, scene_split_from_dict, scored_events_from_dict
from .stages import AnthropicLLMClient, CausalAnalyzer, EpisodeBuilder, EventNormalizer, EventScorer, GenreClassifier, LLMClient, OpenAILLMClient, SceneExtractor, SceneSplitter
from .stats import PipelineStats

_log = logging.getLogger(__name__)


def probe_api_concurrency(client: LLMClient, max_probe: int = 8, ceiling: int = 12) -> int:
    """Auto-detect the max safe concurrency for the LLM API endpoint.

    Sends lightweight concurrent requests (genre classification on a tiny text)
    and ramps up concurrency until error rate exceeds threshold.

    Returns the highest concurrency level with 0% failure rate, minimum 1.
    """
    probe_text = "测试文本。少年觉醒血脉，踏上修仙之路。"
    best = 1

    for n in (2, 4, 6, 8, 10, 12):
        if n > ceiling or n > max_probe:
            break

        def _probe():
            try:
                client.complete_json(
                    f"Classify this text genre. Output JSON only: {{\"genre\": \"...\"}}\n\nText: {probe_text}",
                    max_tokens=128,
                )
                return True
            except Exception:
                return False

        successes = 0
        with ThreadPoolExecutor(max_workers=n) as pool:
            futs = [pool.submit(_probe) for _ in range(n)]
            for fut in as_completed(futs):
                if fut.result():
                    successes += 1

        fail_rate = 1.0 - (successes / n)
        _log.info(f"Concurrency probe: n={n}, success={successes}/{n}, fail_rate={fail_rate:.0%}")

        if fail_rate > 0.0:
            # Any failure means we've hit the limit
            break
        best = n

    _log.info(f"Auto-detected max concurrency: {best}")
    return best


def _build_client(
    api_key: str,
    model: str,
    base_url: str | None,
    stage: str,
    model_config: ModelConfig | None,
    use_anthropic: bool = False,
) -> LLMClient:
    """Build an LLMClient for a specific stage, respecting per-stage model config."""
    if model_config:
        resolved_model, resolved_base_url = model_config.resolve(stage, model, base_url)
    else:
        resolved_model, resolved_base_url = model, base_url
    if use_anthropic:
        return AnthropicLLMClient(api_key=api_key, model=resolved_model, base_url=resolved_base_url or "https://api.anthropic.com")
    return OpenAILLMClient(api_key=api_key, model=resolved_model, base_url=resolved_base_url)


class NovelPipeline:
    def __init__(
        self,
        client: LLMClient,
        paths: Paths | None = None,
        cache: StageCache | None = None,
        logger: RunLogger | None = None,
        artifacts_dir: Path | None = None,
        stats: PipelineStats | None = None,
        skip_quality: bool = False,
        clients_by_stage: dict[str, LLMClient] | None = None,
        max_workers: int = 4,
    ) -> None:
        self.paths = paths or Paths.discover()
        self.validator = SchemaValidator(self.paths.schemas_dir)
        self._default_client = client
        self._clients_by_stage = clients_by_stage or {}
        self._auto_probe = (max_workers == 0)
        self.max_workers = max(1, max_workers) if max_workers > 0 else 4  # temp default until probe

        self.classifier = GenreClassifier(self._client_for("genre"), self.paths, self.validator)
        self.scene_splitter = SceneSplitter(self._client_for("scene_split"), self.paths, self.validator)
        self.extractor = SceneExtractor(self._client_for("scene_extraction"), self.paths, self.validator)
        self.normalizer = EventNormalizer(self._client_for("normalized_events"), self.paths, self.validator)
        self.scorer = EventScorer(self._client_for("scores"), self.paths, self.validator)
        self.episode_builder = EpisodeBuilder(self._client_for("episode"), self.paths, self.validator)
        self.causal_analyzer = CausalAnalyzer(self._client_for("causal_analysis"), self.paths, self.validator)
        self.cache = cache
        self.logger = logger
        self.artifacts_dir = artifacts_dir
        self.alias_memory = CharacterAliasMemory()
        self.knowledge_manager = KnowledgeManager()
        self.causal_engine = CausalEngine(prompts_dir=self.paths.prompts_dir)
        self.stats = stats
        self.skip_quality = skip_quality

    def _client_for(self, stage: str) -> LLMClient:
        return self._clients_by_stage.get(stage, self._default_client)

    def _log(self, event: str, **fields: object) -> None:
        if self.logger:
            self.logger.log(event, **fields)

    def _record_stats(self, stage: str, duration: float, chapter_id: str = "", episode_id: str = "") -> None:
        if not self.stats:
            return
        client = self._client_for(stage)
        usage = getattr(client, "last_usage", None)
        if not usage:
            return
        self.stats.record_call(
            stage=stage,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            duration_seconds=duration,
            model=getattr(client, "model", ""),
            chapter_id=chapter_id,
            episode_id=episode_id,
        )

    def _cached(self, stage: str, payload: dict[str, object], producer, chapter_id: str = "", episode_id: str = ""):
        if self.cache:
            cached = self.cache.get(stage, payload)
            if cached is not None:
                self._log("cache_hit", stage=stage)
                return cached, True
        t0 = time.monotonic()
        result = producer()
        elapsed = time.monotonic() - t0
        self._record_stats(stage, elapsed, chapter_id=chapter_id, episode_id=episode_id)
        if self.cache:
            self.cache.set(stage, payload, result)
        self._log("stage_complete", stage=stage)
        return result, False

    def run_excerpt(self, text: str) -> dict[str, object]:
        return self.run_excerpt_with_context(text, chapter_id=None)

    def run_excerpt_with_context(self, text: str, chapter_id: str | None) -> dict[str, object]:
        self._log("excerpt_start", text_length=len(text))

        genre_payload, _ = self._cached(
            "genre",
            {"text": text},
            lambda: asdict(self.classifier.run(text)),
        )
        genre = genre_from_dict(genre_payload)

        scene_split_payload, _ = self._cached(
            "scene_split",
            {"text": text, "primary_genre": genre.primary_genre},
            lambda: asdict(self.scene_splitter.run(text)),
        )
        scene_split = scene_split_from_dict(scene_split_payload)

        extractions = []
        extraction_payloads = []
        if len(scene_split.scenes) <= 1:
            for scene in scene_split.scenes:
                payload, _ = self._cached(
                    "scene_extraction",
                    {"scene": asdict(scene), "primary_genre": genre.primary_genre},
                    lambda current_scene=scene: asdict(self.extractor.run(current_scene, genre_hint=genre.primary_genre)),
                )
                extraction_payloads.append(payload)
                extractions.append(extraction_from_dict(payload))
        else:
            def _extract_scene(idx: int, scene):
                payload, _ = self._cached(
                    "scene_extraction",
                    {"scene": asdict(scene), "primary_genre": genre.primary_genre},
                    lambda s=scene: asdict(self.extractor.run(s, genre_hint=genre.primary_genre)),
                )
                return idx, payload
            results: dict[int, object] = {}
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                futures = {pool.submit(_extract_scene, i, s): i for i, s in enumerate(scene_split.scenes)}
                for fut in as_completed(futures):
                    idx, payload = fut.result()
                    results[idx] = payload
            for i in range(len(scene_split.scenes)):
                p = results[i]
                extraction_payloads.append(p)
                extractions.append(extraction_from_dict(p))

        normalized_payload, _ = self._cached(
            "normalized_events",
            {"extractions": extraction_payloads, "chapter_id": chapter_id},
            lambda: asdict(self.normalizer.run(extractions)),
        )
        normalized_events = normalized_events_from_dict(normalized_payload)
        normalized_events = self.alias_memory.apply(normalized_events)
        normalized_payload = asdict(normalized_events)

        primary_genre = genre.primary_genre

        # Causal analysis: run LLM causal analyzer then apply via CausalEngine
        causal_payload, _ = self._cached(
            "causal_analysis",
            {"normalized_events": normalized_payload, "chapter_id": chapter_id},
            lambda: self.causal_analyzer.run(
                normalized_events,
                unresolved_foreshadowing=self.causal_engine.unresolved_foreshadowing_dicts(),
            ),
        )
        causal_result = self.causal_engine.process_llm_result(
            normalized_events.events, causal_payload, chapter_id=chapter_id or "",
        )
        normalized_payload = asdict(normalized_events)  # re-serialize after causal annotation

        scores_payload, _ = self._cached(
            "scores",
            {"normalized_events": normalized_payload, "chapter_id": chapter_id, "genre": primary_genre},
            lambda: [asdict(item) for item in self.scorer.run(normalized_events, genre=primary_genre)],
        )
        scored_events = scored_events_from_dict(scores_payload)

        episode_payload, _ = self._cached(
            "episode",
            {
                "normalized_events": normalized_payload,
                "scores": scores_payload,
                "chapter_id": chapter_id,
                "genre": primary_genre,
            },
            lambda: asdict(self.episode_builder.run(normalized_events, scored_events, genre=primary_genre)),
        )

        result = {
            "genre": asdict(genre),
            "scene_split": asdict(scene_split),
            "extractions": [asdict(item) for item in extractions],
            "normalized_events": asdict(normalized_events),
            "causal_analysis": asdict(causal_result),
            "scores": [asdict(item) for item in scored_events],
            "episode": episode_payload,
            "aliases": self.alias_memory.snapshot(),
        }
        if self.artifacts_dir:
            target = "last_excerpt.json" if chapter_id is None else f"{chapter_id}_excerpt.json"
            write_artifact(self.artifacts_dir / target, result)
        self._log("excerpt_complete", scenes=len(scene_split.scenes), events=len(normalized_events.events))
        return result

    def _run_phase_a(self, text: str, chapter_id: str) -> dict[str, object]:
        """Phase A: genre + scene_split (parallel) → scene_extraction → normalized_events"""
        # Genre and scene_split are independent — run in parallel
        with ThreadPoolExecutor(max_workers=2) as mini_pool:
            genre_fut = mini_pool.submit(
                lambda: self._cached("genre", {"text": text}, lambda: asdict(self.classifier.run(text)))[0]
            )
            scene_split_fut = mini_pool.submit(
                lambda: self._cached("scene_split", {"text": text}, lambda: asdict(self.scene_splitter.run(text)))[0]
            )
            genre_payload = genre_fut.result()
            scene_split_payload = scene_split_fut.result()

        genre = genre_from_dict(genre_payload)
        scene_split = scene_split_from_dict(scene_split_payload)

        extraction_payloads: list = []
        if len(scene_split.scenes) <= 1:
            for scene in scene_split.scenes:
                payload, _ = self._cached(
                    "scene_extraction",
                    {"scene": asdict(scene), "primary_genre": genre.primary_genre},
                    lambda s=scene: asdict(self.extractor.run(s, genre_hint=genre.primary_genre)),
                )
                extraction_payloads.append(payload)
        else:
            def _extract(idx: int, scene):
                payload, _ = self._cached(
                    "scene_extraction",
                    {"scene": asdict(scene), "primary_genre": genre.primary_genre},
                    lambda s=scene: asdict(self.extractor.run(s, genre_hint=genre.primary_genre)),
                )
                return idx, payload
            ordered: dict[int, object] = {}
            with ThreadPoolExecutor(max_workers=min(self.max_workers, len(scene_split.scenes))) as pool:
                futs = {pool.submit(_extract, i, s): i for i, s in enumerate(scene_split.scenes)}
                for fut in as_completed(futs):
                    idx, payload = fut.result()
                    ordered[idx] = payload
            extraction_payloads = [ordered[i] for i in range(len(scene_split.scenes))]
        extractions = [extraction_from_dict(p) for p in extraction_payloads]

        normalized_payload, _ = self._cached(
            "normalized_events",
            {"extractions": extraction_payloads, "chapter_id": chapter_id},
            lambda: asdict(self.normalizer.run(extractions)),
        )
        normalized_events = normalized_events_from_dict(normalized_payload)
        normalized_events = self.alias_memory.apply(normalized_events)

        return {
            "genre": genre_payload,
            "scene_split": scene_split_payload,
            "extraction_payloads": extraction_payloads,
            "extractions": [asdict(e) for e in extractions],
            "normalized_events": asdict(normalized_events),
        }

    def _run_phase_b_causal(self, phase_a: dict, chapter_id: str) -> dict[str, object]:
        """Phase B-1: causal analysis only (needs cross-chapter state, must be serial)"""
        normalized_events = normalized_events_from_dict(phase_a["normalized_events"])
        normalized_payload = asdict(normalized_events)
        genre = genre_from_dict(phase_a["genre"])

        causal_payload, _ = self._cached(
            "causal_analysis",
            {"normalized_events": normalized_payload, "chapter_id": chapter_id},
            lambda: self.causal_analyzer.run(
                normalized_events,
                unresolved_foreshadowing=self.causal_engine.unresolved_foreshadowing_dicts(),
            ),
        )
        causal_result = self.causal_engine.process_llm_result(
            normalized_events.events, causal_payload, chapter_id=chapter_id,
        )
        return {
            "normalized_events": normalized_events,
            "genre": genre,
            "causal_result": causal_result,
        }

    def _run_phase_b_score_episode(self, phase_a: dict, causal_out: dict, chapter_id: str) -> dict[str, object]:
        """Phase B-2: scores + episode (no cross-chapter deps, can overlap with next chapter's causal)"""
        normalized_events = causal_out["normalized_events"]
        genre = causal_out["genre"]
        causal_result = causal_out["causal_result"]
        primary_genre = genre.primary_genre
        normalized_payload = asdict(normalized_events)

        scores_payload, _ = self._cached(
            "scores",
            {"normalized_events": normalized_payload, "chapter_id": chapter_id, "genre": primary_genre},
            lambda: [asdict(item) for item in self.scorer.run(normalized_events, genre=primary_genre)],
        )
        scored_events = scored_events_from_dict(scores_payload)

        episode_payload, _ = self._cached(
            "episode",
            {"normalized_events": normalized_payload, "scores": scores_payload, "chapter_id": chapter_id, "genre": primary_genre},
            lambda: asdict(self.episode_builder.run(normalized_events, scored_events, genre=primary_genre)),
        )

        scene_split = scene_split_from_dict(phase_a["scene_split"])
        extractions = [extraction_from_dict(p) for p in phase_a["extraction_payloads"]]

        return {
            "genre": asdict(genre),
            "scene_split": asdict(scene_split),
            "extractions": [asdict(item) for item in extractions],
            "normalized_events": asdict(normalized_events),
            "causal_analysis": asdict(causal_result),
            "scores": [asdict(item) for item in scored_events],
            "episode": episode_payload,
            "aliases": self.alias_memory.snapshot(),
        }

    def _run_phase_b(self, phase_a: dict, chapter_id: str) -> dict[str, object]:
        """Phase B: causal → scores → episode (fallback single-call path)"""
        causal_out = self._run_phase_b_causal(phase_a, chapter_id)
        return self._run_phase_b_score_episode(phase_a, causal_out, chapter_id)

    def _finalize_book_result(
        self,
        chapter_results: list[dict[str, object]],
        chapters: list[Chapter],
        planned_chunks: list,
        failures: list[dict[str, object]],
        book_genre: str | None,
        extra_checkpoint_meta: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Shared episode processing + export + checkpoint logic for run_book / run_book_continue."""
        episodes: list[dict[str, object]] = []
        episode_plan: list[dict[str, object]] = []

        def _process_episode(chunk_plan):
            chunk = [item for item in chapter_results if item["chapter"]["chapter_id"] in chunk_plan.chapter_ids]
            if not chunk:
                return None, None
            chapter_ids = [item["chapter"]["chapter_id"] for item in chunk]
            episode_id = chunk_plan.episode_id
            extraction_payloads = [extraction for item in chunk for extraction in item["extractions"]]
            try:
                normalized_payload, _ = self._cached(
                    "book_normalized_events",
                    {"episode_id": episode_id, "chapter_ids": chapter_ids, "extractions": extraction_payloads},
                    lambda: asdict(
                        self.normalizer.run([extraction_from_dict(extraction) for extraction in extraction_payloads])
                    ),
                )
                normalized_events = normalized_events_from_dict(normalized_payload)
                normalized_events = self.alias_memory.apply(normalized_events)
                normalized_payload = asdict(normalized_events)
                scores_payload, _ = self._cached(
                    "book_scores",
                    {"episode_id": episode_id, "normalized_events": normalized_payload, "genre": book_genre},
                    lambda: [asdict(item) for item in self.scorer.run(normalized_events, genre=book_genre)],
                )
                scored_events = scored_events_from_dict(scores_payload)
                episode_payload, _ = self._cached(
                    "book_episode",
                    {"episode_id": episode_id, "normalized_events": normalized_payload, "scores": scores_payload, "genre": book_genre},
                    lambda: asdict(self.episode_builder.run(normalized_events, scored_events, genre=book_genre)),
                )
                episode_result = {
                    "episode_id": episode_id,
                    "chapter_ids": chapter_ids,
                    "chapter_titles": chunk_plan.chapter_titles,
                    "episode": episode_payload,
                    "normalized_events": normalized_payload,
                    "scores": scores_payload,
                }
                if chunk_plan.boundary is not None:
                    episode_result["boundary"] = asdict(chunk_plan.boundary)
                if self.artifacts_dir:
                    write_artifact(self.artifacts_dir / "episodes" / f"{episode_id}.json", episode_result)
                self._log("episode_complete", episode_id=episode_id, chapter_ids=chapter_ids)
                return episode_result, None
            except Exception as exc:
                failure = {
                    "episode_id": episode_id, "chapter_ids": chapter_ids,
                    "status": "failed", "error_type": type(exc).__name__, "error": str(exc),
                }
                if self.artifacts_dir:
                    write_artifact(self.artifacts_dir / "failures" / f"{episode_id}.json", failure)
                self._log("episode_failed", episode_id=episode_id, chapter_ids=chapter_ids,
                           error_type=type(exc).__name__, error=str(exc))
                return None, failure

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(planned_chunks) or 1)) as pool:
            futures = {pool.submit(_process_episode, cp): cp for cp in planned_chunks}
            for fut in as_completed(futures):
                ep_result, ep_failure = fut.result()
                if ep_result:
                    episodes.append(ep_result)
                    episode_plan.append(build_episode_plan_entry(ep_result))
                if ep_failure:
                    failures.append(ep_failure)

        result: dict[str, object] = {
            "chapters": chapter_results,
            "episodes": episodes,
            "episode_plan": episode_plan,
            "failures": failures,
            "aliases": self.alias_memory.snapshot(),
        }

        # Export knowledge layer
        try:
            knowledge_data = self.knowledge_manager.export_for_artifact()
            result["knowledge"] = knowledge_data
            if self.artifacts_dir:
                write_artifact(self.artifacts_dir / "knowledge" / "knowledge_layer.json", knowledge_data)
                write_artifact(
                    self.artifacts_dir / "knowledge" / "relationship_graph.json",
                    self.knowledge_manager.tracker.get_relationship_graph(),
                )
            self._log("knowledge_export_complete", characters=len(knowledge_data.get("characters", [])))
        except Exception as exc:
            self._log("knowledge_export_failed", error_type=type(exc).__name__, error=str(exc))

        # Export causal state
        try:
            causal_state = self.causal_engine.snapshot()
            result["causal_state"] = causal_state
            if self.artifacts_dir:
                write_artifact(self.artifacts_dir / "knowledge" / "causal_state.json", causal_state)
            self._log("causal_export_complete",
                       chains=len(causal_state.get("active_chains", [])),
                       unresolved=len(causal_state.get("unresolved_foreshadowing", [])))
        except Exception as exc:
            self._log("causal_export_failed", error_type=type(exc).__name__, error=str(exc))

        # Write state checkpoint for cross-run continuation
        try:
            run_dir = self.artifacts_dir.parent if self.artifacts_dir else None
            if run_dir:
                processed_ids = [cr["chapter"]["chapter_id"] for cr in chapter_results if cr.get("status") == "ok"]
                chapter_order = [ch.chapter_id for ch in chapters]
                meta = {
                    "genre": book_genre or "",
                    "total_chapters_processed": len(processed_ids),
                    "source_run_id": run_dir.name if run_dir else "",
                }
                if extra_checkpoint_meta:
                    meta.update(extra_checkpoint_meta)
                write_state_checkpoint(
                    run_dir=run_dir,
                    processed_chapters=processed_ids,
                    chapter_order=chapter_order,
                    knowledge_snapshot=self.knowledge_manager.full_snapshot(),
                    causal_snapshot=self.causal_engine.full_snapshot(),
                    alias_snapshot=self.alias_memory.snapshot(),
                    metadata=meta,
                )
                self._log("checkpoint_written", processed_chapters=len(processed_ids))
        except Exception as exc:
            self._log("checkpoint_write_failed", error_type=type(exc).__name__, error=str(exc))

        if self.artifacts_dir:
            write_artifact(self.artifacts_dir / "book_result.json", result)
            write_artifact(self.artifacts_dir / "aliases.json", self.alias_memory.snapshot())
            write_artifact(self.artifacts_dir / "episode_plan.json", episode_plan)

        return result

    # ------------------------------------------------------------------
    # Shared helpers (extracted from run_book / run_book_continue / run_book_resume)
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_book_genre(chapter_results: list[dict]) -> str | None:
        """Return the primary_genre from the first successful chapter, or None."""
        for cr in chapter_results:
            genre_data = cr.get("genre")
            if genre_data and isinstance(genre_data, dict):
                g = genre_data.get("primary_genre")
                if g:
                    return g
        return None

    def _collect_chapter_result(
        self,
        future_result,
        chapter: Chapter,
        chapter_results: list[dict[str, object]],
        failures: list[dict[str, object]],
    ) -> None:
        """Wait for a phase-B future and append the outcome to *chapter_results* or *failures*."""
        try:
            result = future_result.result()
            result["chapter"] = asdict(chapter)
            result["status"] = "ok"
            chapter_results.append(result)
            if self.artifacts_dir:
                write_artifact(self.artifacts_dir / "chapters" / f"{chapter.chapter_id}.json", result)
            try:
                ch_normalized = normalized_events_from_dict(result["normalized_events"])
                ch_scored = scored_events_from_dict(result["scores"])
                ch_genre = result.get("genre", {}).get("primary_genre", "")
                self.knowledge_manager.update_from_chapter(
                    chapter_id=chapter.chapter_id, normalized_events=ch_normalized,
                    scored_events=ch_scored, genre=ch_genre,
                )
            except Exception:
                pass
            self._log("chapter_complete", chapter_id=chapter.chapter_id)
        except Exception as exc:
            failure = {"chapter": asdict(chapter), "status": "failed", "error_type": type(exc).__name__, "error": str(exc)}
            failures.append(failure)
            if self.artifacts_dir:
                write_artifact(self.artifacts_dir / "failures" / f"{chapter.chapter_id}.json", failure)
            self._log("chapter_failed", chapter_id=chapter.chapter_id, error_type=type(exc).__name__, error=str(exc))

    def _run_chapters_pipelined(
        self,
        chapters: list[Chapter],
        chapter_results: list[dict[str, object]],
        failures: list[dict[str, object]],
    ) -> None:
        """Execute Phase A (parallel) + Phase B (pipelined causal -> scores/episode) for *chapters*.

        Results are appended in-place to *chapter_results* and *failures*.
        """
        # Phase A: parallel — genre + scene_split + extraction + normalize
        phase_a_results: dict[str, dict] = {}
        phase_a_failures: dict[str, Exception] = {}

        def _do_phase_a(chapter):
            self._log("chapter_start", chapter_id=chapter.chapter_id, title=chapter.title)
            return self._run_phase_a(chapter.text, chapter_id=chapter.chapter_id)

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(chapters))) as pool:
            future_map = {pool.submit(_do_phase_a, ch): ch for ch in chapters}
            for fut in as_completed(future_map):
                ch = future_map[fut]
                try:
                    phase_a_results[ch.chapter_id] = fut.result()
                except Exception as exc:
                    phase_a_failures[ch.chapter_id] = exc

        # Phase B: pipelined — causal is serial, scores+episode overlap with next chapter's causal
        from concurrent.futures import Future
        score_episode_pool = ThreadPoolExecutor(max_workers=1)
        pending_future: Future | None = None
        pending_chapter: Chapter | None = None

        def _finish_pending():
            nonlocal pending_future, pending_chapter
            if pending_future is None:
                return
            self._collect_chapter_result(pending_future, pending_chapter, chapter_results, failures)
            pending_future = None
            pending_chapter = None

        for chapter in chapters:
            if chapter.chapter_id in phase_a_failures:
                exc = phase_a_failures[chapter.chapter_id]
                failure = {"chapter": asdict(chapter), "status": "failed", "error_type": type(exc).__name__, "error": str(exc)}
                failures.append(failure)
                if self.artifacts_dir:
                    write_artifact(self.artifacts_dir / "failures" / f"{chapter.chapter_id}.json", failure)
                self._log("chapter_failed", chapter_id=chapter.chapter_id, error_type=type(exc).__name__, error=str(exc))
                continue
            try:
                phase_a = phase_a_results[chapter.chapter_id]
                causal_out = self._run_phase_b_causal(phase_a, chapter_id=chapter.chapter_id)
                _finish_pending()
                pending_chapter = chapter
                pending_future = score_episode_pool.submit(
                    self._run_phase_b_score_episode, phase_a, causal_out, chapter.chapter_id,
                )
            except Exception as exc:
                _finish_pending()
                failure = {"chapter": asdict(chapter), "status": "failed", "error_type": type(exc).__name__, "error": str(exc)}
                failures.append(failure)
                if self.artifacts_dir:
                    write_artifact(self.artifacts_dir / "failures" / f"{chapter.chapter_id}.json", failure)
                self._log("chapter_failed", chapter_id=chapter.chapter_id, error_type=type(exc).__name__, error=str(exc))
                continue

        _finish_pending()
        score_episode_pool.shutdown(wait=False)

    def _run_quality_and_save_stats(self, result: dict, chapter_results: list) -> None:
        """Run quality assessment and persist stats (shared tail logic)."""
        if not self.skip_quality and chapter_results:
            try:
                assessor = QualityAssessor()
                quality_report = assessor.run_all_checks(chapter_results)
                result["quality_report"] = asdict(quality_report)
                if self.artifacts_dir:
                    write_artifact(self.artifacts_dir / "quality_report.json", asdict(quality_report))
                self._log("quality_complete", score=quality_report.overall_score)
            except Exception as exc:
                self._log("quality_failed", error_type=type(exc).__name__, error=str(exc))

        if self.stats and self.artifacts_dir:
            self.stats.save(self.artifacts_dir / "stats.json")

    # ------------------------------------------------------------------
    # Book-level entry points
    # ------------------------------------------------------------------

    def run_book(self, text: str, chapters_per_episode: int = 5, split_strategy: str = "v2", stable_ids: bool = False) -> dict[str, object]:
        chapters = split_into_chapters(text, stable_ids=stable_ids)
        chapter_results: list[dict[str, object]] = []
        failures: list[dict[str, object]] = []

        # Auto-detect API concurrency if requested (max_workers=0 at init)
        if self._auto_probe:
            self._log("probe_start")
            probed = probe_api_concurrency(self._default_client, max_probe=12)
            self.max_workers = max(2, probed)
            self._log("probe_done", max_workers=self.max_workers)

        if self.artifacts_dir:
            write_artifact(self.artifacts_dir / "chapters_index.json", [asdict(chapter) for chapter in chapters])
        self._log("book_start", chapter_count=len(chapters), chapters_per_episode=chapters_per_episode)

        self._run_chapters_pipelined(chapters, chapter_results, failures)

        planned_chunks = plan_episode_chunks(chapter_results, target_size=chapters_per_episode, strategy=split_strategy)
        self._log("episode_plan_ready", planned_episode_count=len(planned_chunks))

        book_genre = self._detect_book_genre(chapter_results)

        result = self._finalize_book_result(
            chapter_results=chapter_results,
            chapters=chapters,
            planned_chunks=planned_chunks,
            failures=failures,
            book_genre=book_genre,
        )

        self._run_quality_and_save_stats(result, chapter_results)
        self._log("book_complete", episodes=len(result.get("episodes", [])))
        return result

    def run_book_continue(
        self,
        text: str,
        continue_from: Path,
        chapters_per_episode: int = 5,
        split_strategy: str = "v2",
    ) -> dict[str, object]:
        """Continue a book run from a previous run's checkpoint, processing only new chapters."""
        checkpoint = load_state_checkpoint(continue_from)
        if checkpoint is None:
            raise RuntimeError(f"No valid state checkpoint found in {continue_from}")

        # Restore cross-chapter state (all-or-nothing to avoid inconsistent state)
        try:
            self.knowledge_manager.restore(checkpoint["knowledge"])
            self.causal_engine.restore(checkpoint["causal"])
            self.alias_memory.restore(checkpoint["aliases"])
        except Exception as exc:
            # Roll back to fresh state on any restore failure
            self.knowledge_manager = KnowledgeManager()
            self.causal_engine = CausalEngine()
            self.alias_memory = CharacterAliasMemory()
            raise RuntimeError(f"Failed to restore checkpoint state: {exc}") from exc
        prev_genre = checkpoint.get("metadata", {}).get("genre", "")
        self._log("continue_state_restored",
                  processed_chapters=len(checkpoint["processed_chapters"]),
                  source=str(continue_from))

        # Split current text with stable IDs
        chapters = split_into_chapters(text, stable_ids=True)
        processed_set = set(checkpoint["processed_chapters"])
        new_chapters = [ch for ch in chapters if ch.chapter_id not in processed_set]
        old_chapters = [ch for ch in chapters if ch.chapter_id in processed_set]

        self._log("continue_start",
                  total_chapters=len(chapters),
                  new_chapters=len(new_chapters),
                  old_chapters=len(old_chapters))

        if self.artifacts_dir:
            write_artifact(self.artifacts_dir / "chapters_index.json", [asdict(ch) for ch in chapters])

        # Load old chapter results from previous run (direct path lookup: O(N))
        old_results: list[dict[str, object]] = []
        prev_chapters_dir = continue_from / "artifacts" / "chapters"
        if prev_chapters_dir.is_dir():
            for ch in old_chapters:
                path = prev_chapters_dir / f"{ch.chapter_id}.json"
                if path.exists():
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                        if data.get("status") == "ok":
                            old_results.append(data)
                    except (json.JSONDecodeError, OSError):
                        pass

        # If old results not found by stable ID, load all OK results from previous run
        if not old_results and old_chapters:
            self._log("continue_fallback_load", reason="stable_id_mismatch")
            prev_run_paths = RunPaths.from_run_dir(continue_from)
            old_results = prev_run_paths.load_chapter_results()

        # Process new chapters
        chapter_results: list[dict[str, object]] = list(old_results)
        failures: list[dict[str, object]] = []

        if new_chapters:
            # Auto-detect API concurrency if requested
            if self._auto_probe:
                self._log("probe_start")
                probed = probe_api_concurrency(self._default_client, max_probe=12)
                self.max_workers = max(2, probed)
                self._log("probe_done", max_workers=self.max_workers)

            self._run_chapters_pipelined(new_chapters, chapter_results, failures)

        # Sort all results by sequence_index
        def _seq_key(cr):
            ch_info = cr.get("chapter", {})
            return ch_info.get("sequence_index", 999)
        chapter_results.sort(key=_seq_key)

        # Full re-plan episodes across ALL chapters (old + new)
        planned_chunks = plan_episode_chunks(chapter_results, target_size=chapters_per_episode, strategy=split_strategy)
        self._log("episode_plan_ready", planned_episode_count=len(planned_chunks))

        book_genre = prev_genre or self._detect_book_genre(chapter_results)

        result = self._finalize_book_result(
            chapter_results=chapter_results,
            chapters=chapters,
            planned_chunks=planned_chunks,
            failures=failures,
            book_genre=book_genre,
            extra_checkpoint_meta={"continued_from": str(continue_from)},
        )

        self._run_quality_and_save_stats(result, chapter_results)
        self._log("continue_complete", episodes=len(result.get("episodes", [])), new_chapters=len(new_chapters))
        return result

    def run_book_resume(
        self,
        text: str,
        run_dir: Path,
        chapters_per_episode: int = 5,
        split_strategy: str = "v2",
    ) -> dict[str, object]:
        """Resume a book run, skipping already-processed chapters."""
        chapters = split_into_chapters(text)
        cached_chapter_ids = _load_cached_chapter_ids(run_dir)
        total = len(chapters)
        cached_count = sum(1 for ch in chapters if ch.chapter_id in cached_chapter_ids)
        print(f"Resuming: {cached_count}/{total} chapters already processed, continuing from where we left off.")
        self._log("resume_start", total=total, cached=cached_count)

        chapter_results: list[dict[str, object]] = []
        failures: list[dict[str, object]] = []

        chapters_dir = run_dir / "artifacts" / "chapters"
        for chapter in chapters:
            if chapter.chapter_id in cached_chapter_ids:
                cached_path = chapters_dir / f"{chapter.chapter_id}.json"
                if cached_path.exists():
                    try:
                        cached_result = json.loads(cached_path.read_text(encoding="utf-8"))
                        chapter_results.append(cached_result)
                        # Rebuild knowledge from cached chapter
                        try:
                            ch_ne = normalized_events_from_dict(cached_result["normalized_events"])
                            ch_se = scored_events_from_dict(cached_result["scores"])
                            ch_g = cached_result.get("genre", {}).get("primary_genre", "") if isinstance(cached_result.get("genre"), dict) else ""
                            self.knowledge_manager.update_from_chapter(
                                chapter_id=chapter.chapter_id,
                                normalized_events=ch_ne,
                                scored_events=ch_se,
                                genre=ch_g,
                            )
                        except Exception:
                            pass
                        # Rebuild causal engine state from cached chapter
                        try:
                            cached_causal = cached_result.get("causal_analysis")
                            if cached_causal and isinstance(cached_causal, dict):
                                ch_ne_for_causal = normalized_events_from_dict(cached_result["normalized_events"])
                                self.causal_engine.process_llm_result(
                                    ch_ne_for_causal.events, cached_causal, chapter_id=chapter.chapter_id,
                                )
                        except Exception:
                            pass
                        self._log("chapter_resumed", chapter_id=chapter.chapter_id)
                        continue
                    except (json.JSONDecodeError, OSError):
                        pass

            self._log("chapter_start", chapter_id=chapter.chapter_id, title=chapter.title)
            try:
                res = self.run_excerpt_with_context(chapter.text, chapter_id=chapter.chapter_id)
                res["chapter"] = asdict(chapter)
                res["status"] = "ok"
                chapter_results.append(res)
                if self.artifacts_dir:
                    write_artifact(self.artifacts_dir / "chapters" / f"{chapter.chapter_id}.json", res)
                # Update knowledge layer from chapter results
                try:
                    ch_normalized = normalized_events_from_dict(res["normalized_events"])
                    ch_scored = scored_events_from_dict(res["scores"])
                    ch_genre = res.get("genre", {}).get("primary_genre", "")
                    self.knowledge_manager.update_from_chapter(
                        chapter_id=chapter.chapter_id,
                        normalized_events=ch_normalized,
                        scored_events=ch_scored,
                        genre=ch_genre,
                    )
                except Exception:
                    pass  # knowledge update is non-critical
                self._log("chapter_complete", chapter_id=chapter.chapter_id)
            except Exception as exc:
                failure = {
                    "chapter": asdict(chapter),
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                failures.append(failure)
                if self.artifacts_dir:
                    write_artifact(self.artifacts_dir / "failures" / f"{chapter.chapter_id}.json", failure)
                self._log("chapter_failed", chapter_id=chapter.chapter_id, error=str(exc))
                continue

        if self.artifacts_dir:
            write_artifact(self.artifacts_dir / "chapters_index.json", [asdict(ch) for ch in chapters])

        planned_chunks = plan_episode_chunks(chapter_results, target_size=chapters_per_episode, strategy=split_strategy)

        book_genre = self._detect_book_genre(chapter_results)

        result = self._finalize_book_result(
            chapter_results=chapter_results,
            chapters=chapters,
            planned_chunks=planned_chunks,
            failures=failures,
            book_genre=book_genre,
        )

        self._run_quality_and_save_stats(result, chapter_results)
        self._log("book_resume_complete", episodes=len(result.get("episodes", [])))
        return result

    def run_standard_analysis(self, text: str) -> dict:
        """Run lightweight standard analysis mode."""
        from .standard_analysis import run_standard_analysis
        return run_standard_analysis(
            text=text,
            client=self._default_client,
            cache=self.cache,
            logger=self.logger,
            artifacts_dir=self.artifacts_dir,
            stats=self.stats,
            max_workers=self.max_workers,
        )


def _load_cached_chapter_ids(run_dir: Path) -> set[str]:
    """Detect completed chapters from a previous run directory."""
    cached_ids: set[str] = set()
    chapters_jsonl = run_dir / "chapters.jsonl"
    if chapters_jsonl.exists():
        try:
            for line in chapters_jsonl.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                if data.get("status") == "ok":
                    chapter_info = data.get("chapter", {})
                    cid = chapter_info.get("chapter_id", "")
                    if cid:
                        cached_ids.add(cid)
        except (json.JSONDecodeError, OSError):
            pass

    chapters_dir = run_dir / "artifacts" / "chapters"
    if chapters_dir.is_dir():
        for path in chapters_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("status") == "ok":
                    chapter_info = data.get("chapter", {})
                    cid = chapter_info.get("chapter_id", "")
                    if cid:
                        cached_ids.add(cid)
            except (json.JSONDecodeError, OSError):
                continue

    return cached_ids


def save_json(data: dict[str, object], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_jsonl(items: list[dict[str, object]], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(item, ensure_ascii=False) for item in items)
    path.write_text(content, encoding="utf-8")
