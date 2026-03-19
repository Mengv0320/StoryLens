from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256


DEFAULT_CHAPTER_PATTERN = r"(?m)^(第[0-9零一二三四五六七八九十百千万两]+章[^\n]*|Chapter\s+\d+[^\n]*|CHAPTER\s+\d+[^\n]*)\s*$"


@dataclass
class Chapter:
    chapter_id: str
    title: str
    text: str
    sequence_index: int = 0


def compute_chapter_id(title: str, text: str) -> str:
    """Content-hash based stable chapter ID (survives re-splitting)."""
    key = f"{title.strip()}\n{text.strip()[:200]}"
    return f"ch_{sha256(key.encode('utf-8')).hexdigest()[:12]}"


def split_into_chapters(
    text: str,
    pattern: str = DEFAULT_CHAPTER_PATTERN,
    stable_ids: bool = False,
) -> list[Chapter]:
    matches = list(re.finditer(pattern, text))
    if not matches:
        cleaned = text.strip()
        if not cleaned:
            return []
        cid = compute_chapter_id("Full Text", cleaned) if stable_ids else "chapter_001"
        return [Chapter(chapter_id=cid, title="Full Text", text=cleaned, sequence_index=0)]

    chapters: list[Chapter] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        chunk = text[start:end].strip()
        title = match.group(0).strip()
        if stable_ids:
            chapter_id = compute_chapter_id(title, chunk)
        else:
            chapter_id = f"chapter_{index + 1:03d}"
        chapters.append(Chapter(chapter_id=chapter_id, title=title, text=chunk, sequence_index=index))
    return chapters
