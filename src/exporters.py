from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, Protocol


class Exporter(Protocol):
    """Protocol for export implementations."""

    def export(self, data: dict[str, Any], output_dir: Path) -> list[Path]:
        """Export data to output_dir. Return list of created file paths."""
        ...


class JSONExporter:
    """Default JSON export (current behavior)."""

    def export(self, data: dict[str, Any], output_dir: Path) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        created: list[Path] = []

        main_path = output_dir / "book_output.json"
        main_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        created.append(main_path)

        for key in ("chapters", "episodes", "episode_plan", "failures"):
            items = data.get(key, [])
            if items:
                path = output_dir / f"{key}.jsonl"
                lines = [json.dumps(item, ensure_ascii=False) for item in items]
                path.write_text("\n".join(lines), encoding="utf-8")
                created.append(path)

        return created


class MarkdownExporter:
    """Export a readable Markdown report."""

    def export(self, data: dict[str, Any], output_dir: Path) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []

        episodes = data.get("episodes", [])
        chapters = data.get("chapters", [])
        failures = data.get("failures", [])

        lines.append(f"# Novel Pipeline Report")
        lines.append("")
        lines.append(f"- Chapters processed: {len(chapters)}")
        lines.append(f"- Episodes generated: {len(episodes)}")
        if failures:
            lines.append(f"- Failures: {len(failures)}")
        lines.append("")

        for ep in episodes:
            episode = ep.get("episode", {})
            lines.append(f"## {episode.get('title', ep.get('episode_id', 'Untitled'))}")
            lines.append("")
            chapter_titles = ep.get("chapter_titles", [])
            if chapter_titles:
                lines.append(f"**Chapters:** {', '.join(chapter_titles)}")
                lines.append("")
            if episode.get("core_theme"):
                lines.append(f"**Theme:** {episode['core_theme']}")
            if episode.get("main_conflict"):
                lines.append(f"**Conflict:** {episode['main_conflict']}")
            if episode.get("climax"):
                lines.append(f"**Climax:** {episode['climax']}")
            if episode.get("episode_summary"):
                lines.append("")
                lines.append(episode["episode_summary"])
            if episode.get("ending_hook"):
                lines.append("")
                lines.append(f"> **Hook:** {episode['ending_hook']}")
            lines.append("")

            key_events = episode.get("key_events", [])
            if key_events:
                lines.append("### Key Events")
                for ke in key_events:
                    lines.append(f"- {ke}")
                lines.append("")

        path = output_dir / "report.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return [path]


class CSVExporter:
    """Export normalized events as a CSV table."""

    def export(self, data: dict[str, Any], output_dir: Path) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        created: list[Path] = []

        rows: list[dict[str, Any]] = []
        chapters = data.get("chapters", [])
        for chapter in chapters:
            chapter_info = chapter.get("chapter", {})
            chapter_id = chapter_info.get("chapter_id", "")
            chapter_title = chapter_info.get("title", "")
            normalized = chapter.get("normalized_events", {})
            score_map: dict[str, dict[str, Any]] = {}
            for se in chapter.get("scores", []):
                score_map[se.get("event_id", "")] = se
            for event in normalized.get("events", []):
                eid = event.get("event_id", "")
                scores = score_map.get(eid, {})
                rows.append({
                    "chapter_id": chapter_id,
                    "chapter_title": chapter_title,
                    "event_id": eid,
                    "event_group": event.get("event_group", ""),
                    "event_type": event.get("event_type", ""),
                    "title": event.get("title", ""),
                    "description": event.get("description", ""),
                    "characters": "; ".join(event.get("characters", [])),
                    "main_plot_score": scores.get("main_plot_score", ""),
                    "climax_score": scores.get("climax_score", ""),
                    "suspense_score": scores.get("suspense_score", ""),
                    "must_keep": scores.get("must_keep", ""),
                })

        if rows:
            path = output_dir / "events.csv"
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
            path.write_text(buf.getvalue(), encoding="utf-8")
            created.append(path)

        return created


class APIExporter:
    """Export data in flat API-friendly JSON formats."""

    def export(self, data: dict[str, Any], output_dir: Path) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        created: list[Path] = []

        episodes_flat = self._build_episode_list(data)
        path = output_dir / "api_episodes.json"
        path.write_text(json.dumps(episodes_flat, ensure_ascii=False, indent=2), encoding="utf-8")
        created.append(path)

        characters = self._build_character_data(data)
        path = output_dir / "api_characters.json"
        path.write_text(json.dumps(characters, ensure_ascii=False, indent=2), encoding="utf-8")
        created.append(path)

        timeline = self._build_timeline(data)
        path = output_dir / "api_timeline.json"
        path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
        created.append(path)

        return created

    def _build_episode_list(self, data: dict[str, Any]) -> dict[str, Any]:
        episodes = data.get("episodes", [])
        items = []
        for ep in episodes:
            episode = ep.get("episode", {})
            items.append({
                "episode_id": ep.get("episode_id", ""),
                "title": episode.get("title", ""),
                "core_theme": episode.get("core_theme", ""),
                "main_conflict": episode.get("main_conflict", ""),
                "climax": episode.get("climax", ""),
                "episode_summary": episode.get("episode_summary", ""),
                "chapter_ids": ep.get("chapter_ids", []),
            })
        return {"total": len(items), "episodes": items}

    def _build_character_data(self, data: dict[str, Any]) -> dict[str, Any]:
        character_events: dict[str, list[str]] = {}
        chapters = data.get("chapters", [])
        for chapter in chapters:
            normalized = chapter.get("normalized_events", {})
            for event in normalized.get("events", []):
                for char in event.get("characters", []):
                    character_events.setdefault(char, []).append(event.get("event_id", ""))

        characters = []
        for name, event_ids in sorted(character_events.items()):
            characters.append({
                "name": name,
                "event_count": len(event_ids),
                "event_ids": sorted(set(event_ids)),
            })
        aliases = data.get("aliases", {})
        return {"total": len(characters), "characters": characters, "aliases": aliases}

    def _build_timeline(self, data: dict[str, Any]) -> dict[str, Any]:
        timeline: list[dict[str, Any]] = []
        chapters = data.get("chapters", [])
        for chapter in chapters:
            chapter_info = chapter.get("chapter", {})
            chapter_id = chapter_info.get("chapter_id", "")
            normalized = chapter.get("normalized_events", {})
            for event in normalized.get("events", []):
                timeline.append({
                    "chapter_id": chapter_id,
                    "event_id": event.get("event_id", ""),
                    "event_group": event.get("event_group", ""),
                    "event_type": event.get("event_type", ""),
                    "title": event.get("title", ""),
                    "characters": event.get("characters", []),
                })
        return {"total": len(timeline), "events": timeline}


EXPORTERS: dict[str, type] = {
    "json": JSONExporter,
    "markdown": MarkdownExporter,
    "csv": CSVExporter,
    "api": APIExporter,
}


def get_exporter(name: str) -> Exporter:
    cls = EXPORTERS.get(name)
    if cls is None:
        raise ValueError(f"Unknown export format: {name!r}. Available: {', '.join(EXPORTERS)}")
    return cls()
