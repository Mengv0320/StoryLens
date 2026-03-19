from __future__ import annotations

import json
import logging
import os
import re
import threading
import uuid
import copy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

from .config import Paths
from .pipeline import NovelPipeline, save_json, save_jsonl
from .runtime import RunLogger, RunPaths, StageCache, compute_book_fingerprint
from .stages import OpenAILLMClient, AnthropicLLMClient, MultiProviderClient
from .stats import PipelineStats
from .web_crawler import inspect_novel_book, crawl_novel_book, save_selected_chapters, select_chapters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_RELATION_MAP = {
    "enemy": "hostile", "rival": "hostile",
    "ally": "allied",
    "master_disciple": "mentor",
    "lover": "romantic",
    "family": "family",
    "neutral": "unknown",
}


def _map_relation_type(rt: str) -> str:
    return _RELATION_MAP.get(rt, "unknown")


def sanitize_name(value: str) -> str:
    safe = "".join(
        ch if (ch.isalnum() or ch in {"-", "_"}) else "_"
        for ch in value.strip()
    )
    # isalnum() already covers CJK characters in Python 3
    return safe.strip("_") or "novel"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snake_to_camel(key: str) -> str:
    """Convert snake_case to camelCase."""
    parts = key.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _camelize(obj):
    """Recursively convert all dict keys from snake_case to camelCase."""
    if isinstance(obj, dict):
        return {_snake_to_camel(k): _camelize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_camelize(item) for item in obj]
    return obj


# ---------------------------------------------------------------------------
# RunState / RunManager
# ---------------------------------------------------------------------------

@dataclass
class RunState:
    status: str = "idle"
    run_id: str = ""
    input_path: str = ""
    output_dir: str = ""
    model: str = ""
    project_name: str = ""
    started_at: str = ""
    updated_at: str = ""
    error: str = ""
    chapters_per_episode: int = 5
    split_strategy: str = "v2"
    skip_quality: bool = False
    use_cache: bool = True
    mode: str = "fast_scan"
    continue_from: str = ""


class RunManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = RunState()
        self._run_paths: RunPaths | None = None
        self._artifact_cache: dict[str, Any] = {}
        self._artifact_cache_mtime: dict[str, float] = {}
        self._restore_last_run()

    def _restore_last_run(self) -> None:
        """Scan data/runs/ and data/processed/ for the most recent completed run and restore state."""
        candidates = []
        # Scan data/runs/ subdirectories
        runs_dir = Path("data/runs")
        if runs_dir.is_dir():
            for d in runs_dir.iterdir():
                if not d.is_dir():
                    continue
                artifacts = d / "artifacts"
                if not artifacts.is_dir():
                    continue
                stats = artifacts / "run_stats.json"
                book = artifacts / "book_result.json"
                standard = d / "standard_output.json"
                if stats.exists() or book.exists() or standard.exists():
                    try:
                        mtime = max((f.stat().st_mtime for f in artifacts.iterdir() if f.is_file()), default=0)
                    except OSError:
                        mtime = 0
                    if standard.exists() and mtime == 0:
                        try:
                            mtime = standard.stat().st_mtime
                        except OSError:
                            pass
                    candidates.append((mtime, d))
        # Also check data/processed/ (CLI output directory)
        processed_dir = Path("data/processed")
        if processed_dir.is_dir():
            artifacts = processed_dir / "artifacts"
            if artifacts.is_dir():
                stats = artifacts / "run_stats.json"
                book = artifacts / "book_result.json"
                standard = processed_dir / "standard_output.json"
                if stats.exists() or book.exists() or standard.exists():
                    try:
                        mtime = max((f.stat().st_mtime for f in artifacts.iterdir() if f.is_file()), default=0)
                    except OSError:
                        mtime = 0
                    if standard.exists() and mtime == 0:
                        try:
                            mtime = standard.stat().st_mtime
                        except OSError:
                            pass
                    candidates.append((mtime, processed_dir))
        if not candidates:
            return
        candidates.sort(key=lambda x: x[0], reverse=True)
        latest_dir = candidates[0][1]
        artifacts = latest_dir / "artifacts"
        # Determine mode
        has_standard = (Path(latest_dir) / "standard_output.json").exists()
        is_scan = (artifacts / "run_stats.json").exists() and not (artifacts / "book_result.json").exists()
        if has_standard:
            mode = "standard_analysis"
        elif is_scan:
            mode = "fast_scan"
        else:
            mode = "deep_analysis"
        # Extract run_id from dir name (last segment after last _)
        dir_name = latest_dir.name
        run_id = dir_name.rsplit("_", 1)[-1] if "_" in dir_name else dir_name
        project_name = dir_name.rsplit("_", 1)[0] if "_" in dir_name else dir_name
        self._state = RunState(
            status="completed",
            run_id=run_id,
            output_dir=str(latest_dir.resolve()),
            project_name=project_name,
            mode=mode,
            model=os.environ.get("OPENAI_MODEL", ""),
        )
        self._run_paths = RunPaths.from_output(latest_dir)
        logger.info("Restored last run: %s (mode=%s, dir=%s)", run_id, mode, latest_dir)

    def _read_cached_artifact(self, path: str) -> Any:
        """读取产物文件，带 mtime 缓存。"""
        if not os.path.exists(path):
            return None
        try:
            mtime = os.path.getmtime(path)
            if path in self._artifact_cache and self._artifact_cache_mtime.get(path) == mtime:
                return self._artifact_cache[path]
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._artifact_cache[path] = data
            self._artifact_cache_mtime[path] = mtime
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read cached artifact %s: %s", path, exc)
            self._artifact_cache.pop(path, None)
            self._artifact_cache_mtime.pop(path, None)
            return None

    # -- public API --

    @staticmethod
    def _validate_continue_from(raw: Any) -> str:
        """Sanitize continueFrom path: must be under data/runs/ with no traversal."""
        value = str(raw or "").strip()
        if not value:
            return ""
        resolved = Path(value).resolve()
        allowed_base = Path("data/runs").resolve()
        if not str(resolved).startswith(str(allowed_base)):
            raise ValueError(f"continueFrom must be under data/runs/, got: {value}")
        if ".." in Path(value).parts:
            raise ValueError(f"continueFrom must not contain '..': {value}")
        return str(resolved)

    def start(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if self._state.status == "running":
                return {"error": "A pipeline run is already in progress"}
            run_id = uuid.uuid4().hex[:12]
            input_path = str(payload.get("inputPath", "")).strip()
            if not input_path:
                return {"error": "inputPath is required"}
            if not Path(input_path).exists():
                return {"error": f"Input file not found: {input_path}"}
            if not os.environ.get("OPENAI_API_KEY"):
                return {"error": "OPENAI_API_KEY environment variable is not set"}
            valid_modes = {"fast_scan", "deep_analysis", "excerpt", "book", "standard_analysis"}
            mode = payload.get("mode", "fast_scan")
            if mode not in valid_modes:
                return {"error": f"Invalid mode: {mode}. Must be one of {valid_modes}"}
            model = payload.get("model") or os.environ.get("OPENAI_MODEL", "gpt-4o")
            project_name = payload.get("projectName", "") or Path(input_path).stem
            output_base = payload.get("outputDir") or "data/runs"
            output_dir = str(Path(output_base).resolve() / f"{sanitize_name(project_name)}_{run_id}")
            self._state = RunState(
                status="running",
                run_id=run_id,
                input_path=input_path,
                output_dir=output_dir,
                model=model,
                project_name=project_name,
                started_at=_utc_now(),
                updated_at=_utc_now(),
                chapters_per_episode=int(payload.get("chaptersPerEpisode", 5)),
                split_strategy=payload.get("splitStrategy", "v2"),
                skip_quality=bool(payload.get("skipQuality", False)),
                use_cache=bool(payload.get("useCache", True)),
                mode=mode,
                continue_from=self._validate_continue_from(payload.get("continueFrom", "")),
            )
            self._run_paths = RunPaths.from_output(Path(output_dir))
            self._run_paths.ensure()
        logger.info("Pipeline start: run_id=%s mode=%s model=%s project=%s", run_id, mode, model, project_name)
        t = threading.Thread(target=self._run_pipeline, daemon=True)
        t.start()
        return {"runId": run_id, "status": "running", "outputDir": output_dir}

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            st = copy.copy(self._state)
            rp = self._run_paths
        base = {
            "status": st.status,
            "runId": st.run_id,
            "mode": st.mode,
            "model": st.model,
            "projectName": st.project_name,
            "outputDir": st.output_dir,
            "startedAt": st.started_at,
            "updatedAt": st.updated_at,
            "error": st.error,
        }
        if rp and st.status in ("running", "completed", "failed"):
            base["progress"] = self._read_progress(rp)
        else:
            base["progress"] = {
                "currentStage": "", "currentChapterLabel": "",
                "completedChapters": 0, "totalChapters": 0,
                "cacheHits": 0, "failedCount": 0,
            }
        return base

    @property
    def run_paths(self) -> RunPaths | None:
        with self._lock:
            return self._run_paths

    @property
    def state(self) -> RunState:
        with self._lock:
            return copy.copy(self._state)

    # -- pipeline thread --

    def _run_pipeline(self) -> None:
        try:
            with self._lock:
                st = self._state
                rp = self._run_paths
            assert rp is not None
            text = Path(st.input_path).read_text(encoding="utf-8")
            api_key = os.environ.get("OPENAI_API_KEY", "")
            base_url = os.environ.get("OPENAI_BASE_URL")
            api_type = os.environ.get("OPENAI_TYPE", "openai")
            if api_type == "anthropic":
                primary = AnthropicLLMClient(api_key=api_key, model=st.model, base_url=base_url or "")
            else:
                primary = OpenAILLMClient(api_key=api_key, model=st.model, base_url=base_url)
            # Build multi-provider client if secondary endpoint is configured
            extra_key = os.environ.get("OPENAI_API_KEY_2", "")
            extra_url = os.environ.get("OPENAI_BASE_URL_2", "")
            extra_model = os.environ.get("OPENAI_MODEL_2", "")
            extra_type = os.environ.get("OPENAI_TYPE_2", "openai")
            extra_sanitize = os.environ.get("OPENAI_SANITIZE_2", "").lower() in ("1", "true", "yes")
            if extra_key and extra_url and extra_model:
                if extra_type == "anthropic":
                    secondary = AnthropicLLMClient(api_key=extra_key, model=extra_model, base_url=extra_url)
                else:
                    secondary = OpenAILLMClient(api_key=extra_key, model=extra_model, base_url=extra_url)
                client = MultiProviderClient([(primary, False), (secondary, extra_sanitize)])
            else:
                client = primary

            # --- fast_scan mode ---
            if st.mode == "fast_scan":
                from .fast_scan import run_fast_scan
                book_fp = compute_book_fingerprint(text)
                base_cache = Path(st.output_dir).parent.parent / "cache"
                cache = StageCache.for_book(base_cache, book_fp, st.model) if st.use_cache else None
                run_log = RunLogger(rp.logs_dir / "run.jsonl")
                run_fast_scan(
                    text=text,
                    output_dir=st.output_dir,
                    client=client,
                    project_name=st.project_name,
                    cache=cache,
                    run_logger=run_log,
                )
                with self._lock:
                    self._state.status = "completed"
                    self._state.updated_at = _utc_now()
                logger.info("Fast scan completed: run_id=%s output=%s", st.run_id, st.output_dir)
                return

            # --- standard_analysis mode ---
            if st.mode == "standard_analysis":
                from .standard_analysis import run_standard_analysis
                book_fp = compute_book_fingerprint(text)
                base_cache = Path(st.output_dir).parent.parent / "cache"
                cache = StageCache.for_book(base_cache, book_fp, st.model) if st.use_cache else None
                run_log = RunLogger(rp.logs_dir / "run.jsonl")
                sa_stats = PipelineStats()
                result = run_standard_analysis(
                    text=text,
                    client=client,
                    cache=cache,
                    logger=run_log,
                    artifacts_dir=Path(st.output_dir) / "artifacts",
                    stats=sa_stats,
                )
                save_json(result, Path(st.output_dir) / "standard_output.json")
                with self._lock:
                    self._state.status = "completed"
                    self._state.updated_at = _utc_now()
                logger.info("Standard analysis completed: run_id=%s output=%s", st.run_id, st.output_dir)
                return

            # --- continue-from mode (incremental) ---
            book_fp = compute_book_fingerprint(text)
            base_cache = Path(st.output_dir).parent.parent / "cache"
            run_log = RunLogger(rp.logs_dir / "run.jsonl")
            stats = PipelineStats()
            if st.continue_from:
                continue_dir = Path(st.continue_from)
                if not continue_dir.is_dir():
                    raise RuntimeError(f"continue_from directory does not exist: {continue_dir}")
                # Use project-level cache for cross-run sharing
                cache = StageCache.for_project(base_cache, st.project_name, st.model) if st.use_cache else None
                pipeline = NovelPipeline(
                    client=client,
                    paths=Paths.discover(),
                    cache=cache,
                    logger=run_log,
                    artifacts_dir=rp.artifacts_dir,
                    stats=stats,
                    skip_quality=st.skip_quality,
                    max_workers=int(os.environ.get("PIPELINE_MAX_WORKERS", "4")),
                )
                result = pipeline.run_book_continue(
                    text,
                    continue_from=continue_dir,
                    chapters_per_episode=st.chapters_per_episode,
                    split_strategy=st.split_strategy,
                )
                save_json(result, Path(st.output_dir) / "book_result.json")
                chapters = result.get("chapters", [])
                if isinstance(chapters, list):
                    save_jsonl(chapters, Path(st.output_dir) / "chapters.jsonl")
                save_jsonl(result.get("episodes", []), Path(st.output_dir) / "episodes.jsonl")
                save_jsonl(result.get("episode_plan", []), Path(st.output_dir) / "episode_plan.jsonl")
                save_jsonl(result.get("failures", []), Path(st.output_dir) / "failures.jsonl")
                with self._lock:
                    self._state.status = "completed"
                    self._state.updated_at = _utc_now()
                logger.info("Continue-from completed: run_id=%s output=%s", st.run_id, st.output_dir)
                return

            # --- deep_analysis (original book pipeline) ---
            cache = StageCache.for_book(base_cache, book_fp, st.model) if st.use_cache else None
            pipeline = NovelPipeline(
                client=client,
                paths=Paths.discover(),
                cache=cache,
                logger=run_log,
                artifacts_dir=rp.artifacts_dir,
                stats=stats,
                skip_quality=st.skip_quality,
                max_workers=int(os.environ.get("PIPELINE_MAX_WORKERS", "4")),
            )
            result = pipeline.run_book(
                text,
                chapters_per_episode=st.chapters_per_episode,
                split_strategy=st.split_strategy,
            )
            save_json(result, Path(st.output_dir) / "book_result.json")
            chapters = result.get("chapters", [])
            if isinstance(chapters, list):
                save_jsonl(chapters, Path(st.output_dir) / "chapters.jsonl")
            save_jsonl(result.get("episodes", []), Path(st.output_dir) / "episodes.jsonl")
            save_jsonl(result.get("failures", []), Path(st.output_dir) / "failures.jsonl")
            with self._lock:
                self._state.status = "completed"
                self._state.updated_at = _utc_now()
            logger.info("Pipeline completed: run_id=%s output=%s", st.run_id, st.output_dir)
        except Exception as exc:
            logger.exception("Pipeline failed: run_id=%s error=%s", st.run_id, exc)
            with self._lock:
                self._state.status = "failed"
                self._state.error = str(exc)
                self._state.updated_at = _utc_now()

    # -- progress from filesystem --

    def _read_progress(self, rp: RunPaths) -> dict[str, Any]:
        completed_chapters = 0
        total_chapters = 0
        current_stage = ""
        current_chapter = ""
        failed_count = 0
        cache_hits = 0
        try:
            idx_path = rp.artifacts_dir / "chapters_index.json"
            if idx_path.exists():
                total_chapters = len(json.loads(idx_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
        chapters_dir = rp.artifacts_dir / "chapters"
        if chapters_dir.is_dir():
            for p in chapters_dir.glob("*.json"):
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                    if d.get("status") == "ok":
                        completed_chapters += 1
                except (json.JSONDecodeError, OSError):
                    pass
        failures_dir = rp.artifacts_dir / "failures"
        if failures_dir.is_dir():
            failed_count = sum(1 for _ in failures_dir.glob("*.json"))
        log_path = rp.logs_dir / "run.jsonl"
        if log_path.exists():
            try:
                # Only read the tail of the log to avoid high memory usage on large files
                _TAIL_BYTES = 65536  # 64KB
                with open(log_path, "r", encoding="utf-8") as _lf:
                    _lf.seek(0, 2)  # seek to end
                    _fsize = _lf.tell()
                    _lf.seek(max(0, _fsize - _TAIL_BYTES))
                    if _fsize > _TAIL_BYTES:
                        _lf.readline()  # discard partial first line
                    _tail_text = _lf.read()
                lines = _tail_text.strip().splitlines()
                # Find current stage/chapter from most recent log entries
                for line in reversed(lines[-50:]):
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ev = rec.get("event", "")
                    if not current_stage and rec.get("stage"):
                        current_stage = rec["stage"]
                    if not current_chapter and rec.get("chapter_id"):
                        current_chapter = rec["chapter_id"]
                    if current_stage and current_chapter:
                        break
                # Count cache_hits in tail portion
                cache_hits = sum(1 for ln in lines if '"cache_hit"' in ln)
            except OSError:
                pass
        return {
            "currentStage": current_stage,
            "currentChapterLabel": current_chapter,
            "completedChapters": completed_chapters,
            "totalChapters": total_chapters,
            "cacheHits": cache_hits,
            "failedCount": failed_count,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_run_manager = RunManager()


# ---------------------------------------------------------------------------
# Data readers (read from artifacts on disk)
# ---------------------------------------------------------------------------

def _load_artifact(rp: RunPaths, *parts: str) -> Any:
    path = rp.artifacts_dir.joinpath(*parts)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _read_summary(mgr: RunManager) -> dict[str, Any]:
    st = mgr.state
    rp = mgr.run_paths
    chapter_count = 0
    scene_count = 0
    event_count = 0
    character_count = 0
    episode_count = 0
    failure_count = 0
    if rp:
        idx = _load_artifact(rp, "chapters_index.json")
        if isinstance(idx, list):
            chapter_count = len(idx)
        chapters_dir = rp.artifacts_dir / "chapters"
        if chapters_dir.is_dir():
            for p in chapters_dir.glob("*.json"):
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                    if d.get("status") != "ok":
                        continue
                    ss = d.get("scene_split", {})
                    scene_count += len(ss.get("scenes", []))
                    ne = d.get("normalized_events", {})
                    event_count += len(ne.get("events", []))
                except (json.JSONDecodeError, OSError):
                    pass
        episodes_dir = rp.artifacts_dir / "episodes"
        if episodes_dir.is_dir():
            episode_count = sum(1 for _ in episodes_dir.glob("*.json"))
        failures_dir = rp.artifacts_dir / "failures"
        if failures_dir.is_dir():
            failure_count = sum(1 for _ in failures_dir.glob("*.json"))
        kl = _load_artifact(rp, "knowledge", "knowledge_layer.json")
        if isinstance(kl, dict):
            character_count = len(kl.get("characters", []))
    return {
        "runId": st.run_id,
        "projectName": st.project_name,
        "inputName": Path(st.input_path).name if st.input_path else "",
        "model": st.model,
        "status": st.status,
        "chapterCount": chapter_count,
        "sceneCount": scene_count,
        "eventCount": event_count,
        "characterCount": character_count,
        "episodeCount": episode_count,
        "failureCount": failure_count,
        "outputDir": st.output_dir,
        "startedAt": st.started_at,
        "updatedAt": st.updated_at,
    }


def _read_episodes(mgr: RunManager) -> list[dict[str, Any]]:
    rp = mgr.run_paths
    if not rp:
        return []
    episodes_dir = rp.artifacts_dir / "episodes"
    if not episodes_dir.is_dir():
        return []
    items: list[dict[str, Any]] = []
    paths = sorted(episodes_dir.glob("*.json"))
    for i, p in enumerate(paths):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        ep = d.get("episode", {})
        titles = d.get("chapter_titles", [])
        range_label = ""
        if titles:
            range_label = titles[0] if len(titles) == 1 else f"{titles[0]} ~ {titles[-1]}"
        status = "completed"
        if d.get("status") == "failed":
            status = "failed"
        items.append({
            "id": d.get("episode_id", p.stem),
            "indexLabel": f"EP{i+1:02d}",
            "title": ep.get("title", ""),
            "chapterRangeLabel": range_label,
            "status": status,
        })
    return items


def _read_episode_detail(mgr: RunManager, episode_id: str) -> dict[str, Any] | None:
    rp = mgr.run_paths
    if not rp:
        return None
    path = rp.artifacts_dir / "episodes" / f"{episode_id}.json"
    if not path.exists():
        return None
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    ep = d.get("episode", {})
    titles = d.get("chapter_titles", [])
    chapter_ids = d.get("chapter_ids", [])
    range_label = ""
    if titles:
        range_label = titles[0] if len(titles) == 1 else f"{titles[0]} ~ {titles[-1]}"
    ne = d.get("normalized_events", {})
    event_count = len(ne.get("events", [])) if isinstance(ne, dict) else 0
    characters_in_events: set[str] = set()
    for ev in ne.get("events", []) if isinstance(ne, dict) else []:
        for c in ev.get("characters", []):
            characters_in_events.add(c)
    return {
        "id": d.get("episode_id", episode_id),
        "title": ep.get("title", ""),
        "chapterIds": chapter_ids,
        "chapterTitles": titles,
        "chapterRangeLabel": range_label,
        "coreTheme": ep.get("core_theme", ""),
        "hook": ep.get("hook", ""),
        "mainConflict": ep.get("main_conflict", ""),
        "keyEvents": ep.get("key_events", []),
        "climax": ep.get("climax", ""),
        "endingHook": ep.get("ending_hook", ""),
        "summary": ep.get("episode_summary", ""),
        "characterIds": sorted(characters_in_events),
        "eventCount": event_count,
    }


def _read_episode_plan(mgr: RunManager) -> list[dict[str, Any]]:
    rp = mgr.run_paths
    if not rp:
        return []
    data = _load_artifact(rp, "episode_plan.json")
    if not isinstance(data, list):
        return []
    result: list[dict[str, Any]] = []
    for item in data:
        titles = item.get("chapter_titles", [])
        range_label = ""
        if titles:
            range_label = titles[0] if len(titles) == 1 else f"{titles[0]} ~ {titles[-1]}"
        result.append({
            "id": item.get("episode_id", ""),
            "title": item.get("title", ""),
            "chapterIds": item.get("chapter_ids", []),
            "chapterRangeLabel": range_label,
            "coreTheme": item.get("core_theme", ""),
            "mainConflict": item.get("main_conflict", ""),
            "climax": item.get("climax", ""),
            "endingHook": item.get("ending_hook", ""),
        })
    return result


def _read_characters(mgr: RunManager) -> list[dict[str, Any]]:
    rp = mgr.run_paths
    if not rp:
        return []
    kl = _load_artifact(rp, "knowledge", "knowledge_layer.json")
    if not isinstance(kl, dict):
        return []
    characters = kl.get("characters", [])
    event_counts: dict[str, int] = {}
    latest_chapter: dict[str, str] = {}
    chapters_dir = rp.artifacts_dir / "chapters"
    if chapters_dir.is_dir():
        for p in sorted(chapters_dir.glob("*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                if d.get("status") != "ok":
                    continue
                ch_id = d.get("chapter", {}).get("chapter_id", "")
                ne = d.get("normalized_events", {})
                for ev in ne.get("events", []) if isinstance(ne, dict) else []:
                    for c in ev.get("characters", []):
                        event_counts[c] = event_counts.get(c, 0) + 1
                        latest_chapter[c] = ch_id
            except (json.JSONDecodeError, OSError):
                pass
    items: list[dict[str, Any]] = []
    for ch in characters:
        name = ch.get("canonical_name", "")
        cid = ch.get("character_id", "")
        aliases = ch.get("aliases", [])
        faction = ch.get("stance", "") or None
        items.append({
            "id": cid,
            "name": name,
            "faction": faction,
            "aliasCount": len(aliases),
            "eventCount": event_counts.get(name, 0),
            "latestChapterLabel": latest_chapter.get(name, ""),
        })
    return items


def _read_character_detail(mgr: RunManager, char_id: str) -> dict[str, Any] | None:
    rp = mgr.run_paths
    if not rp:
        return None
    kl = _load_artifact(rp, "knowledge", "knowledge_layer.json")
    if not isinstance(kl, dict):
        return None
    characters = kl.get("characters", [])
    card: dict[str, Any] | None = None
    for ch in characters:
        if ch.get("character_id") == char_id:
            card = ch
            break
    if not card:
        return None
    name = card.get("canonical_name", "")
    recent_events: list[str] = []
    chapters_dir = rp.artifacts_dir / "chapters"
    if chapters_dir.is_dir():
        for p in sorted(chapters_dir.glob("*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                if d.get("status") != "ok":
                    continue
                ne = d.get("normalized_events", {})
                for ev in ne.get("events", []) if isinstance(ne, dict) else []:
                    if name in ev.get("characters", []):
                        recent_events.append(ev.get("title", ev.get("description", "")))
            except (json.JSONDecodeError, OSError):
                pass
    rels: list[dict[str, Any]] = []
    for r in card.get("relationships", []):
        rels.append({
            "targetName": r.get("target_character", ""),
            "relationType": _map_relation_type(r.get("relation_type", "")),
            "note": r.get("description", ""),
        })
    return {
        "id": char_id,
        "name": name,
        "aliases": card.get("aliases", []),
        "identity": card.get("identity", ""),
        "faction": card.get("stance", ""),
        "currentGoal": card.get("recent_goals", [""])[0] if card.get("recent_goals") else "",
        "recentEvents": recent_events[-20:],
        "relationships": rels,
    }


def _read_timeline(mgr: RunManager) -> list[dict[str, Any]]:
    rp = mgr.run_paths
    if not rp:
        return []
    kl = _load_artifact(rp, "knowledge", "knowledge_layer.json")
    if not isinstance(kl, dict):
        return []
    timeline = kl.get("timeline", {})
    events = timeline.get("main_plot_events", []) if isinstance(timeline, dict) else []
    items: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        items.append({
            "id": ev.get("event_id", f"te_{i}"),
            "title": ev.get("description", ""),
            "chapterRangeLabel": ev.get("chapter", ""),
            "eventType": "plot",
            "eventGroup": ev.get("plot_significance", ""),
            "importance": i + 1,
            "characters": ev.get("characters_involved", []),
            "summary": ev.get("description", ""),
        })
    return items


def _read_exports(mgr: RunManager) -> list[dict[str, Any]]:
    st = mgr.state
    rp = mgr.run_paths
    if not rp:
        return []

    # fast_scan mode: show scan artifacts
    if st.mode == "fast_scan":
        artifacts_dir = Path(st.output_dir) / "artifacts" if st.output_dir else None
        scan_files = [
            ("book_overview", "book_overview.json", "json", "全书总览"),
            ("segments", "segments.json", "json", "分段摘要"),
            ("segments_meta", "segments_meta.json", "json", "分段元数据（章节列表/候选）"),
            ("key_chapters", "key_chapters.json", "json", "关键章节精摘要"),
            ("reading_guide", "reading_guide.json", "json", "阅读指南"),
            ("chapter_index", "chapter_index.json", "json", "章节索引"),
            ("run_stats", "run_stats.json", "json", "运行统计"),
        ]
        items: list[dict[str, Any]] = []
        for file_id, rel_path, fmt, desc in scan_files:
            full = artifacts_dir / rel_path if artifacts_dir else Path(rel_path)
            items.append({
                "id": file_id,
                "label": desc,
                "format": fmt,
                "path": str(full),
                "exists": full.exists() if artifacts_dir else False,
                "description": desc,
            })
        return items

    # deep_analysis mode: show pipeline artifacts
    known_files = [
        ("book_result", "book_result.json", "json", "Complete pipeline result"),
        ("episode_plan", "episode_plan.json", "json", "Episode plan"),
        ("aliases", "aliases.json", "json", "Character alias mappings"),
        ("quality_report", "quality_report.json", "json", "Quality assessment report"),
        ("stats", "stats.json", "json", "Pipeline statistics and cost"),
        ("knowledge_layer", "knowledge/knowledge_layer.json", "json", "Knowledge layer (characters, factions, timeline)"),
        ("relationship_graph", "knowledge/relationship_graph.json", "json", "Character relationship graph"),
        ("causal_state", "knowledge/causal_state.json", "json", "Causal chains and foreshadowing"),
    ]
    items: list[dict[str, Any]] = []
    for file_id, rel_path, fmt, desc in known_files:
        full = rp.artifacts_dir / rel_path
        items.append({
            "id": file_id,
            "label": file_id.replace("_", " ").title(),
            "format": fmt,
            "path": str(full),
            "exists": full.exists(),
            "description": desc,
        })
    # Also check for chapters.jsonl in output_dir
    st = mgr.state
    chapters_jsonl = Path(st.output_dir) / "chapters.jsonl"
    items.append({
        "id": "chapters_jsonl",
        "label": "Chapters JSONL",
        "format": "jsonl",
        "path": str(chapters_jsonl),
        "exists": chapters_jsonl.exists(),
        "description": "Per-chapter results in JSONL format",
    })
    return items


def _read_failures(mgr: RunManager) -> list[dict[str, Any]]:
    rp = mgr.run_paths
    if not rp:
        return []
    failures_dir = rp.artifacts_dir / "failures"
    if not failures_dir.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for p in sorted(failures_dir.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        is_episode = "episode_id" in d
        items.append({
            "type": "episode" if is_episode else "chapter",
            "id": d.get("episode_id", "") or d.get("chapter", {}).get("chapter_id", p.stem),
            "title": d.get("chapter", {}).get("title", ""),
            "chapterIds": d.get("chapter_ids", []) if is_episode else [],
            "errorType": d.get("error_type", "Unknown"),
            "error": d.get("error", ""),
        })
    return items  # end _read_failures


def _read_logs(mgr: RunManager, limit: int = 200) -> list[dict[str, Any]]:
    rp = mgr.run_paths
    if not rp:
        return []
    log_path = rp.logs_dir / "run.jsonl"
    if not log_path.exists():
        return []
    items: list[dict[str, Any]] = []
    try:
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        for line in lines[-limit:]:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            items.append({
                "timestamp": rec.get("timestamp", ""),
                "event": rec.get("event", ""),
                "stage": rec.get("stage"),
                "chapterId": rec.get("chapter_id"),
                "episodeId": rec.get("episode_id"),
                "errorType": rec.get("error_type"),
                "error": rec.get("error"),
            })
    except OSError:
        pass
    return items  # end _read_logs


def _read_settings(mgr: RunManager) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    st = mgr.state
    return {
        "apiKeySet": bool(api_key),
        "apiKeyStatus": "已配置" if api_key else "未配置",
        "model": st.model or os.environ.get("OPENAI_MODEL", "gpt-4o"),
        "baseUrl": os.environ.get("OPENAI_BASE_URL", ""),
        "chaptersPerEpisode": st.chapters_per_episode,
        "splitStrategy": st.split_strategy,
        "useCache": st.use_cache,
        "skipQuality": st.skip_quality,
        "outputDir": st.output_dir or "./output",
        "lastRunId": st.run_id or "—",
        "lastRunStatus": st.status,
    }


def _read_standard_analysis(mgr: RunManager) -> dict[str, Any] | None:
    """Read standard_analysis result from standard_output.json."""
    st = mgr.state
    if not st.output_dir:
        return None
    path = Path(st.output_dir) / "standard_output.json"
    if not path.exists():
        return None
    try:
        return mgr._read_cached_artifact(str(path))
    except Exception:
        return None


def _list_runs() -> list[dict[str, Any]]:
    """List all completed runs in data/runs/ with checkpoint availability."""
    runs_dir = Path("data/runs")
    if not runs_dir.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for d in sorted(runs_dir.iterdir()):
        if not d.is_dir():
            continue
        # Check for book_result or book_output to confirm it's a valid run
        has_result = (d / "artifacts" / "book_result.json").exists() or (d / "book_output.json").exists()
        # Check for fast_scan artifacts
        has_scan = (d / "artifacts" / "book_overview.json").exists()
        # Check for standard_analysis artifacts
        has_standard = (d / "standard_output.json").exists()
        if not has_result and not has_scan and not has_standard:
            continue
        # Read checkpoint availability
        checkpoint_path = d / "knowledge" / "state_checkpoint.json"
        has_checkpoint = checkpoint_path.exists()
        # Try to read basic metadata
        project_name = d.name
        chapter_count = 0
        mode = ""
        try:
            idx_path = d / "artifacts" / "chapters_index.json"
            if idx_path.exists():
                idx = json.loads(idx_path.read_text(encoding="utf-8"))
                if isinstance(idx, list):
                    chapter_count = len(idx)
            # Try chapter_index.json (fast_scan format)
            if chapter_count == 0:
                ci_path = d / "artifacts" / "chapter_index.json"
                if ci_path.exists():
                    ci = json.loads(ci_path.read_text(encoding="utf-8"))
                    if isinstance(ci, list):
                        chapter_count = len(ci)
        except (json.JSONDecodeError, OSError):
            pass
        if has_standard:
            mode = "standard_analysis"
        elif has_scan and not has_result:
            mode = "fast_scan"
        elif has_result:
            mode = "deep_analysis"
        items.append({
            "runId": d.name,
            "projectName": project_name,
            "outputDir": str(d.resolve()),
            "mode": mode,
            "chapterCount": chapter_count,
            "hasCheckpoint": has_checkpoint,
        })
    return items


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class ApiHandler(BaseHTTPRequestHandler):
    server_version = "HistoryApi/0.2"

    def log_message(self, format: str, *args: Any) -> None:
        logger.info("%s %s", self.address_string(), format % args)

    def log_error(self, format: str, *args: Any) -> None:
        logger.error("%s %s", self.address_string(), format % args)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        mgr = _run_manager

        if path == "/api/health":
            self._send_json({"status": "ok"})
            return
        if path == "/api/pipeline/status":
            self._send_json(mgr.get_status())
            return
        if path == "/api/runs":
            self._send_json(_list_runs())
            return
        if path == "/api/results/dashboard":
            if mgr.state.mode == "standard_analysis":
                self._send_standard_dashboard(mgr)
                return
            rp = mgr.run_paths
            progress = mgr._read_progress(rp) if rp else {
                "currentStage": "", "currentChapterLabel": "",
                "completedChapters": 0, "totalChapters": 0,
                "cacheHits": 0, "failedCount": 0,
            }
            self._send_json({
                "summary": _read_summary(mgr),
                "latestEpisodes": _read_episodes(mgr)[-5:],
                "latestFailures": _read_failures(mgr)[-5:],
                "progress": progress,
                "recentLogs": _read_logs(mgr, limit=20),
            })
            return
        if path == "/api/results/summary":
            self._send_json(_read_summary(mgr))
            return
        if path == "/api/results/episodes":
            if mgr.state.mode == "standard_analysis":
                self._send_json([])
                return
            self._send_json(_read_episodes(mgr))
            return
        # /api/results/episodes/{id}
        ep_match = re.match(r"^/api/results/episodes/(.+)$", path)
        if ep_match:
            detail = _read_episode_detail(mgr, ep_match.group(1))
            if detail is None:
                self._send_json({"error": "Episode not found"}, status=HTTPStatus.NOT_FOUND)
            else:
                self._send_json(detail)
            return
        if path == "/api/results/episode-plan":
            self._send_json(_read_episode_plan(mgr))
            return
        if path == "/api/results/characters":
            if mgr.state.mode == "standard_analysis":
                self._send_standard_characters(mgr)
                return
            self._send_json(_read_characters(mgr))
            return
        # /api/results/characters/{id}
        ch_match = re.match(r"^/api/results/characters/(.+)$", path)
        if ch_match:
            cid = unquote(ch_match.group(1))
            if mgr.state.mode == "standard_analysis":
                self._send_standard_character_detail(mgr, cid)
                return
            detail = _read_character_detail(mgr, cid)
            if detail is None:
                self._send_json({"error": "Character not found"}, status=HTTPStatus.NOT_FOUND)
            else:
                self._send_json(detail)
            return
        if path == "/api/results/timeline":
            if mgr.state.mode == "standard_analysis":
                self._send_standard_timeline(mgr)
                return
            self._send_json(_read_timeline(mgr))
            return
        if path == "/api/results/exports":
            self._send_json(_read_exports(mgr))
            return
        if path == "/api/results/failures":
            self._send_json(_read_failures(mgr))
            return
        if path == "/api/results/logs":
            self._send_json(_read_logs(mgr))
            return
        if path == "/api/settings":
            self._send_json(_read_settings(mgr))
            return

        # -- standard_analysis result endpoint --
        if path == "/api/results/standard-analysis":
            data = _read_standard_analysis(mgr)
            if data is None:
                self._send_json({"error": "No standard analysis result"}, status=HTTPStatus.NOT_FOUND)
            else:
                self._send_json(_camelize(data))
            return

        # -- scan API endpoints (3-way: standard_analysis / deep_analysis / fast_scan) --
        is_deep = mgr.state.mode in ("deep_analysis", "book")
        is_standard = mgr.state.mode == "standard_analysis"
        if path == "/api/scan/overview":
            if is_standard:
                self._send_standard_overview(mgr)
            elif is_deep:
                self._send_deep_overview(mgr)
            else:
                self._send_scan_artifact(mgr, "book_overview.json")
            return
        if path == "/api/scan/segments":
            if is_standard:
                self._send_standard_segments(mgr)
            elif is_deep:
                self._send_deep_segments(mgr)
            else:
                self._send_scan_segments_merged(mgr)
            return
        # /api/scan/segments/{id}
        seg_match = re.match(r"^/api/scan/segments/(.+)$", path)
        if seg_match:
            if is_standard:
                self._send_standard_segment(mgr, seg_match.group(1))
            elif is_deep:
                self._send_deep_segment(mgr, seg_match.group(1))
            else:
                self._send_scan_segment(mgr, seg_match.group(1))
            return
        if path == "/api/scan/key-chapters":
            if is_standard:
                self._send_standard_key_chapters(mgr)
            elif is_deep:
                self._send_deep_key_chapters(mgr)
            else:
                self._send_scan_artifact(mgr, "key_chapters.json")
            return
        if path == "/api/scan/reading-guide":
            if is_standard:
                self._send_standard_reading_guide(mgr)
            elif is_deep:
                self._send_deep_reading_guide(mgr)
            else:
                self._send_scan_artifact(mgr, "reading_guide.json")
            return
        if path == "/api/scan/chapter-index":
            if is_standard:
                self._send_standard_chapter_index(mgr)
            elif is_deep:
                self._send_deep_chapter_index(mgr)
            else:
                self._send_scan_artifact(mgr, "chapter_index.json")
            return
        if path == "/api/scan/stats":
            if is_standard:
                self._send_standard_stats(mgr)
            elif is_deep:
                self._send_deep_stats(mgr)
            else:
                self._send_scan_artifact(mgr, "run_stats.json")
            return

        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        mgr = _run_manager
        try:
            payload = self._read_json()
            if path == "/api/pipeline/start":
                result = mgr.start(payload)
                if "error" in result:
                    self._send_json(result, status=HTTPStatus.CONFLICT)
                else:
                    self._send_json(result)
                return
            if path == "/api/pipeline/retry":
                self._handle_retry(mgr, payload)
                return
            if path == "/api/crawl/inspect":
                self._handle_inspect(payload)
                return
            if path == "/api/crawl/export":
                self._handle_export(payload)
                return
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            logger.exception("POST %s failed: %s", path, exc)
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    # -- crawl handlers (preserved from original) --

    def _handle_inspect(self, payload: dict) -> None:
        book_url = str(payload.get("book_url", "")).strip()
        if not book_url:
            raise RuntimeError("book_url is required")
        logger.info("Crawl inspect: %s", book_url)
        limit = payload.get("limit")
        if limit is not None:
            limit = int(limit)
        preview = inspect_novel_book(book_url, limit=limit)
        logger.info("Crawl inspect done: %s — %d chapters", preview.title, len(preview.chapters))
        self._send_json(asdict(preview))

    def _handle_export(self, payload: dict) -> None:
        book_url = str(payload.get("book_url", "")).strip()
        if not book_url:
            raise RuntimeError("book_url is required")
        logger.info("Crawl export: %s chapters %s-%s", book_url,
                     payload.get("chapter_start"), payload.get("chapter_end"))
        chapter_start = int(payload.get("chapter_start") or 1)
        chapter_end = int(payload.get("chapter_end") or chapter_start)
        context_before = int(payload.get("context_before_chapters") or 0)
        crawl_limit = chapter_end
        book = crawl_novel_book(book_url, limit=crawl_limit)
        context_chapters, selected_chapters = select_chapters(
            book.chapters,
            start=chapter_start,
            end=chapter_end,
            context_before=context_before,
        )
        output_dir = Path(str(payload.get("output_dir") or "data/exports")).resolve()
        slug = sanitize_name(book.title or "novel")
        output_path = output_dir / f"{slug}_selection.txt"
        json_path = output_dir / f"{slug}_selection.json"
        save_selected_chapters(
            book,
            context_chapters=context_chapters,
            selected_chapters=selected_chapters,
            output_path=output_path,
            json_output_path=json_path,
        )
        self._send_json({
            "title": book.title,
            "author": book.author,
            "selected_start": chapter_start,
            "selected_end": chapter_end,
            "context_count": len(context_chapters),
            "selected_count": len(selected_chapters),
            "text_output": str(output_path),
            "json_output": str(json_path),
            "selected_titles": [chapter.title for chapter in selected_chapters],
        })

    # -- helpers --

    def _handle_retry(self, mgr: RunManager, payload: dict) -> None:
        """Handle /api/pipeline/retry — 补跑失败的 segment 或 key_chapter（异步执行）。"""
        retry_type = payload.get("type", "")  # "segments" or "key_chapters"

        if retry_type not in ("segments", "key_chapters"):
            self._send_json({"error": "type 必须是 segments 或 key_chapters"}, status=HTTPStatus.BAD_REQUEST)
            return

        with mgr._lock:
            st = copy.copy(mgr._state)

        if st.status not in ("completed", "failed"):
            self._send_json({"error": "只能在完成或失败状态下补跑"}, status=HTTPStatus.BAD_REQUEST)
            return

        artifacts_dir = self._scan_artifacts_dir(mgr)
        if not artifacts_dir:
            self._send_json({"error": "未找到产物目录"}, status=HTTPStatus.NOT_FOUND)
            return

        # Mark as running before spawning thread
        with mgr._lock:
            mgr._state.status = "running"
            mgr._state.updated_at = _utc_now()

        def _do_retry():
            try:
                from .chaptering import split_into_chapters
                with open(st.input_path, "r", encoding="utf-8") as f:
                    text = f.read()
                chapters = split_into_chapters(text)
                chapters_map = {ch.chapter_id: ch for ch in chapters}

                api_key = os.environ.get("OPENAI_API_KEY", "")
                base_url = os.environ.get("OPENAI_BASE_URL")
                api_type = os.environ.get("OPENAI_TYPE", "openai")
                model = st.model or os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
                if api_type == "anthropic":
                    client = AnthropicLLMClient(api_key=api_key, model=model, base_url=base_url or "")
                else:
                    client = OpenAILLMClient(api_key=api_key, model=model, base_url=base_url)

                try:
                    book_fp = compute_book_fingerprint(text)
                    base_cache = Path(st.output_dir).parent.parent / "cache"
                    cache = StageCache.for_book(base_cache, book_fp, model) if st.use_cache else None
                except Exception:
                    cache = None

                from .retry_missing import retry_failed_segments, retry_failed_key_chapters
                if retry_type == "segments":
                    retry_failed_segments(str(artifacts_dir), client, chapters_map, cache=cache)
                else:
                    retry_failed_key_chapters(str(artifacts_dir), client, chapters_map, cache=cache)

                with mgr._lock:
                    mgr._state.status = "completed"
                    mgr._state.updated_at = _utc_now()
            except Exception as exc:
                logging.getLogger(__name__).error("Retry failed: %s", exc)
                with mgr._lock:
                    mgr._state.status = "completed"
                    mgr._state.error = f"retry error: {exc}"
                    mgr._state.updated_at = _utc_now()

        t = threading.Thread(target=_do_retry, daemon=True)
        t.start()
        self._send_json({"status": "retrying", "type": retry_type})

    # ------------------------------------------------------------------
    # Deep-analysis → scan-compatible data synthesis
    # ------------------------------------------------------------------

    def _load_book_result(self, mgr: RunManager) -> dict | None:
        artifacts = self._scan_artifacts_dir(mgr)
        if not artifacts:
            return None
        path = artifacts / "book_result.json"
        if not path.exists():
            return None
        try:
            return mgr._read_cached_artifact(str(path))
        except Exception:
            return None

    def _send_deep_overview(self, mgr: RunManager) -> None:
        br = self._load_book_result(mgr)
        if not br:
            self._send_json({"error": "No deep analysis result"}, status=HTTPStatus.NOT_FOUND)
            return
        chapters = br.get("chapters", [])
        total_words = sum(len(ch.get("chapter", {}).get("text", "")) for ch in chapters)
        knowledge = br.get("knowledge", {})
        chars = knowledge.get("characters", [])
        core_chars = [c.get("canonical_name", "") for c in chars[:10]]
        ep_plan = br.get("episode_plan", [])
        key_stages = [ep.get("title", "") for ep in ep_plan]
        # Build main plotline from episode themes
        main_plot_parts = []
        for ep in ep_plan:
            theme = ep.get("core_theme", "")
            if theme:
                main_plot_parts.append(theme)
        main_plotline = "；".join(main_plot_parts) if main_plot_parts else "深度分析已完成"
        # Open questions from unresolved foreshadowing
        causal = br.get("causal_state", {})
        open_qs = [f.get("description", str(f)) if isinstance(f, dict) else str(f)
                   for f in causal.get("unresolved_foreshadowing", [])[:10]]
        completeness = 1.0 if mgr.state.status == "completed" else 0.5
        overview = {
            "title": mgr.state.project_name or "深度分析",
            "total_chapters": len(chapters),
            "total_words": total_words,
            "main_plotline": main_plotline,
            "key_stages": key_stages,
            "core_characters": core_chars,
            "open_questions": open_qs,
            "completeness": completeness,
        }
        self._send_json(_camelize(overview))

    def _send_deep_segments(self, mgr: RunManager) -> None:
        br = self._load_book_result(mgr)
        if not br:
            self._send_json({"error": "No deep analysis result"}, status=HTTPStatus.NOT_FOUND)
            return
        segments = []
        for ch_result in br.get("chapters", []):
            ch = ch_result.get("chapter", {})
            cid = ch.get("chapter_id", "")
            title = ch.get("title", "")
            ep = ch_result.get("episode", {})
            ne = ch_result.get("normalized_events", {})
            events = ne.get("events", []) if isinstance(ne, dict) else []
            chars_set: set[str] = set()
            for ev in events:
                for c in ev.get("characters", []):
                    chars_set.add(c)
            scores = ch_result.get("scores", [])
            max_climax = max((s.get("climax_score", 0) for s in scores), default=0) if scores else 0
            priority = "high" if max_climax >= 6 else ("medium" if max_climax >= 4 else "low")
            segments.append({
                "segment_id": cid,
                "chapter_ids": [cid],
                "chapter_range": title,
                "candidate_chapters": [title],
                "estimated_priority": priority,
                "summary": ep.get("episode_summary", ""),
                "main_plot": ep.get("core_theme", ""),
                "key_characters": list(chars_set)[:8],
                "must_read_chapters": [title] if max_climax >= 5 else [],
                "skippable_ranges": [],
                "open_threads": [ep.get("ending_hook", "")] if ep.get("ending_hook") else [],
                "status": ch_result.get("status", "completed"),
                "error": None,
            })
        self._send_json(_camelize(segments))

    def _send_deep_segment(self, mgr: RunManager, segment_id: str) -> None:
        br = self._load_book_result(mgr)
        if not br:
            self._send_json({"error": "No deep analysis result"}, status=HTTPStatus.NOT_FOUND)
            return
        for ch_result in br.get("chapters", []):
            ch = ch_result.get("chapter", {})
            if ch.get("chapter_id") == segment_id:
                ep = ch_result.get("episode", {})
                ne = ch_result.get("normalized_events", {})
                events = ne.get("events", []) if isinstance(ne, dict) else []
                chars_set: set[str] = set()
                for ev in events:
                    for c in ev.get("characters", []):
                        chars_set.add(c)
                scores = ch_result.get("scores", [])
                max_climax = max((s.get("climax_score", 0) for s in scores), default=0) if scores else 0
                priority = "high" if max_climax >= 6 else ("medium" if max_climax >= 4 else "low")
                title = ch.get("title", "")
                seg = {
                    "segment_id": segment_id,
                    "chapter_ids": [segment_id],
                    "chapter_range": title,
                    "candidate_chapters": [title],
                    "estimated_priority": priority,
                    "summary": ep.get("episode_summary", ""),
                    "main_plot": ep.get("core_theme", ""),
                    "key_characters": list(chars_set)[:8],
                    "must_read_chapters": [title] if max_climax >= 5 else [],
                    "skippable_ranges": [],
                    "open_threads": [ep.get("ending_hook", "")] if ep.get("ending_hook") else [],
                    "status": ch_result.get("status", "completed"),
                    "error": None,
                }
                self._send_json(_camelize(seg))
                return
        self._send_json({"error": f"Segment {segment_id} not found"}, status=HTTPStatus.NOT_FOUND)

    def _send_deep_key_chapters(self, mgr: RunManager) -> None:
        br = self._load_book_result(mgr)
        if not br:
            self._send_json({"error": "No deep analysis result"}, status=HTTPStatus.NOT_FOUND)
            return
        key_chapters = []
        for ch_result in br.get("chapters", []):
            ch = ch_result.get("chapter", {})
            cid = ch.get("chapter_id", "")
            title = ch.get("title", "")
            ep = ch_result.get("episode", {})
            scores = ch_result.get("scores", [])
            ne = ch_result.get("normalized_events", {})
            events = ne.get("events", []) if isinstance(ne, dict) else []
            max_climax = max((s.get("climax_score", 0) for s in scores), default=0) if scores else 0
            max_plot = max((s.get("main_plot_score", 0) for s in scores), default=0) if scores else 0
            importance = max(max_climax, max_plot)
            if importance >= 4:
                level = "critical" if importance >= 7 else ("important" if importance >= 5 else "notable")
            else:
                level = "notable"
            chars_set: set[str] = set()
            for ev in events:
                for c in ev.get("characters", []):
                    chars_set.add(c)
            # Build why_it_matters from key_events + climax
            why_parts = []
            if ep.get("climax"):
                why_parts.append(ep["climax"])
            elif ep.get("main_conflict"):
                why_parts.append(ep["main_conflict"])
            why = why_parts[0] if why_parts else ep.get("episode_summary", "")
            # Related threads from ending_hook
            threads = []
            if ep.get("ending_hook"):
                threads.append(ep["ending_hook"])
            key_chapters.append({
                "chapter_id": f"{cid}:{title}",
                "importance_level": level,
                "summary": ep.get("episode_summary", ""),
                "why_it_matters": why,
                "related_characters": list(chars_set)[:6],
                "related_threads": threads,
                "status": "completed" if ch_result.get("status") == "ok" or ch_result.get("status") == "completed" else "completed",
            })
        self._send_json(_camelize(key_chapters))

    def _send_deep_reading_guide(self, mgr: RunManager) -> None:
        br = self._load_book_result(mgr)
        if not br:
            self._send_json({"error": "No deep analysis result"}, status=HTTPStatus.NOT_FOUND)
            return
        chapters = br.get("chapters", [])
        ep_plan = br.get("episode_plan", [])
        # All chapters are must-read in deep analysis (it's a curated selection)
        must_read = []
        for ch_result in chapters:
            ch = ch_result.get("chapter", {})
            must_read.append(f"{ch.get('chapter_id', '')}:{ch.get('title', '')}")
        # Summary by episode
        summary_by_stage = []
        for ep in ep_plan:
            ch_titles = ep.get("chapter_titles", [])
            ch_range = f"{ch_titles[0]} ~ {ch_titles[-1]}" if ch_titles else ""
            summary_by_stage.append({
                "stage": ep.get("title", ""),
                "chapters": ch_range,
                "summary": ep.get("core_theme", ""),
            })
        guide = {
            "must_read_chapters": must_read,
            "skippable_ranges": [],
            "reading_order_suggestion": "按章节顺序阅读，深度分析已覆盖所有选定章节。",
            "estimated_essential_ratio": 1.0,
            "summary_by_stage": summary_by_stage,
        }
        self._send_json(_camelize(guide))

    def _send_deep_chapter_index(self, mgr: RunManager) -> None:
        br = self._load_book_result(mgr)
        if not br:
            self._send_json({"error": "No deep analysis result"}, status=HTTPStatus.NOT_FOUND)
            return
        index = []
        for ch_result in br.get("chapters", []):
            ch = ch_result.get("chapter", {})
            scores = ch_result.get("scores", [])
            max_climax = max((s.get("climax_score", 0) for s in scores), default=0) if scores else 0
            max_plot = max((s.get("main_plot_score", 0) for s in scores), default=0) if scores else 0
            importance = max(max_climax, max_plot)
            genre = ch_result.get("genre", {})
            genre_name = genre.get("primary_genre", "") if isinstance(genre, dict) else ""
            tags = [genre_name] if genre_name else []
            if max_climax >= 5:
                tags.append("高潮")
            if max_plot >= 5:
                tags.append("主线")
            index.append({
                "chapter_id": ch.get("chapter_id", ""),
                "title": ch.get("title", ""),
                "word_count": len(ch.get("text", "")),
                "feature_tags": tags,
                "importance_score": importance,
                "candidate_reason": "深度分析章节" if importance >= 4 else "普通章节",
                "is_candidate": importance >= 4,
            })
        self._send_json(_camelize(index))

    def _send_deep_stats(self, mgr: RunManager) -> None:
        br = self._load_book_result(mgr)
        chapters = br.get("chapters", []) if br else []
        # Try to read stats.json for token/timing info
        artifacts = self._scan_artifacts_dir(mgr)
        model_calls = 0
        elapsed = 0
        if artifacts:
            stats_path = artifacts / "stats.json"
            if stats_path.exists():
                try:
                    stats_data = mgr._read_cached_artifact(str(stats_path))
                    if isinstance(stats_data, dict):
                        calls = stats_data.get("calls", [])
                        model_calls = len(calls)
                        elapsed = int(sum(c.get("duration_seconds", 0) for c in calls))
                except Exception:
                    pass
        stats = {
            "total_chapters": len(chapters),
            "total_segments": len(chapters),
            "segments_completed": sum(1 for c in chapters if c.get("status") in ("ok", "completed")),
            "segments_failed": sum(1 for c in chapters if c.get("status") == "failed"),
            "key_chapters_count": len(chapters),
            "key_chapters_completed": len(chapters),
            "key_chapters_failed": 0,
            "elapsed_seconds": elapsed,
            "model_calls": model_calls,
        }
        self._send_json(_camelize(stats))

    def _scan_artifacts_dir(self, mgr: RunManager) -> Path | None:
        """Return the artifacts dir for the current run, or None."""
        st = mgr.state
        if not st.output_dir:
            return None
        artifacts = Path(st.output_dir) / "artifacts"
        if not artifacts.is_dir():
            return None
        return artifacts

    def _send_scan_artifact(self, mgr: RunManager, filename: str) -> None:
        """Read and return a JSON artifact file from the scan artifacts dir (with mtime cache)."""
        artifacts = self._scan_artifacts_dir(mgr)
        if not artifacts:
            self._send_json({"error": "No run output available"}, status=HTTPStatus.NOT_FOUND)
            return
        path = artifacts / filename
        if not path.exists():
            self._send_json({"error": f"{filename} not found"}, status=HTTPStatus.NOT_FOUND)
            return
        try:
            data = mgr._read_cached_artifact(str(path))
            if data is None:
                self._send_json({"error": f"{filename} not found"}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json(_camelize(data))
        except (json.JSONDecodeError, OSError) as exc:
            self._send_json({"error": f"Failed to read {filename}: {exc}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _send_scan_segment(self, mgr: RunManager, segment_id: str) -> None:
        """Read segments.json and return the segment with the given id (with mtime cache)."""
        artifacts = self._scan_artifacts_dir(mgr)
        if not artifacts:
            self._send_json({"error": "No run output available"}, status=HTTPStatus.NOT_FOUND)
            return
        path = artifacts / "segments.json"
        if not path.exists():
            self._send_json({"error": "segments.json not found"}, status=HTTPStatus.NOT_FOUND)
            return
        try:
            data = mgr._read_cached_artifact(str(path))
        except (json.JSONDecodeError, OSError) as exc:
            self._send_json({"error": f"Failed to read segments.json: {exc}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if not isinstance(data, list):
            self._send_json({"error": "Invalid segments data"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        for item in data:
            if isinstance(item, dict) and item.get("segment_id") == segment_id:
                self._send_json(_camelize(item))
                return
        self._send_json({"error": f"Segment {segment_id} not found"}, status=HTTPStatus.NOT_FOUND)

    def _send_scan_segments_merged(self, mgr: RunManager) -> None:
        """Return segments.json merged with segments_meta.json so frontend gets all fields."""
        artifacts = self._scan_artifacts_dir(mgr)
        if not artifacts:
            self._send_json({"error": "No run output available"}, status=HTTPStatus.NOT_FOUND)
            return
        seg_path = artifacts / "segments.json"
        if not seg_path.exists():
            self._send_json({"error": "segments.json not found"}, status=HTTPStatus.NOT_FOUND)
            return
        try:
            seg_data = mgr._read_cached_artifact(str(seg_path))
        except (json.JSONDecodeError, OSError) as exc:
            self._send_json({"error": f"Failed to read segments.json: {exc}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if not isinstance(seg_data, list):
            self._send_json({"error": "Invalid segments data"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        # Merge metadata (chapter_ids, candidate_chapters, estimated_priority)
        meta_path = artifacts / "segments_meta.json"
        meta_map: dict[str, dict] = {}
        if meta_path.exists():
            try:
                meta_data = mgr._read_cached_artifact(str(meta_path))
                if isinstance(meta_data, list):
                    for m in meta_data:
                        if isinstance(m, dict) and "segment_id" in m:
                            meta_map[m["segment_id"]] = m
            except Exception:
                pass  # meta is optional enrichment

        merged = []
        for item in seg_data:
            if not isinstance(item, dict):
                merged.append(item)
                continue
            sid = item.get("segment_id", "")
            meta = meta_map.get(sid, {})
            enriched = {**item}
            if "chapter_ids" not in enriched and "chapter_ids" in meta:
                enriched["chapter_ids"] = meta["chapter_ids"]
            if "candidate_chapters" not in enriched and "candidate_chapters" in meta:
                enriched["candidate_chapters"] = meta["candidate_chapters"]
            if "estimated_priority" not in enriched and "estimated_priority" in meta:
                enriched["estimated_priority"] = meta["estimated_priority"]
            if "chapter_range_label" in meta and "chapter_range" not in enriched:
                enriched["chapter_range"] = meta["chapter_range_label"]
            merged.append(enriched)

        self._send_json(_camelize(merged))

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"Invalid JSON in request body: {exc}") from exc

    def _send_json(self, payload: dict | list, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ------------------------------------------------------------------
    # Standard-analysis → scan-compatible data synthesis
    # ------------------------------------------------------------------

    def _load_standard_result(self, mgr: RunManager) -> dict | None:
        return _read_standard_analysis(mgr)

    def _standard_chapters(self, data: dict) -> list[dict]:
        return [ch for ch in data.get("chapters", []) if ch.get("status") in ("completed", "ok")]

    def _send_standard_overview(self, mgr: RunManager) -> None:
        data = self._load_standard_result(mgr)
        if not data:
            self._send_json({"error": "No standard analysis result"}, status=HTTPStatus.NOT_FOUND)
            return
        chapters = self._standard_chapters(data)
        high = [ch for ch in chapters if ch.get("importance_score", 0) >= 4]
        # main plotline from top importance chapter summaries
        top_summaries = [ch.get("chapter_summary", "") for ch in sorted(chapters, key=lambda c: c.get("importance_score", 0), reverse=True) if ch.get("chapter_summary")][:5]
        # core characters deduplicated
        chars: list[str] = []
        seen_chars: set[str] = set()
        for ch in chapters:
            for ev in ch.get("key_events", []):
                for c in ev.get("characters", []):
                    if c not in seen_chars:
                        seen_chars.add(c)
                        chars.append(c)
        overview = {
            "title": mgr.state.project_name or "标准分析",
            "total_chapters": len(data.get("chapters", [])),
            "total_words": 0,
            "main_plotline": "；".join(top_summaries) if top_summaries else "标准分析已完成",
            "key_stages": [ch.get("title", "") for ch in high],
            "core_characters": chars[:15],
            "open_questions": [],
            "completeness": 1.0 if mgr.state.status == "completed" else 0.5,
        }
        self._send_json(_camelize(overview))

    def _send_standard_segments(self, mgr: RunManager) -> None:
        data = self._load_standard_result(mgr)
        if not data:
            self._send_json({"error": "No standard analysis result"}, status=HTTPStatus.NOT_FOUND)
            return
        all_chapters = data.get("chapters", [])
        group_size = 10
        segments = []
        for i in range(0, len(all_chapters), group_size):
            group = all_chapters[i:i + group_size]
            first_title = group[0].get("title", "") if group else ""
            last_title = group[-1].get("title", "") if group else ""
            chars_set: set[str] = set()
            summaries = []
            important_summaries = []
            must_read = []
            max_imp = 0
            for ch in group:
                imp = ch.get("importance_score", 0)
                if imp > max_imp:
                    max_imp = imp
                if ch.get("chapter_summary"):
                    summaries.append(ch["chapter_summary"])
                if imp >= 3 and ch.get("chapter_summary"):
                    important_summaries.append(ch["chapter_summary"])
                if imp >= 4:
                    must_read.append(ch.get("title", ""))
                for ev in ch.get("key_events", []):
                    for c in ev.get("characters", []):
                        chars_set.add(c)
            priority = "high" if max_imp >= 4 else ("medium" if max_imp >= 3 else "low")
            segments.append({
                "segment_id": f"seg_{(i // group_size) + 1:03d}",
                "chapter_ids": [ch.get("chapter_id", "") for ch in group],
                "chapter_range": f"{first_title} ~ {last_title}" if first_title != last_title else first_title,
                "candidate_chapters": [ch.get("title", "") for ch in group if ch.get("importance_score", 0) >= 4],
                "estimated_priority": priority,
                "summary": " ".join(summaries[:3]),
                "main_plot": " ".join(important_summaries[:2]),
                "key_characters": list(chars_set)[:8],
                "must_read_chapters": must_read,
                "skippable_ranges": [],
                "open_threads": [],
                "status": "completed",
                "error": None,
            })
        self._send_json(_camelize(segments))

    def _send_standard_segment(self, mgr: RunManager, segment_id: str) -> None:
        """Find a single segment by id from the same grouping logic."""
        data = self._load_standard_result(mgr)
        if not data:
            self._send_json({"error": "No standard analysis result"}, status=HTTPStatus.NOT_FOUND)
            return
        all_chapters = data.get("chapters", [])
        group_size = 10
        for i in range(0, len(all_chapters), group_size):
            sid = f"seg_{(i // group_size) + 1:03d}"
            if sid != segment_id:
                continue
            group = all_chapters[i:i + group_size]
            first_title = group[0].get("title", "") if group else ""
            last_title = group[-1].get("title", "") if group else ""
            chars_set: set[str] = set()
            summaries = []
            must_read = []
            max_imp = 0
            for ch in group:
                imp = ch.get("importance_score", 0)
                if imp > max_imp:
                    max_imp = imp
                if ch.get("chapter_summary"):
                    summaries.append(ch["chapter_summary"])
                if imp >= 4:
                    must_read.append(ch.get("title", ""))
                for ev in ch.get("key_events", []):
                    for c in ev.get("characters", []):
                        chars_set.add(c)
            priority = "high" if max_imp >= 4 else ("medium" if max_imp >= 3 else "low")
            seg = {
                "segment_id": sid,
                "chapter_ids": [ch.get("chapter_id", "") for ch in group],
                "chapter_range": f"{first_title} ~ {last_title}" if first_title != last_title else first_title,
                "candidate_chapters": [ch.get("title", "") for ch in group if ch.get("importance_score", 0) >= 4],
                "estimated_priority": priority,
                "summary": " ".join(summaries[:3]),
                "main_plot": " ".join([s for ch2 in group if ch2.get("importance_score", 0) >= 3 for s in [ch2.get("chapter_summary", "")] if s][:2]),
                "key_characters": list(chars_set)[:8],
                "must_read_chapters": must_read,
                "skippable_ranges": [],
                "open_threads": [],
                "status": "completed",
                "error": None,
            }
            self._send_json(_camelize(seg))
            return
        self._send_json({"error": f"Segment {segment_id} not found"}, status=HTTPStatus.NOT_FOUND)

    def _send_standard_key_chapters(self, mgr: RunManager) -> None:
        data = self._load_standard_result(mgr)
        if not data:
            self._send_json({"error": "No standard analysis result"}, status=HTTPStatus.NOT_FOUND)
            return
        key_chapters = []
        for ch in data.get("chapters", []):
            score = ch.get("importance_score", 0)
            if score < 3:
                continue
            level = "critical" if score >= 5 else ("important" if score >= 4 else "notable")
            chars_set: set[str] = set()
            for ev in ch.get("key_events", []):
                for c in ev.get("characters", []):
                    chars_set.add(c)
            key_chapters.append({
                "chapter_id": f"{ch.get('chapter_id', '')}:{ch.get('title', '')}",
                "importance_level": level,
                "summary": ch.get("chapter_summary", ""),
                "why_it_matters": ch.get("importance_reason", ""),
                "related_characters": list(chars_set)[:6],
                "related_threads": [],
                "status": "completed",
            })
        self._send_json(_camelize(key_chapters))

    def _send_standard_reading_guide(self, mgr: RunManager) -> None:
        data = self._load_standard_result(mgr)
        if not data:
            self._send_json({"error": "No standard analysis result"}, status=HTTPStatus.NOT_FOUND)
            return
        chapters = data.get("chapters", [])
        total = len(chapters)
        must_read = [ch.get("title", "") for ch in chapters if ch.get("importance_score", 0) >= 4]
        skippable = [ch.get("title", "") for ch in chapters if ch.get("importance_score", 0) <= 2]
        # summary_by_stage: group by segments of 10
        summary_by_stage = []
        group_size = 10
        for i in range(0, total, group_size):
            group = chapters[i:i + group_size]
            first = group[0].get("title", "") if group else ""
            last = group[-1].get("title", "") if group else ""
            sums = [ch.get("chapter_summary", "") for ch in group if ch.get("importance_score", 0) >= 3 and ch.get("chapter_summary")]
            summary_by_stage.append({
                "stage": f"第{(i // group_size) + 1}段",
                "chapters": f"{first} ~ {last}" if first != last else first,
                "summary": " ".join(sums[:2]) if sums else "无重要事件",
            })
        guide = {
            "must_read_chapters": must_read,
            "skippable_ranges": skippable,
            "reading_order_suggestion": "按章节顺序阅读，重点关注重要性≥4的章节。",
            "estimated_essential_ratio": len(must_read) / total if total > 0 else 0,
            "summary_by_stage": summary_by_stage,
        }
        self._send_json(_camelize(guide))

    def _send_standard_chapter_index(self, mgr: RunManager) -> None:
        data = self._load_standard_result(mgr)
        if not data:
            self._send_json({"error": "No standard analysis result"}, status=HTTPStatus.NOT_FOUND)
            return
        index = []
        for ch in data.get("chapters", []):
            score = ch.get("importance_score", 0)
            tags: list[str] = []
            for ev in ch.get("key_events", []):
                if ev.get("involvesProtagonist") or ev.get("involves_protagonist"):
                    tags.append("protagonist")
                    break
            for ev in ch.get("key_events", []):
                tp = ev.get("eventType") or ev.get("event_type", "")
                if tp == "turning_point":
                    tags.append("turning_point")
                    break
            if score >= 4:
                tags.append("重要")
            index.append({
                "chapter_id": ch.get("chapter_id", ""),
                "title": ch.get("title", ""),
                "word_count": 0,
                "feature_tags": tags,
                "importance_score": score,
                "candidate_reason": ch.get("importance_reason", ""),
                "is_candidate": score >= 3,
            })
        self._send_json(_camelize(index))

    def _send_standard_stats(self, mgr: RunManager) -> None:
        import math
        data = self._load_standard_result(mgr)
        if not data:
            self._send_json(_camelize({
                "total_chapters": 0, "total_segments": 0,
                "segments_completed": 0, "segments_failed": 0,
                "key_chapters_count": 0, "key_chapters_completed": 0,
                "key_chapters_failed": 0, "elapsed_seconds": 0, "model_calls": 0,
            }))
            return
        chapters = data.get("chapters", [])
        total = len(chapters)
        key_count = sum(1 for ch in chapters if ch.get("importance_score", 0) >= 3)
        stats_data = data.get("stats", {})
        self._send_json(_camelize({
            "total_chapters": total,
            "total_segments": math.ceil(total / 10) if total > 0 else 0,
            "segments_completed": math.ceil(total / 10) if total > 0 else 0,
            "segments_failed": 0,
            "key_chapters_count": key_count,
            "key_chapters_completed": key_count,
            "key_chapters_failed": 0,
            "elapsed_seconds": 0,
            "model_calls": len(stats_data.get("calls", [])),
        }))

    def _send_standard_dashboard(self, mgr: RunManager) -> None:
        """Synthesize dashboard data from standard_output.json."""
        data = self._load_standard_result(mgr)
        chapters = data.get("chapters", []) if data else []
        failures = data.get("failures", []) if data else []
        stats_data = data.get("stats", {}) if data else {}
        completed_count = sum(1 for ch in chapters if ch.get("status") in ("completed", "ok"))
        failed_count = len(failures)
        char_set: set[str] = set()
        for ch in chapters:
            for ev in ch.get("key_events", []):
                for c in ev.get("characters", []):
                    char_set.add(c)
        summary = {
            "runId": mgr.state.run_id,
            "projectName": mgr.state.project_name,
            "inputName": Path(mgr.state.input_path).name if mgr.state.input_path else "",
            "model": mgr.state.model,
            "status": mgr.state.status,
            "chapterCount": len(chapters),
            "sceneCount": 0,
            "eventCount": sum(len(ch.get("key_events", [])) for ch in chapters),
            "characterCount": len(char_set),
            "episodeCount": 0,
            "failureCount": failed_count,
            "outputDir": mgr.state.output_dir,
            "startedAt": mgr.state.started_at,
            "updatedAt": mgr.state.updated_at,
        }
        latest_failures = []
        for f in failures[-5:]:
            latest_failures.append({
                "type": "chapter",
                "id": f.get("chapter_id", f.get("chapterId", "")),
                "title": f.get("title", ""),
                "chapterIds": [],
                "errorType": "LLMError",
                "error": f.get("error", ""),
            })
        progress = {
            "currentStage": "completed" if mgr.state.status == "completed" else "running",
            "currentChapterLabel": "",
            "completedChapters": completed_count,
            "totalChapters": len(chapters),
            "cacheHits": stats_data.get("cache_hits", 0),
            "failedCount": failed_count,
        }
        self._send_json({
            "summary": summary,
            "latestEpisodes": [],
            "latestFailures": latest_failures,
            "progress": progress,
            "recentLogs": [],
        })

    def _send_standard_characters(self, mgr: RunManager) -> list[dict]:
        """Synthesize character list from standard_output key_events."""
        data = self._load_standard_result(mgr)
        if not data:
            self._send_json([])
            return []
        char_events: dict[str, int] = {}
        char_latest: dict[str, str] = {}
        for ch in data.get("chapters", []):
            ch_title = ch.get("title", "")
            for ev in ch.get("key_events", []):
                for c in ev.get("characters", []):
                    char_events[c] = char_events.get(c, 0) + 1
                    char_latest[c] = ch_title
        items = []
        for name, count in sorted(char_events.items(), key=lambda x: x[1], reverse=True):
            items.append({
                "id": name,
                "name": name,
                "faction": None,
                "aliasCount": 0,
                "eventCount": count,
                "latestChapterLabel": char_latest.get(name, ""),
            })
        self._send_json(items)
        return items

    def _send_standard_character_detail(self, mgr: RunManager, char_id: str) -> None:
        """Synthesize character detail from standard_output key_events."""
        data = self._load_standard_result(mgr)
        if not data:
            self._send_json({"error": "Character not found"}, status=HTTPStatus.NOT_FOUND)
            return
        events: list[str] = []
        related: set[str] = set()
        found = False
        for ch in data.get("chapters", []):
            for ev in ch.get("key_events", []):
                chars = ev.get("characters", [])
                if char_id in chars:
                    found = True
                    events.append(ev.get("title", ev.get("description", "")))
                    for c in chars:
                        if c != char_id:
                            related.add(c)
        if not found:
            self._send_json({"error": "Character not found"}, status=HTTPStatus.NOT_FOUND)
            return
        rels = [{"targetName": r, "relationType": "unknown", "note": ""} for r in list(related)[:10]]
        self._send_json({
            "id": char_id,
            "name": char_id,
            "aliases": [],
            "identity": "",
            "faction": "",
            "currentGoal": "",
            "recentEvents": events[-20:],
            "relationships": rels,
        })

    def _send_standard_timeline(self, mgr: RunManager) -> None:
        """Synthesize timeline from standard_output key_events."""
        data = self._load_standard_result(mgr)
        if not data:
            self._send_json([])
            return
        items = []
        idx = 0
        for ch in data.get("chapters", []):
            ch_title = ch.get("title", "")
            for ev in ch.get("key_events", []):
                idx += 1
                items.append({
                    "id": ev.get("event_id", f"se_{idx}"),
                    "title": ev.get("title", ""),
                    "chapterRangeLabel": ch_title,
                    "eventType": ev.get("event_type", ev.get("eventType", "plot")),
                    "eventGroup": ch_title,
                    "importance": ev.get("importance", ch.get("importance_score", 3)),
                    "characters": ev.get("characters", []),
                    "summary": ev.get("description", ""),
                })
        self._send_json(items)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")


def _load_env(path: str = ".env") -> None:
    """Load .env file into os.environ (no external dependency)."""
    env_path = Path(path)
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if not os.environ.get(key):
                os.environ[key] = value


def _setup_logging() -> None:
    """Configure logging to write to both stderr and data/api_server.log."""
    log_dir = Path("data")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # File handler — append mode
    fh = logging.FileHandler(log_dir / "api_server.log", encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(log_fmt)
    root.addHandler(fh)
    # Stderr handler
    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    sh.setFormatter(log_fmt)
    root.addHandler(sh)
    # Error-only file
    eh = logging.FileHandler(log_dir / "api_server.err.log", encoding="utf-8")
    eh.setLevel(logging.WARNING)
    eh.setFormatter(log_fmt)
    root.addHandler(eh)


def main() -> None:
    _load_env()
    _setup_logging()
    server = ThreadingHTTPServer(("127.0.0.1", 8765), ApiHandler)
    logger.info("API server listening on http://127.0.0.1:8765")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
