"""Book index: scans disk to build book-centric view over runs."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .book_types import BookMeta

logger = logging.getLogger(__name__)


from .serialization import camelize as _camelize

class BookIndex:
    """Scans data/runs/ and data/exports/ to build a book_id -> BookMeta mapping.

    book_id is derived from the run directory name: ``{project}_{fingerprint}``.
    The last ``_``-separated segment that looks like a hex hash is treated as the
    book fingerprint.  Metadata (title/author) is enriched from export JSON files
    in data/exports/ when available.
    """

    def __init__(self, runs_dir: str | Path = "data/runs",
                 exports_dir: str | Path = "data/exports") -> None:
        self._runs_dir = Path(runs_dir)
        self._exports_dir = Path(exports_dir)
        self._books: dict[str, BookMeta] = {}
        self._last_scan_mtime: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_books(self) -> list[dict[str, Any]]:
        """Return list of all books (auto-refreshes if disk changed)."""
        self._maybe_refresh()
        return [b.to_dict() for b in self._books.values()]

    def get_book(self, book_id: str) -> dict[str, Any] | None:
        """Return single book detail by book_id."""
        self._maybe_refresh()
        meta = self._books.get(book_id)
        return meta.to_dict() if meta else None

    def get_latest_run_dir(self, book_id: str) -> Path | None:
        """Return the latest run directory Path for a book."""
        self._maybe_refresh()
        meta = self._books.get(book_id)
        if meta and meta.latest_run_dir:
            p = Path(meta.latest_run_dir)
            if p.is_dir():
                return p
        return None

    def get_chapters(self, book_id: str) -> list[dict[str, Any]] | None:
        """Return chapter list from the latest run."""
        run_dir = self.get_latest_run_dir(book_id)
        if not run_dir:
            return None
            
        chapters = []
        has_standard = (run_dir / "standard_output.json").exists()
        if has_standard:
            data = self._read_standard_output(run_dir)
            if data:
                for ch in data.get("chapters", []):
                    chapters.append({
                        "chapterId": ch.get("chapter_id", ""),
                        "title": ch.get("title", ""),
                        "status": ch.get("status", ""),
                        "importanceScore": ch.get("importance_score", 0),
                        "importanceReason": ch.get("importance_reason", ""),
                        "eventCount": len(ch.get("key_events", [])),
                    })
                return chapters
                
        # Fallback to stream reading index
        idx_path = run_dir / "artifacts" / "chapters_index.json"
        if idx_path.exists():
            try:
                idx_list = json.loads(idx_path.read_text(encoding="utf-8"))
                for entry in idx_list:
                    cid = entry.get("chapter_id", "")
                    title = entry.get("title", "")
                    ch_path = run_dir / "artifacts" / "chapters" / f"{cid}.json"
                    
                    status = "pending"
                    importance_score = 0
                    importance_reason = ""
                    event_count = 0
                    
                    if ch_path.exists():
                        try:
                            ch_data = json.loads(ch_path.read_text(encoding="utf-8"))
                            status = ch_data.get("status", "ok")
                            importance_score = ch_data.get("importance_score", 0)
                            importance_reason = ch_data.get("importance_reason", "")
                            event_count = len(ch_data.get("key_events", []))
                        except (json.JSONDecodeError, OSError):
                            status = "error"
                            
                    chapters.append({
                        "chapterId": cid,
                        "title": title,
                        "status": status,
                        "importanceScore": importance_score,
                        "importanceReason": importance_reason,
                        "eventCount": event_count,
                    })
                return chapters
            except (json.JSONDecodeError, OSError):
                pass
                
        return None

    def get_chapter_detail(self, book_id: str, chapter_id: str) -> dict[str, Any] | None:
        """Return full chapter data including key_events and raw text if available."""
        run_dir = self.get_latest_run_dir(book_id)
        if not run_dir:
            return None
        data = self._read_standard_output(run_dir)
        if not data:
            return None
        for ch in data.get("chapters", []):
            if ch.get("chapter_id") == chapter_id:
                return _camelize(ch)
        return None

    def get_latest_analysis(self, book_id: str) -> dict[str, Any] | None:
        """Return the full latest analysis result for a book."""
        run_dir = self.get_latest_run_dir(book_id)
        if not run_dir:
            return None
        data = self._read_standard_output(run_dir)
        if not data:
            return None
        result = _camelize(data)
        # Enrich with book metadata
        meta = self._books.get(book_id)
        if meta:
            result["bookId"] = meta.book_id
            result["title"] = meta.title
            result["author"] = meta.author
        return result

    def get_latest_narrative(self, book_id: str) -> dict[str, Any] | None:
        """Return narrative_output.json for the latest run of a book."""
        run_dir = self.get_latest_run_dir(book_id)
        if not run_dir:
            return None
        path = run_dir / "narrative_output.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _maybe_refresh(self) -> None:
        """Re-scan if runs directory or any immediate subdirectory mtime changed."""
        try:
            if not self._runs_dir.is_dir():
                current_mtime = 0.0
            else:
                # Check parent dir + all immediate child dirs for mtime changes.
                # A new file inside a child dir updates the child's mtime,
                # but not necessarily the parent's.
                mtimes = [self._runs_dir.stat().st_mtime]
                for child in self._runs_dir.iterdir():
                    if child.is_dir():
                        try:
                            mtimes.append(child.stat().st_mtime)
                        except OSError:
                            pass
                current_mtime = max(mtimes)
        except OSError:
            current_mtime = 0.0
        if current_mtime != self._last_scan_mtime or not self._books:
            self._scan()
            self._last_scan_mtime = current_mtime

    def _scan(self) -> None:
        """Full scan of runs and exports directories."""
        books: dict[str, BookMeta] = {}

        # 1. Scan runs
        if self._runs_dir.is_dir():
            for d in sorted(self._runs_dir.iterdir()):
                if not d.is_dir():
                    continue
                fingerprint, project_name = self._parse_run_dir_name(d.name)
                if not fingerprint:
                    continue
                # Use project_name as book_id so same-title runs merge
                book_id = project_name
                # Check if this run has output
                has_standard = (d / "standard_output.json").exists()
                has_result = (d / "artifacts" / "book_result.json").exists()
                has_index = (d / "artifacts" / "chapters_index.json").exists()
                if not has_standard and not has_result and not has_index:
                    continue

                run_info = {
                    "runId": d.name,
                    "runDir": str(d.resolve()),
                    "hasStandard": has_standard,
                    "hasBookResult": has_result,
                    "hasIndex": has_index,
                }

                if book_id not in books:
                    books[book_id] = BookMeta(book_id=book_id, title=project_name)
                meta = books[book_id]
                meta.runs.append(run_info)

                # Use the latest run (sorted order = chronological by creation)
                meta.latest_run_id = d.name
                meta.latest_run_dir = str(d.resolve())
                meta.latest_mode = "standard_analysis" if has_standard or has_index else "book"
                meta.latest_status = "completed" if has_standard or has_result else "running"

                # Read chapter count (lightweight — avoid full JSON parse)
                if has_standard:
                    meta.chapter_count = self._count_chapters_fast(d / "standard_output.json")
                elif has_index:
                    try:
                        idx_list = json.loads((d / "artifacts" / "chapters_index.json").read_text(encoding="utf-8"))
                        meta.chapter_count = len(idx_list)
                    except (json.JSONDecodeError, OSError):
                        pass

        # 2. Enrich from exports
        self._enrich_from_exports(books)

        # 3. Also try book_meta.json in run dirs
        for meta in books.values():
            if meta.latest_run_dir and not meta.title:
                bm_path = Path(meta.latest_run_dir) / "book_meta.json"
                if bm_path.exists():
                    try:
                        bm = json.loads(bm_path.read_text(encoding="utf-8"))
                        meta.title = bm.get("title", meta.title)
                        meta.author = bm.get("author", meta.author)
                        meta.source_url = bm.get("source_url", meta.source_url)
                    except (json.JSONDecodeError, OSError):
                        pass

        self._books = books

    def _enrich_from_exports(self, books: dict[str, BookMeta]) -> None:
        """Try to fill in title/author/source_url from export JSON files."""
        if not self._exports_dir.is_dir():
            return
        # Build project_name -> book_id lookup
        project_to_bid: dict[str, str] = {}
        for bid, meta in books.items():
            for run in meta.runs:
                run_id = run.get("runId", "")
                if "_" in run_id:
                    proj = run_id.rsplit("_", 1)[0]
                    project_to_bid[proj] = bid
        for p in self._exports_dir.glob("*.json"):
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            title = raw.get("title", "")
            author = raw.get("author", "")
            source_url = raw.get("source_url", "")
            if not title:
                continue
            stem = p.stem
            # Try exact match on export filename stem vs project names
            matched_bid = project_to_bid.get(stem)
            if not matched_bid:
                # Fuzzy: check if any project name is a prefix of the stem
                for proj, bid in project_to_bid.items():
                    if stem.startswith(proj) or proj.startswith(stem):
                        matched_bid = bid
                        break
            if matched_bid and matched_bid in books:
                meta = books[matched_bid]
                if not meta.title:
                    meta.title = title
                if not meta.author and author:
                    meta.author = author
                if not meta.source_url and source_url:
                    meta.source_url = source_url

    @staticmethod
    def _parse_run_dir_name(name: str) -> tuple[str, str]:
        """Extract (book_fingerprint, project_name) from run dir name.

        Convention: ``{project_name}_{hex_fingerprint}``
        Returns ("", "") if the name doesn't match.
        """
        if "_" not in name:
            return ("", "")
        parts = name.rsplit("_", 1)
        fingerprint = parts[1]
        project_name = parts[0]
        # Validate fingerprint looks like hex
        if len(fingerprint) >= 8 and all(c in "0123456789abcdef" for c in fingerprint):
            return (fingerprint, project_name)
        return ("", "")

    @staticmethod
    def _count_chapters_fast(path: Path) -> int:
        """Count chapters by parsing the top-level 'chapters' array length."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return len(data.get("chapters", []))
        except (json.JSONDecodeError, OSError):
            return 0

    @staticmethod
    def _read_standard_output(run_dir: Path) -> dict[str, Any] | None:
        """Read and parse standard_output.json from a run directory."""
        path = run_dir / "standard_output.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
