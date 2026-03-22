"""Book-centric data types for the book index layer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BookMeta:
    """Metadata for a single book, aggregated from exports and runs."""
    book_id: str  # book fingerprint (SHA256[:16])
    title: str = ""
    author: str = ""
    source_url: str = ""
    chapter_count: int = 0
    latest_run_id: str = ""
    latest_run_dir: str = ""
    latest_mode: str = ""
    latest_status: str = ""
    runs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        # Sanitize runs: strip disk paths (runDir) before exposing via API
        sanitized_runs = [
            {k: v for k, v in r.items() if k != "runDir"}
            for r in self.runs
        ]
        return {
            "bookId": self.book_id,
            "title": self.title,
            "author": self.author,
            "sourceUrl": self.source_url,
            "chapterCount": self.chapter_count,
            "latestRunId": self.latest_run_id,
            "latestMode": self.latest_mode,
            "latestStatus": self.latest_status,
            "runs": sanitized_runs,
        }
