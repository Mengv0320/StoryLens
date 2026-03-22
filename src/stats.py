from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LLMCallRecord:
    stage: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    duration_seconds: float = 0.0
    model: str = ""
    chapter_id: str = ""
    episode_id: str = ""


@dataclass
class StageSummary:
    stage: str
    call_count: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_duration_seconds: float = 0.0


# Default token prices (USD per token). Override by passing custom `token_prices`
# dict to PipelineStats(). Keys: "prompt", "completion".
DEFAULT_TOKEN_PRICES: dict[str, float] = {
    "prompt": 0.15 / 1_000_000,
    "completion": 0.60 / 1_000_000,
}


class PipelineStats:
    """Tracks per-LLM-call token usage and per-stage timing."""

    def __init__(
        self,
        token_prices: dict[str, float] | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self.records: list[LLMCallRecord] = []
        self.token_prices = token_prices or DEFAULT_TOKEN_PRICES
        self._stage_timers: dict[str, float] = {}

    def record_call(
        self,
        stage: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        duration_seconds: float,
        model: str = "",
        chapter_id: str = "",
        episode_id: str = "",
    ) -> None:
        with self._lock:
            self.records.append(LLMCallRecord(
                stage=stage,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                duration_seconds=duration_seconds,
                model=model,
                chapter_id=chapter_id,
                episode_id=episode_id,
            ))

    def start_stage_timer(self, stage: str) -> None:
        with self._lock:
            self._stage_timers[stage] = time.monotonic()

    def stop_stage_timer(self, stage: str) -> float:
        with self._lock:
            start = self._stage_timers.pop(stage, None)
        if start is None:
            return 0.0
        return time.monotonic() - start

    def aggregate_by_stage(self) -> list[StageSummary]:
        stage_data: dict[str, StageSummary] = {}
        for rec in self.records:
            if rec.stage not in stage_data:
                stage_data[rec.stage] = StageSummary(stage=rec.stage)
            s = stage_data[rec.stage]
            s.call_count += 1
            s.total_prompt_tokens += rec.prompt_tokens
            s.total_completion_tokens += rec.completion_tokens
            s.total_tokens += rec.total_tokens
            s.total_duration_seconds += rec.duration_seconds
        return list(stage_data.values())

    def aggregate_by_chapter(self) -> dict[str, StageSummary]:
        chapter_data: dict[str, StageSummary] = {}
        for rec in self.records:
            key = rec.chapter_id or "global"
            if key not in chapter_data:
                chapter_data[key] = StageSummary(stage=key)
            s = chapter_data[key]
            s.call_count += 1
            s.total_prompt_tokens += rec.prompt_tokens
            s.total_completion_tokens += rec.completion_tokens
            s.total_tokens += rec.total_tokens
            s.total_duration_seconds += rec.duration_seconds
        return chapter_data

    def aggregate_by_episode(self) -> dict[str, StageSummary]:
        episode_data: dict[str, StageSummary] = {}
        for rec in self.records:
            key = rec.episode_id or "global"
            if key not in episode_data:
                episode_data[key] = StageSummary(stage=key)
            s = episode_data[key]
            s.call_count += 1
            s.total_prompt_tokens += rec.prompt_tokens
            s.total_completion_tokens += rec.completion_tokens
            s.total_tokens += rec.total_tokens
            s.total_duration_seconds += rec.duration_seconds
        return episode_data

    def estimate_cost(self) -> dict[str, float]:
        total_prompt = sum(r.prompt_tokens for r in self.records)
        total_completion = sum(r.completion_tokens for r in self.records)
        prompt_cost = total_prompt * self.token_prices.get("prompt", 0.0)
        completion_cost = total_completion * self.token_prices.get("completion", 0.0)
        return {
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "total_tokens": total_prompt + total_completion,
            "prompt_cost_usd": round(prompt_cost, 6),
            "completion_cost_usd": round(completion_cost, 6),
            "total_cost_usd": round(prompt_cost + completion_cost, 6),
        }

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            records_snap = list(self.records)
        # Serialize from snapshot so we don't hold the lock during heavy work.
        # aggregate_*/estimate_cost already iterate self.records without mutation,
        # so a shallow copy is sufficient.
        return {
            "calls": [asdict(r) for r in records_snap],
            "by_stage": [asdict(s) for s in self.aggregate_by_stage()],
            "by_chapter": {k: asdict(v) for k, v in self.aggregate_by_chapter().items()},
            "by_episode": {k: asdict(v) for k, v in self.aggregate_by_episode().items()},
            "cost_estimate": self.estimate_cost(),
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
