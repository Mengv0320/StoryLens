from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    root: Path
    prompts_dir: Path
    schemas_dir: Path

    @classmethod
    def discover(cls) -> "Paths":
        root = Path(__file__).resolve().parent.parent
        return cls(
            root=root,
            prompts_dir=root / "prompts",
            schemas_dir=root / "schemas",
        )


@dataclass
class ModelConfig:
    """Per-stage model configuration. All fields default to None, meaning use the global model."""
    genre_model: str | None = None
    genre_base_url: str | None = None
    extraction_model: str | None = None
    extraction_base_url: str | None = None
    analysis_model: str | None = None
    analysis_base_url: str | None = None
    summary_model: str | None = None
    summary_base_url: str | None = None

    def resolve(self, stage: str, default_model: str, default_base_url: str | None = None) -> tuple[str, str | None]:
        """Return (model, base_url) for a given stage."""
        stage_map: dict[str, tuple[str | None, str | None]] = {
            "genre": (self.genre_model, self.genre_base_url),
            "scene_split": (self.extraction_model, self.extraction_base_url),
            "scene_extraction": (self.extraction_model, self.extraction_base_url),
            "normalized_events": (self.analysis_model, self.analysis_base_url),
            "causal_analysis": (self.analysis_model, self.analysis_base_url),
            "scores": (self.analysis_model, self.analysis_base_url),
            "episode": (self.summary_model, self.summary_base_url),
        }
        model, base_url = stage_map.get(stage, (None, None))
        return (model or default_model, base_url or default_base_url)

