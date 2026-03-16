from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .alias_memory import CharacterAliasMemory
from .chaptering import Chapter, split_into_chapters
from .config import Paths
from .episode_planner import build_episode_plan_entry, plan_episode_chunks
from .runtime import RunLogger, StageCache, write_artifact
from .schema_validator import SchemaValidator
from .serialization import extraction_from_dict, genre_from_dict, normalized_events_from_dict, scene_split_from_dict, scored_events_from_dict
from .stages import EpisodeBuilder, EventNormalizer, EventScorer, GenreClassifier, LLMClient, SceneExtractor, SceneSplitter


class NovelPipeline:
    def __init__(
        self,
        client: LLMClient,
        paths: Paths | None = None,
        cache: StageCache | None = None,
        logger: RunLogger | None = None,
        artifacts_dir: Path | None = None,
    ) -> None:
        self.paths = paths or Paths.discover()
        self.validator = SchemaValidator(self.paths.schemas_dir)
        self.classifier = GenreClassifier(client, self.paths, self.validator)
        self.scene_splitter = SceneSplitter(client, self.paths, self.validator)
        self.extractor = SceneExtractor(client, self.paths, self.validator)
        self.normalizer = EventNormalizer(client, self.paths, self.validator)
        self.scorer = EventScorer(client, self.paths, self.validator)
        self.episode_builder = EpisodeBuilder(client, self.paths, self.validator)
        self.cache = cache
        self.logger = logger
        self.artifacts_dir = artifacts_dir
        self.alias_memory = CharacterAliasMemory()

    def _log(self, event: str, **fields: object) -> None:
        if self.logger:
            self.logger.log(event, **fields)

    def _cached(self, stage: str, payload: dict[str, object], producer):
        if self.cache:
            cached = self.cache.get(stage, payload)
            if cached is not None:
                self._log("cache_hit", stage=stage)
                return cached, True
        result = producer()
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
        for scene in scene_split.scenes:
            payload, _ = self._cached(
                "scene_extraction",
                {
                    "scene": asdict(scene),
                    "primary_genre": genre.primary_genre,
                },
                lambda current_scene=scene: asdict(self.extractor.run(current_scene, genre_hint=genre.primary_genre)),
            )
            extraction_payloads.append(payload)
            extractions.append(extraction_from_dict(payload))

        normalized_payload, _ = self._cached(
            "normalized_events",
            {"extractions": extraction_payloads, "chapter_id": chapter_id},
            lambda: asdict(self.normalizer.run(extractions)),
        )
        normalized_events = normalized_events_from_dict(normalized_payload)
        normalized_events = self.alias_memory.apply(normalized_events)
        normalized_payload = asdict(normalized_events)

        scores_payload, _ = self._cached(
            "scores",
            {"normalized_events": normalized_payload, "chapter_id": chapter_id},
            lambda: [asdict(item) for item in self.scorer.run(normalized_events)],
        )
        scored_events = scored_events_from_dict(scores_payload)

        episode_payload, _ = self._cached(
            "episode",
            {
                "normalized_events": normalized_payload,
                "scores": scores_payload,
                "chapter_id": chapter_id,
            },
            lambda: asdict(self.episode_builder.run(normalized_events, scored_events)),
        )

        result = {
            "genre": asdict(genre),
            "scene_split": asdict(scene_split),
            "extractions": [asdict(item) for item in extractions],
            "normalized_events": asdict(normalized_events),
            "scores": [asdict(item) for item in scored_events],
            "episode": episode_payload,
            "aliases": self.alias_memory.snapshot(),
        }
        if self.artifacts_dir:
            target = "last_excerpt.json" if chapter_id is None else f"{chapter_id}_excerpt.json"
            write_artifact(self.artifacts_dir / target, result)
        self._log("excerpt_complete", scenes=len(scene_split.scenes), events=len(normalized_events.events))
        return result

    def run_book(self, text: str, chapters_per_episode: int = 5) -> dict[str, object]:
        chapters = split_into_chapters(text)
        chapter_results: list[dict[str, object]] = []
        episodes: list[dict[str, object]] = []
        episode_plan: list[dict[str, object]] = []
        failures: list[dict[str, object]] = []
        if self.artifacts_dir:
            write_artifact(self.artifacts_dir / "chapters_index.json", [asdict(chapter) for chapter in chapters])
        self._log("book_start", chapter_count=len(chapters), chapters_per_episode=chapters_per_episode)

        for chapter in chapters:
            self._log("chapter_start", chapter_id=chapter.chapter_id, title=chapter.title)
            try:
                result = self.run_excerpt_with_context(chapter.text, chapter_id=chapter.chapter_id)
                result["chapter"] = asdict(chapter)
                result["status"] = "ok"
                chapter_results.append(result)
                if self.artifacts_dir:
                    write_artifact(self.artifacts_dir / "chapters" / f"{chapter.chapter_id}.json", result)
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
                self._log(
                    "chapter_failed",
                    chapter_id=chapter.chapter_id,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
                continue

        planned_chunks = plan_episode_chunks(chapter_results, target_size=chapters_per_episode)
        self._log("episode_plan_ready", planned_episode_count=len(planned_chunks))

        for chunk_plan in planned_chunks:
            chunk = [item for item in chapter_results if item["chapter"]["chapter_id"] in chunk_plan.chapter_ids]
            if not chunk:
                continue
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
                    {"episode_id": episode_id, "normalized_events": normalized_payload},
                    lambda: [asdict(item) for item in self.scorer.run(normalized_events)],
                )
                scored_events = scored_events_from_dict(scores_payload)
                episode_payload, _ = self._cached(
                    "book_episode",
                    {
                        "episode_id": episode_id,
                        "normalized_events": normalized_payload,
                        "scores": scores_payload,
                    },
                    lambda: asdict(self.episode_builder.run(normalized_events, scored_events)),
                )
                episode_result = {
                    "episode_id": episode_id,
                    "chapter_ids": chapter_ids,
                    "chapter_titles": chunk_plan.chapter_titles,
                    "episode": episode_payload,
                    "normalized_events": normalized_payload,
                    "scores": scores_payload,
                }
                episodes.append(episode_result)
                episode_plan.append(build_episode_plan_entry(episode_result))
                if self.artifacts_dir:
                    write_artifact(self.artifacts_dir / "episodes" / f"{episode_id}.json", episode_result)
                self._log("episode_complete", episode_id=episode_id, chapter_ids=chapter_ids)
            except Exception as exc:
                failure = {
                    "episode_id": episode_id,
                    "chapter_ids": chapter_ids,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                failures.append(failure)
                if self.artifacts_dir:
                    write_artifact(self.artifacts_dir / "failures" / f"{episode_id}.json", failure)
                self._log(
                    "episode_failed",
                    episode_id=episode_id,
                    chapter_ids=chapter_ids,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )

        result = {
            "chapters": chapter_results,
            "episodes": episodes,
            "episode_plan": episode_plan,
            "failures": failures,
            "aliases": self.alias_memory.snapshot(),
        }
        if self.artifacts_dir:
            write_artifact(self.artifacts_dir / "book_result.json", result)
            write_artifact(self.artifacts_dir / "aliases.json", self.alias_memory.snapshot())
            write_artifact(self.artifacts_dir / "episode_plan.json", episode_plan)
        self._log("book_complete", episodes=len(episodes))
        return result


def save_json(data: dict[str, object], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_jsonl(items: list[dict[str, object]], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(item, ensure_ascii=False) for item in items)
    path.write_text(content, encoding="utf-8")
