from __future__ import annotations

from dataclasses import dataclass
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

