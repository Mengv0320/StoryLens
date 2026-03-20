from __future__ import annotations

import json
import logging
import os
import re
import threading
import uuid
import copy
import secrets
import traceback as _tb_mod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# -- Security: API token (C-2) --
_API_TOKEN: str | None = None
MAX_BODY_SIZE = 10 * 1024 * 1024  # 10 MB (H-1)

def _init_token() -> str:
    global _API_TOKEN
    token = os.environ.get("API_TOKEN") or secrets.token_urlsafe(32)
    _API_TOKEN = token
    return token

# -- Security: CORS whitelist (C-3) --
_CORS_ORIGINS: list[str] = []

def _init_cors() -> None:
    global _CORS_ORIGINS
    defaults = ["http://localhost", "http://127.0.0.1"]
    extra = os.environ.get("CORS_ORIGINS", "")
    if extra:
        defaults.extend(o.strip() for o in extra.split(",") if o.strip())
    _CORS_ORIGINS = defaults

def _check_cors_origin(origin: str | None) -> str | None:
    if not origin:
        return None
    from urllib.parse import urlparse as _up
    parsed = _up(origin)
    origin_base = f"{parsed.scheme}://{parsed.hostname}" if parsed.hostname else ""
    for allowed in _CORS_ORIGINS:
        a = _up(allowed)
        allowed_base = f"{a.scheme}://{a.hostname}" if a.hostname else allowed.rstrip("/")
        if origin_base == allowed_base:
            return origin
    return None

# -- Security: Path validation (H-2/H-3/H-4) --
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

def _validate_path_within(path_val: str, base: Path, label: str) -> Path:
    resolved = Path(path_val).resolve()
    base_resolved = base.resolve()
    if os.name == "nt":
        ok = str(resolved).lower().startswith(str(base_resolved).lower())
    else:
        ok = str(resolved).startswith(str(base_resolved))
    if not ok:
        raise ValueError(f"{label} must be within {base_resolved}")
    return resolved

from .config import Paths, DEFAULT_MODEL
from .serialization import camelize as _camelize
from .runtime import RunLogger, RunPaths, StageCache, compute_book_fingerprint, save_json, save_jsonl
from .stages import OpenAILLMClient, AnthropicLLMClient, MultiProviderClient
from .stats import PipelineStats
from .web_crawler import inspect_novel_book, crawl_novel_book, save_selected_chapters, select_chapters
from .book_index import BookIndex


# ---------------------------------------------------------------------------
_paths = Paths.discover()

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
    mode: str = "standard_analysis"
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
        runs_dir = _paths.runs_dir
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
        processed_dir = _paths.data_dir / "processed"
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
        mode = "standard_analysis"
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
            model=os.environ.get("OPENAI_MODEL", DEFAULT_MODEL),
        )
        self._run_paths = RunPaths.from_output(latest_dir)
        logger.info("Restored last run: %s (mode=%s, dir=%s)", run_id, mode, latest_dir)

    def _read_cached_artifact(self, path: str) -> Any:
        """读取产物文件，带 mtime 缓存。"""
        if not os.path.exists(path):
            return None
        try:
            mtime = os.path.getmtime(path)
            with self._lock:
                if path in self._artifact_cache and self._artifact_cache_mtime.get(path) == mtime:
                    return self._artifact_cache[path]
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            with self._lock:
                self._artifact_cache[path] = data
                self._artifact_cache_mtime[path] = mtime
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read cached artifact %s: %s", path, exc)
            with self._lock:
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
        resolved = _validate_path_within(value, _PROJECT_ROOT / "data" / "runs", "continueFrom")
        return str(resolved)
    def start(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if self._state.status == "running":
                return {"error": "A pipeline run is already in progress"}
            run_id = uuid.uuid4().hex[:12]
            input_path = str(payload.get("inputPath", "")).strip()
            if not input_path:
                return {"error": "inputPath is required"}
            try:
                _validate_path_within(input_path, _PROJECT_ROOT, "inputPath")
            except ValueError as ve:
                return {"error": str(ve)}
            if not input_path.endswith(".txt"):
                return {"error": "inputPath must be a .txt file"}
            if not Path(input_path).exists():
                return {"error": f"Input file not found: {input_path}"}
            if not os.environ.get("OPENAI_API_KEY"):
                return {"error": "OPENAI_API_KEY environment variable is not set"}
            valid_modes = {"standard_analysis"}
            mode = payload.get("mode", "standard_analysis")
            if mode not in valid_modes:
                return {"error": f"Invalid mode: {mode}. Must be one of {valid_modes}"}
            model = payload.get("model") or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
            project_name = payload.get("projectName", "") or Path(input_path).stem
            output_base = payload.get("outputDir") or str(_paths.runs_dir)
            try:
                _validate_path_within(str(Path(output_base).resolve()), _PROJECT_ROOT / "data", "outputDir")
            except ValueError as ve:
                return {"error": str(ve)}
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
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY not set")
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

            # --- Narrative analysis (Layer 1 + Layer 2) ---
            try:
                from .narrative_analyzer import run_narrative_analysis
                from .config import Paths
                from .schema_validator import SchemaValidator
                paths = Paths.discover()
                validator = SchemaValidator(paths.schemas_dir)
                ok_chapters = [ch for ch in result.get("chapters", []) if ch.get("status") == "ok"]
                genre_dict = result.get("genre", {})
                if ok_chapters:
                    narrative_result = run_narrative_analysis(
                        chapter_results=ok_chapters,
                        genre=genre_dict,
                        client=client,
                        paths=paths,
                        validator=validator,
                        cache=cache,
                        logger=run_log,
                        stats=sa_stats,
                    )
                    save_json(narrative_result.to_dict(), Path(st.output_dir) / "narrative_output.json")
                    logger.info("Narrative analysis completed: run_id=%s", st.run_id)
            except Exception:
                logger.exception("Narrative analysis failed (non-fatal)")

            with self._lock:
                self._state.status = "completed"
                self._state.updated_at = _utc_now()
            logger.info("Standard analysis completed: run_id=%s output=%s", st.run_id, st.output_dir)
        except Exception:
            logger.exception("Pipeline failed")
            with self._lock:
                self._state.status = "failed"
                logger.error("Pipeline failed: %s", _tb_mod.format_exc())


                self._state.error = f"{type(e).__name__}: {e}"
                self._state.updated_at = _utc_now()

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
_book_index = BookIndex()


# ---------------------------------------------------------------------------
# Data readers (read from artifacts on disk)
# ---------------------------------------------------------------------------
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
    # Tail-read: only load the last chunk instead of the entire file
    items: list[dict[str, Any]] = []
    try:
        file_size = log_path.stat().st_size
        if file_size == 0:
            return []
        chunk_size = 8192
        lines: list[str] = []
        with open(log_path, "rb") as fh:
            # Read backwards in chunks until we have enough lines
            pos = file_size
            tail_buf = b""
            while pos > 0 and len(lines) < limit + 1:
                read_size = min(chunk_size, pos)
                pos -= read_size
                fh.seek(pos)
                tail_buf = fh.read(read_size) + tail_buf
                lines = tail_buf.decode("utf-8", errors="replace").strip().splitlines()
            # Keep only the last 'limit' lines
            lines = lines[-limit:]
        for line in lines:
            line = line.strip()
            if not line:
                continue
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
        "model": st.model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL),
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


def _read_narrative_analysis(mgr: RunManager) -> dict | None:
    """Read narrative analysis result from narrative_output.json."""
    st = mgr.state
    if not st.output_dir:
        return None
    path = Path(st.output_dir) / "narrative_output.json"
    if not path.exists():
        return None
    try:
        return mgr._read_cached_artifact(str(path))
    except Exception:
        return None


def _list_runs() -> list[dict[str, Any]]:
    """List all completed runs in data/runs/ with checkpoint availability."""
    runs_dir = _paths.runs_dir
    if not runs_dir.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for d in sorted(runs_dir.iterdir()):
        if not d.is_dir():
            continue
        # Check for book_result or book_output to confirm it's a valid run
        has_result = (d / "artifacts" / "book_result.json").exists() or (d / "book_output.json").exists()
        # Check for standard_analysis artifacts
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
            # Try chapter_index.json
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
            mode = "standard_analysis"
        elif has_result:
            mode = "standard_analysis"
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


def _read_exports_standard(mgr: RunManager) -> list[dict[str, Any]]:
    """List export files for standard_analysis mode."""
    if not mgr.run_paths:
        return []
    out_dir = Path(mgr.state.output_dir)
    items = []
    sa_path = out_dir / "standard_output.json"
    items.append({
        "id": "standard_output",
        "label": "标准分析结果",
        "format": "json",
        "path": str(sa_path),
        "exists": sa_path.exists(),
        "description": "标准分析完整输出（体裁、章节、事件、评分）",
    })
    na_path = out_dir / "narrative_output.json"
    items.append({
        "id": "narrative_output",
        "label": "叙事分析结果",
        "format": "json",
        "path": str(na_path),
        "exists": na_path.exists(),
        "description": "分层叙事分析（分组摘要 + 全书综合）",
    })
    return items

class ApiHandler(BaseHTTPRequestHandler):
    server_version = "HistoryApi/0.2"

    def log_message(self, format: str, *args: Any) -> None:
        logger.info("%s %s", self.address_string(), format % args)

    def log_error(self, format: str, *args: Any) -> None:
        logger.error("%s %s", self.address_string(), format % args)

    def _check_auth(self) -> bool:
        return True
        self.wfile.write(data)
        return False

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        if not self._check_auth():
            return
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
            self._send_standard_dashboard(mgr)
            return
        if path == "/api/results/characters":
            self._send_standard_characters(mgr)
            return
        ch_match = re.match(r"^/api/results/characters/(.+)$", path)
        if ch_match:
            cid = unquote(ch_match.group(1))
            self._send_standard_character_detail(mgr, cid)
            return
        if path == "/api/results/timeline":
            self._send_standard_timeline(mgr)
            return
        if path == "/api/results/exports":
            self._send_json(_read_exports_standard(mgr))
            return
        if path == "/api/results/failures":
            self._send_json(_read_failures(mgr))
            return
        if path == "/api/results/logs":
            self._send_json(_read_logs(mgr))
            return
        if path in ("/api/settings", "/api/results/settings"):
            self._send_json(_read_settings(mgr))
            return
        if path == "/api/results/standard-analysis":
            data = _read_standard_analysis(mgr)
            if data:
                self._send_json(_camelize(data))
            else:
                self._send_json({"error": "No standard analysis data"}, status=HTTPStatus.NOT_FOUND)
            return
        # ORPHAN: No frontend consumer, preserved for future use
        if path == "/api/scan/overview":
            self._send_standard_overview(mgr)
            return
        # ORPHAN: No frontend consumer, preserved for future use
        if path == "/api/scan/segments":
            self._send_standard_segments(mgr)
            return
        seg_match = re.match(r"^/api/scan/segments/(.+)$", path)
        if seg_match:
            self._send_standard_segment(mgr, seg_match.group(1))
            return
        # ORPHAN: No frontend consumer, preserved for future use
        if path == "/api/scan/key-chapters":
            self._send_standard_key_chapters(mgr)
            return
        # ORPHAN: No frontend consumer, preserved for future use
        if path == "/api/scan/reading-guide":
            self._send_standard_reading_guide(mgr)
            return
        # ORPHAN: No frontend consumer, preserved for future use
        if path == "/api/scan/chapter-index":
            self._send_standard_chapter_index(mgr)
            return
        # ORPHAN: No frontend consumer, preserved for future use
        if path == "/api/scan/stats":
            self._send_standard_stats(mgr)
            return
        if path == "/api/results/narrative":
            data = _read_narrative_analysis(mgr)
            if data:
                self._send_json(_camelize(data))
            else:
                self._send_json({"error": "No narrative analysis data"}, status=HTTPStatus.NOT_FOUND)
            return
        if path == "/api/results/narrative/groups":
            data = _read_narrative_analysis(mgr)
            if data:
                self._send_json(_camelize(data.get("group_summaries", [])))
            else:
                self._send_json({"error": "No narrative analysis data"}, status=HTTPStatus.NOT_FOUND)
            return
        if path == "/api/results/narrative/synthesis":
            data = _read_narrative_analysis(mgr)
            if data and data.get("book_synthesis"):
                self._send_json(_camelize(data["book_synthesis"]))
            else:
                self._send_json({"error": "No book synthesis data"}, status=HTTPStatus.NOT_FOUND)
            return
        if path == "/api/results/chapter-analysis":
            data = _read_standard_analysis(mgr)
            if data:
                self._send_json(data)
            else:
                self._send_json({"error": "No data"}, status=HTTPStatus.NOT_FOUND)
            return

        # -- Book API --
        if path == "/api/books":
            self._send_json(_book_index.list_books())
            return
        book_match = re.match(r"^/api/books/([^/]+)$", path)
        if book_match:
            book_id = unquote(book_match.group(1))
            data = _book_index.get_book(book_id)
            if data:
                self._send_json(data)
            else:
                self._send_json({"error": "Book not found"}, status=HTTPStatus.NOT_FOUND)
            return
        book_chapters_match = re.match(r"^/api/books/([^/]+)/chapters$", path)
        if book_chapters_match:
            book_id = unquote(book_chapters_match.group(1))
            data = _book_index.get_chapters(book_id)
            if data is not None:
                self._send_json(data)
            else:
                self._send_json({"error": "Book not found or no chapters"}, status=HTTPStatus.NOT_FOUND)
            return
        book_chapter_detail_match = re.match(r"^/api/books/([^/]+)/chapters/([^/]+)$", path)
        if book_chapter_detail_match:
            book_id = unquote(book_chapter_detail_match.group(1))
            chapter_id = unquote(book_chapter_detail_match.group(2))
            data = _book_index.get_chapter_detail(book_id, chapter_id)
            if data:
                self._send_json(data)
            else:
                self._send_json({"error": "Chapter not found"}, status=HTTPStatus.NOT_FOUND)
            return
        book_analysis_match = re.match(r"^/api/books/([^/]+)/analysis/latest$", path)
        if book_analysis_match:
            book_id = unquote(book_analysis_match.group(1))
            data = _book_index.get_latest_analysis(book_id)
            if data:
                self._send_json(data)
            else:
                self._send_json({"error": "No analysis found for this book"}, status=HTTPStatus.NOT_FOUND)
            return

        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if not self._check_auth():
            return
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
            if path == "/api/crawl/inspect":
                book_url = payload.get("book_url", "").strip()
                if not book_url:
                    self._send_json({"error": "book_url is required"}, status=HTTPStatus.BAD_REQUEST)
                    return
                preview = inspect_novel_book(book_url)
                self._send_json(asdict(preview))
                return
            if path == "/api/crawl/export":
                book_url = payload.get("book_url", "").strip()
                if not book_url:
                    self._send_json({"error": "book_url is required"}, status=HTTPStatus.BAD_REQUEST)
                    return
                chapter_start = payload.get("chapter_start")
                chapter_end = payload.get("chapter_end")
                context_before = payload.get("context_before_chapters", 0)
                output_dir = payload.get("output_dir", str(_paths.exports_dir))
                # Only crawl the needed range instead of the entire book
                effective_start = chapter_start or 1
                effective_end = chapter_end
                crawl_start = max(1, effective_start - context_before)
                crawl_limit = (effective_end - crawl_start + 1) if effective_end is not None else None
                book = crawl_novel_book(book_url, start=crawl_start, limit=crawl_limit)
                # In the crawled slice, context = first N chapters, selected = the rest
                ctx_count = effective_start - crawl_start
                context_chapters = book.chapters[:ctx_count]
                selected_chapters = book.chapters[ctx_count:]
                safe_title = "".join(c for c in (book.title or "book") if c.isalnum() or c in " _-")[:60].strip() or "book"
                out_dir = Path(output_dir)
                text_path = out_dir / f"{safe_title}.txt"
                json_path = out_dir / f"{safe_title}.json"
                save_selected_chapters(book, context_chapters, selected_chapters, text_path, json_path)
                self._send_json({
                    "title": book.title,
                    "author": book.author,
                    "selected_start": chapter_start,
                    "selected_end": chapter_end,
                    "context_count": len(context_chapters),
                    "selected_count": len(selected_chapters),
                    "text_output": str(text_path),
                    "json_output": str(json_path),
                    "selected_titles": [ch.title for ch in selected_chapters],
                })
                return
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            logger.exception("POST %s failed: %s", path, exc)
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    # -- crawl handlers (preserved from original) --
    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY_SIZE:
            raise ValueError(f"Request body too large: {length} bytes (max {MAX_BODY_SIZE})")
        body = self.rfile.read(min(length, MAX_BODY_SIZE)) if length else b"{}"
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
        origin = self.headers.get("Origin")
        allowed = _check_cors_origin(origin)
        if allowed:
            self.send_header("Access-Control-Allow-Origin", allowed)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
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
    _init_cors()
    token = _init_token()
    logger.info("API Token: %s", token)
    print("  API Token:", token)
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
