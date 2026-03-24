"""Story Memory: rolling character/relationship/plot state that accumulates across chapters.

Provides dataclasses for structured memory, serialization helpers, prompt formatting,
character-alias normalization, and content hashing for cache keys.

Zero coupling with other src/ modules — depends only on the Python standard library.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CharacterProfile:
    """A tracked character's profile."""

    name: str                                          # 归一化主名（唯一标识）
    aliases: list[str] = field(default_factory=list)   # 绰号/称号/代称
    role: str = "minor"                                # protagonist | antagonist | supporting | minor
    faction: str = ""                                  # 所属势力/门派
    status: str = "alive"                              # alive | dead | missing | unknown
    power_level: str = ""                              # 当前境界/实力
    personality_traits: list[str] = field(default_factory=list)  # ≤5
    summary: str = ""                                  # 一句话概要（≤80字）
    last_seen_chapter: str = ""                        # 最后出现的章节 ID


@dataclass
class Relationship:
    """A directed relationship between two characters."""

    character_a: str          # 归一化主名
    character_b: str          # 归一化主名
    relation_type: str = "unknown"  # hostile|suspicious|allied|subordinate|mentor|family|romantic|rival|unknown
    description: str = ""     # 关系描述（≤50字）
    since_chapter: str = ""   # 关系建立/变化的章节 ID


@dataclass
class FactionInfo:
    """A tracked faction / organization."""

    name: str
    description: str = ""                              # 势力简介（≤80字）
    key_members: list[str] = field(default_factory=list)  # ≤10
    status: str = "active"                             # active | disbanded | destroyed | unknown


@dataclass
class PlotState:
    """Current plot/arc state."""

    current_arc: str = ""                              # 当前主线弧名称（≤30字）
    arc_summary: str = ""                              # 当前弧概要（≤150字）
    active_threads: list[str] = field(default_factory=list)        # ≤10
    unresolved_foreshadowing: list[str] = field(default_factory=list)  # ≤15
    recent_events_digest: str = ""                     # 最近剧情摘要（≤250字）


@dataclass
class StoryMemory:
    """Top-level rolling memory container."""

    characters: list[CharacterProfile] = field(default_factory=list)    # ≤30
    relationships: list[Relationship] = field(default_factory=list)     # ≤40
    factions: list[FactionInfo] = field(default_factory=list)           # ≤10
    plot_state: PlotState = field(default_factory=PlotState)
    last_chapter_id: str = ""
    last_chapter_title: str = ""
    total_chapters_processed: int = 0

    # -- serialization -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dict (snake_case keys)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoryMemory:
        """Deserialize from a dict. Missing/extra fields are tolerated."""
        if not isinstance(data, dict):
            return cls.empty()
        try:
            characters = [
                _safe_character(c) for c in data.get("characters", [])
                if isinstance(c, dict)
            ]
            relationships = [
                _safe_relationship(r) for r in data.get("relationships", [])
                if isinstance(r, dict)
            ]
            factions = [
                _safe_faction(f) for f in data.get("factions", [])
                if isinstance(f, dict)
            ]
            plot_raw = data.get("plot_state")
            plot_state = _safe_plot_state(plot_raw) if isinstance(plot_raw, dict) else PlotState()

            return cls(
                characters=characters,
                relationships=relationships,
                factions=factions,
                plot_state=plot_state,
                last_chapter_id=str(data.get("last_chapter_id", "")),
                last_chapter_title=str(data.get("last_chapter_title", "")),
                total_chapters_processed=_safe_int(data.get("total_chapters_processed", 0)),
            )
        except Exception as exc:
            _log.warning("StoryMemory.from_dict fallback to empty: %s", exc)
            return cls.empty()

    # -- persistence ----------------------------------------------------------

    def save(self, path: Path) -> None:
        """Atomically write memory JSON (write .tmp then rename)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, str(path))
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    @classmethod
    def load(cls, path: Path) -> StoryMemory:
        """Load from a JSON file. Returns empty() on missing / corrupt file."""
        path = Path(path)
        if not path.exists():
            return cls.empty()
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            return cls.from_dict(data)
        except Exception as exc:
            _log.warning("StoryMemory.load failed for %s: %s", path, exc)
            return cls.empty()

    @classmethod
    def empty(cls) -> StoryMemory:
        """Return a blank memory instance."""
        return cls(
            characters=[],
            relationships=[],
            factions=[],
            plot_state=PlotState(),
            last_chapter_id="",
            last_chapter_title="",
            total_chapters_processed=0,
        )


# ---------------------------------------------------------------------------
# Prompt formatting
# ---------------------------------------------------------------------------

# 角色 role 中英映射
_ROLE_LABELS: dict[str, str] = {
    "protagonist": "主角",
    "antagonist": "反派",
    "supporting": "配角",
    "minor": "路人",
}

# 角色 status 中英映射
_STATUS_LABELS: dict[str, str] = {
    "alive": "存活",
    "dead": "死亡",
    "missing": "失踪",
    "unknown": "未知",
}

# 势力 status 中英映射
_FACTION_STATUS_LABELS: dict[str, str] = {
    "active": "活跃",
    "disbanded": "解散",
    "destroyed": "覆灭",
    "unknown": "未知",
}


def format_memory_for_prompt(memory: StoryMemory) -> str:
    """Format memory as readable markdown for LLM prompt injection.

    Returns empty string for blank memories (total_chapters_processed == 0).
    """
    if memory.total_chapters_processed == 0:
        return ""

    sections: list[str] = []

    # -- 角色档案 --
    # 只列有有效信息的角色（有 aliases/power_level/faction，或 role 非 minor）
    notable_chars = [
        c for c in memory.characters
        if c.role != "minor" or c.aliases or c.power_level or c.faction
    ]
    if notable_chars:
        rows: list[str] = []
        rows.append("## 已知角色档案\n")
        rows.append("| 角色 | 别名 | 身份 | 势力 | 境界 | 状态 |")
        rows.append("|------|------|------|------|------|------|")
        for c in notable_chars:
            alias_str = ", ".join(c.aliases) if c.aliases else "-"
            role_str = _ROLE_LABELS.get(c.role, c.role)
            faction_str = c.faction or "-"
            power_str = c.power_level or "-"
            status_str = _STATUS_LABELS.get(c.status, c.status)
            rows.append(f"| {c.name} | {alias_str} | {role_str} | {faction_str} | {power_str} | {status_str} |")
        sections.append("\n".join(rows))

    # -- 主要关系 --
    known_rels = [r for r in memory.relationships if r.relation_type != "unknown"]
    if known_rels:
        lines: list[str] = ["## 主要关系\n"]
        for r in known_rels:
            since = f"（自{r.since_chapter}）" if r.since_chapter else ""
            desc = f" — {r.description}" if r.description else ""
            lines.append(f"- {r.character_a} ↔ {r.character_b}：{r.relation_type}{desc}{since}")
        sections.append("\n".join(lines))

    # -- 势力格局 --
    active_factions = [f for f in memory.factions if f.status != "unknown" or f.key_members]
    if active_factions:
        lines = ["## 势力格局\n"]
        for f in active_factions:
            status_str = _FACTION_STATUS_LABELS.get(f.status, f.status)
            members_str = "、".join(f.key_members) if f.key_members else "暂无"
            desc_part = f" — {f.description}" if f.description else ""
            lines.append(f"- **{f.name}**（{status_str}）：{members_str}{desc_part}")
        sections.append("\n".join(lines))

    # -- 剧情状态 --
    ps = memory.plot_state
    has_plot = ps.current_arc or ps.recent_events_digest or ps.active_threads
    if has_plot:
        lines = ["## 剧情状态\n"]
        if ps.current_arc:
            lines.append(f"**当前主线**：{ps.current_arc}")
            if ps.arc_summary:
                lines.append(f"> {ps.arc_summary}")
            lines.append("")
        if ps.active_threads:
            lines.append(f"**活跃支线**：{'、'.join(ps.active_threads)}")
        if ps.unresolved_foreshadowing:
            lines.append(f"**未回收伏笔**：{'、'.join(ps.unresolved_foreshadowing)}")
        if ps.recent_events_digest:
            lines.append("")
            lines.append("**最近剧情**：")
            lines.append(f"> {ps.recent_events_digest}")
        sections.append("\n".join(lines))

    if not sections:
        return ""

    return "\n\n".join(sections) + "\n"


# ---------------------------------------------------------------------------
# Character alias normalization
# ---------------------------------------------------------------------------

def normalize_character_names(
    events: list[dict[str, Any]],
    memory: StoryMemory,
) -> list[dict[str, Any]]:
    """Replace character aliases with canonical names in event dicts.

    Returns a new list (does not mutate the input).
    Empty memory or empty events → returns a shallow copy unchanged.
    """
    if not memory.characters or not events:
        return list(events)

    # 构建 alias → 主名 映射（包含主名自身映射）
    alias_map: dict[str, str] = {}
    for cp in memory.characters:
        alias_map[cp.name] = cp.name
        for alias in cp.aliases:
            # 如果别名冲突（两个角色共享同一别名），先到先得，不覆盖
            if alias not in alias_map:
                alias_map[alias] = cp.name

    result: list[dict[str, Any]] = []
    for ev in events:
        chars = ev.get("characters")
        if not isinstance(chars, list):
            result.append(copy.copy(ev))
            continue

        # 归一化 + 去重（保持顺序）
        normalized: list[str] = []
        seen: set[str] = set()
        for name in chars:
            canonical = alias_map.get(name, name)
            if canonical not in seen:
                seen.add(canonical)
                normalized.append(canonical)

        new_ev = copy.copy(ev)
        new_ev["characters"] = normalized
        result.append(new_ev)

    return result


# ---------------------------------------------------------------------------
# Content hash (for cache keys)
# ---------------------------------------------------------------------------

def memory_content_hash(memory: StoryMemory) -> str:
    """Return a short SHA-256 hash (first 16 hex chars) of the memory content.

    Empty memory (total_chapters_processed == 0) returns empty string.
    """
    if memory.total_chapters_processed == 0:
        return ""
    payload = json.dumps(memory.to_dict(), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Internal helpers — safe deserialization
# ---------------------------------------------------------------------------

def _safe_int(value: Any, default: int = 0) -> int:
    """Convert to int with fallback."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_str_list(value: Any) -> list[str]:
    """Extract a list[str] from value, tolerating non-list input."""
    if not isinstance(value, list):
        return []
    return [str(v) for v in value if v is not None]


def _safe_character(data: dict[str, Any]) -> CharacterProfile:
    """Build a CharacterProfile from a dict, tolerating missing keys."""
    return CharacterProfile(
        name=str(data.get("name", "")),
        aliases=_safe_str_list(data.get("aliases")),
        role=str(data.get("role", "minor")),
        faction=str(data.get("faction", "")),
        status=str(data.get("status", "alive")),
        power_level=str(data.get("power_level", "")),
        personality_traits=_safe_str_list(data.get("personality_traits")),
        summary=str(data.get("summary", "")),
        last_seen_chapter=str(data.get("last_seen_chapter", "")),
    )


def _safe_relationship(data: dict[str, Any]) -> Relationship:
    """Build a Relationship from a dict, tolerating missing keys."""
    return Relationship(
        character_a=str(data.get("character_a", "")),
        character_b=str(data.get("character_b", "")),
        relation_type=str(data.get("relation_type", "unknown")),
        description=str(data.get("description", "")),
        since_chapter=str(data.get("since_chapter", "")),
    )


def _safe_faction(data: dict[str, Any]) -> FactionInfo:
    """Build a FactionInfo from a dict, tolerating missing keys."""
    return FactionInfo(
        name=str(data.get("name", "")),
        description=str(data.get("description", "")),
        key_members=_safe_str_list(data.get("key_members")),
        status=str(data.get("status", "active")),
    )


def _safe_plot_state(data: dict[str, Any]) -> PlotState:
    """Build a PlotState from a dict, tolerating missing keys."""
    return PlotState(
        current_arc=str(data.get("current_arc", "")),
        arc_summary=str(data.get("arc_summary", "")),
        active_threads=_safe_str_list(data.get("active_threads")),
        unresolved_foreshadowing=_safe_str_list(data.get("unresolved_foreshadowing")),
        recent_events_digest=str(data.get("recent_events_digest", "")),
    )
