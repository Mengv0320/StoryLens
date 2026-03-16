from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


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


class StageCache:
    def __init__(self, cache_dir: Path, namespace: str) -> None:
        self.cache_dir = cache_dir
        self.namespace = namespace
        self.cache_dir.mkdir(parents=True, exist_ok=True)

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
