from __future__ import annotations

import logging
import re
from pathlib import Path

MAX_VARIABLE_LENGTH = 100_000  # 100K chars

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")

log = logging.getLogger(__name__)


def load_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def render_prompt(template: str, **variables: str) -> str:
    rendered = template
    for key, value in variables.items():
        if key == "text" and len(value) > MAX_VARIABLE_LENGTH:
            value = value[:MAX_VARIABLE_LENGTH] + "\n[...truncated...]"
        rendered = rendered.replace(f"{{{{{key}}}}}", value)

    leftover = _PLACEHOLDER_RE.findall(rendered)
    if leftover:
        log.warning("render_prompt: unreplaced placeholders remain: %s", leftover)

    return rendered
