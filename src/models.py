from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SceneChunk:
    scene_id: str
    start_hint: str
    end_hint: str
    location: str
    characters_present: list[str] = field(default_factory=list)
    summary: str = ""
    text: str = ""


@dataclass
class SceneSplit:
    scenes: list[SceneChunk] = field(default_factory=list)


@dataclass
class GenreClassification:
    primary_genre: str
    subgenre: str
    secondary_genres: list[str] = field(default_factory=list)
    confidence: float = 0.0
    signals: list[str] = field(default_factory=list)


@dataclass
class ExtractedEvent:
    event_id: str
    event_group: str
    event_type: str
    title: str
    description: str
    participants: list[str] = field(default_factory=list)
    cause: str = ""
    consequence: str = ""
    importance_to_main_plot: int = 1
    emotion_value: int = 1
    shock_value: int = 1
    relationship_impact: int = 1
    status_change: bool = False
    foreshadowing: bool = False
    payoff: bool = False
    must_keep: bool = False
    can_omit: bool = False


@dataclass
class SceneExtraction:
    scene_id: str
    genre_guess: str
    scene_function: str
    events: list[ExtractedEvent] = field(default_factory=list)


@dataclass
class NormalizedEvent:
    event_id: str
    source_scene_ids: list[str] = field(default_factory=list)
    event_group: str = ""
    event_type: str = ""
    title: str = ""
    description: str = ""
    characters: list[str] = field(default_factory=list)
    cause: str = ""
    consequence: str = ""
    must_keep: bool = False


@dataclass
class NormalizedEventSet:
    events: list[NormalizedEvent] = field(default_factory=list)


@dataclass
class ScoredEvent:
    event_id: str
    main_plot_score: int
    character_relation_score: int
    status_shift_score: int
    climax_score: int
    suspense_score: int
    genre_value_score: int
    must_keep: bool
    keep_reason: str


@dataclass
class EpisodeSummary:
    episode_id: str
    title: str
    core_theme: str
    hook: str
    main_conflict: str
    key_events: list[str] = field(default_factory=list)
    climax: str = ""
    ending_hook: str = ""
    episode_summary: str = ""


JsonDict = dict[str, Any]
