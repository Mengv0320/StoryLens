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
    event_type: str  # conflict, turning_point, relationship_change, status_change, foreshadowing, payoff
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


@dataclass
class ChapterKeyEventSet:
    """Set of key events extracted from a single chapter."""
    events: list[ChapterKeyEvent] = field(default_factory=list)
    chapter_summary: str = ""


JsonDict = dict[str, Any]
