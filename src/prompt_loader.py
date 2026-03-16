from __future__ import annotations

from pathlib import Path


def load_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def render_prompt(template: str, **variables: str) -> str:
    rendered = template
    for key, value in variables.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered

