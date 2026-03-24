from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GenreClassification:
    primary_genre: str
    subgenre: str
    secondary_genres: list[str] = field(default_factory=list)
    confidence: float = 0.0
    signals: list[str] = field(default_factory=list)


@dataclass
class ChapterKeyEvent:
    """A key event extracted directly at chapter level."""
    event_id: str
    event_type: str  # 冲突, 转折, 关系变化, 身份变化, 伏笔, 伏笔回收
    title: str
    description: str
    characters: list[str] = field(default_factory=list)
    cause: str = ""
    consequence: str = ""
    involves_protagonist: bool = False
    involves_identity_reveal: bool = False
    involves_faction_change: bool = False
    involves_death_or_breakthrough: bool = False
    involves_relationship_change: bool = False
    importance: int = 3  # 1-5 scale
    anchor_text: str = ""  # 原文中事件发生位置的引用片段，用于阅读器高亮定位
    time_marker: str = ""  # 故事内时间标记


@dataclass
class ChapterKeyEventSet:
    """Set of key events extracted from a single chapter."""
    events: list[ChapterKeyEvent] = field(default_factory=list)
    chapter_summary: str = ""
    filler_ratio: float = 0.0   # 注水比例
    filler_type: str = "none"   # 注水类型


JsonDict = dict[str, Any]
