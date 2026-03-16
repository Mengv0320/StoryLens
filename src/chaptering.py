from __future__ import annotations

import re
from dataclasses import dataclass


DEFAULT_CHAPTER_PATTERN = r"(?m)^(第[0-9零一二三四五六七八九十百千万两]+章[^\n]*|Chapter\s+\d+[^\n]*|CHAPTER\s+\d+[^\n]*)\s*$"


@dataclass
class Chapter:
    chapter_id: str
    title: str
    text: str


def split_into_chapters(text: str, pattern: str = DEFAULT_CHAPTER_PATTERN) -> list[Chapter]:
    matches = list(re.finditer(pattern, text))
    if not matches:
        cleaned = text.strip()
        return [Chapter(chapter_id="chapter_001", title="Full Text", text=cleaned)] if cleaned else []

    chapters: list[Chapter] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        chunk = text[start:end].strip()
        title = match.group(0).strip()
        chapter_id = f"chapter_{index + 1:03d}"
        chapters.append(Chapter(chapter_id=chapter_id, title=title, text=chunk))
    return chapters
