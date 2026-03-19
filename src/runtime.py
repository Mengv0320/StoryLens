from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


PIPELINE_VERSION = "1"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_book_fingerprint(text: str) -> str:
    """Stable fingerprint for a book's content (first 16 hex chars of SHA-256)."""
    normalized = text.strip().replace("\r\n", "\n").replace("\r", "\n")
    return sha256(normalized.encode("utf-8")).hexdigest()[:16]


@dataclass
class RunPaths:
    output_dir: Path
    cache_dir: Path
    artifacts_dir: Path
    logs_dir: Path

    @classmethod
    def from_output(cls, output_path: Path) -> "RunPaths":
        output_dir = output_path if output_path.suffix == "" else output_path.parent
        return cls(
            output_dir=output_dir,
            cache_dir=output_dir / "cache",
            artifacts_dir=output_dir / "artifacts",
            logs_dir=output_dir / "logs",
        )

    def ensure(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_run_dir(cls, run_dir: Path) -> "RunPaths":
        """Reconstruct RunPaths from an existing run directory (for --resume)."""
        return cls(
            output_dir=run_dir,
            cache_dir=run_dir / "cache",
            artifacts_dir=run_dir / "artifacts",
            logs_dir=run_dir / "logs",
        )

    def completed_chapter_ids(self) -> set[str]:
        """Detect chapters already completed in a previous run (for resume)."""
        chapters_dir = self.artifacts_dir / "chapters"
        if not chapters_dir.exists():
            return set()
        completed: set[str] = set()
        for path in chapters_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("status") == "ok":
                    completed.add(path.stem)
            except (json.JSONDecodeError, OSError):
                continue
        return completed

    def load_chapter_results(self) -> list[dict[str, Any]]:
        """Load all completed chapter results from artifacts (for resume)."""
        chapters_dir = self.artifacts_dir / "chapters"
        if not chapters_dir.exists():
            return []
        results: list[dict[str, Any]] = []
        for path in sorted(chapters_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("status") == "ok":
                    results.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        return results


class StageCache:
    def __init__(self, cache_dir: Path, namespace: str) -> None:
        self.cache_dir = cache_dir
        self.namespace = namespace
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def for_book(cls, base_cache_dir: Path, book_fingerprint: str, model: str) -> "StageCache":
        """Create a book-level cache that persists across runs."""
        namespace = f"{book_fingerprint}:{model}:v{PIPELINE_VERSION}"
        cache_dir = base_cache_dir / "books" / book_fingerprint
        return cls(cache_dir=cache_dir, namespace=namespace)

    @classmethod
    def for_project(cls, base_cache_dir: Path, project_name: str, model: str) -> "StageCache":
        """Create a project-level cache that persists across runs."""
        namespace = f"project:{project_name}:{model}:v{PIPELINE_VERSION}"
        cache_dir = base_cache_dir / "projects" / project_name
        return cls(cache_dir=cache_dir, namespace=namespace)

    def get(self, stage: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        path = self._path_for(stage, payload)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def set(self, stage: str, payload: dict[str, Any], result: dict[str, Any]) -> None:
        path = self._path_for(stage, payload)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    def _path_for(self, stage: str, payload: dict[str, Any]) -> Path:
        digest = sha256(
            json.dumps(
                {
                    "namespace": self.namespace,
                    "stage": stage,
                    "payload": payload,
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return self.cache_dir / stage / f"{digest}.json"


class RunLogger:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, **fields: Any) -> None:
        record = {
            "timestamp": utc_timestamp(),
            "event": event,
            **fields,
        }
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_artifact(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_state_checkpoint(
    run_dir: Path,
    processed_chapters: list[str],
    chapter_order: list[str],
    knowledge_snapshot: dict[str, Any],
    causal_snapshot: dict[str, Any],
    alias_snapshot: dict[str, list[str]],
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Write a full state checkpoint for cross-run continuation."""
    checkpoint = {
        "version": 2,
        "created_at": utc_timestamp(),
        "pipeline_version": PIPELINE_VERSION,
        "processed_chapters": processed_chapters,
        "chapter_order": chapter_order,
        "knowledge": knowledge_snapshot,
        "causal": causal_snapshot,
        "aliases": alias_snapshot,
        "metadata": metadata or {},
    }
    path = run_dir / "knowledge" / "state_checkpoint.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_state_checkpoint(run_dir: Path) -> dict[str, Any] | None:
    """Load a state checkpoint from a previous run. Returns None if not found.

    Raises ValueError if the file exists but has an incompatible version.
    Returns None only when the checkpoint file does not exist.
    """
    path = run_dir / "knowledge" / "state_checkpoint.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Checkpoint file is corrupt: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Checkpoint file is not a JSON object: {path}")
    if data.get("version") != 2:
        raise ValueError(
            f"Checkpoint version mismatch: expected 2, got {data.get('version')} in {path}"
        )
    return data
