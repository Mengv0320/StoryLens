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
    # Causal chain fields
    causes: list[str] = field(default_factory=list)
    effects: list[str] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    foreshadowing_for: str | None = None
    foreshadowed_by: str | None = None
    causal_chain_id: str | None = None


@dataclass
class NormalizedEventSet:
    events: list[NormalizedEvent] = field(default_factory=list)


@dataclass
class ChapterKeyEvent:
    """A key event extracted directly at chapter level (lite pipeline)."""
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
    """Set of key events extracted from a single chapter (lite pipeline)."""
    events: list[ChapterKeyEvent] = field(default_factory=list)
    chapter_summary: str = ""


@dataclass
class CausalChain:
    chain_id: str
    title: str
    events: list[str] = field(default_factory=list)
    chain_type: str = "main_plot"
    status: str = "active"


@dataclass
class Foreshadowing:
    foreshadow_id: str
    setup_event_id: str
    setup_chapter: str
    payoff_event_id: str | None = None
    payoff_chapter: str | None = None
    description: str = ""
    status: str = "planted"


@dataclass
class CausalAnalysisResult:
    causal_links: list[dict[str, Any]] = field(default_factory=list)
    chains: list[CausalChain] = field(default_factory=list)
    foreshadowing: list[Foreshadowing] = field(default_factory=list)


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


@dataclass
class EpisodeBoundary:
    boundary_chapter_id: str
    scores: dict[str, float] = field(default_factory=dict)
    cut_reason: str = ""
    hook_description: str = ""


@dataclass
class TitleStyle:
    genre: str
    pattern: str
    examples: list[str] = field(default_factory=list)
    tone_keywords: list[str] = field(default_factory=list)


@dataclass
class SummaryTone:
    genre: str
    tone_description: str
    emphasis_points: list[str] = field(default_factory=list)
    avoid_points: list[str] = field(default_factory=list)


@dataclass
class RetentionPriority:
    genre: str
    priority_order: list[str] = field(default_factory=list)
    boost_event_types: list[str] = field(default_factory=list)
    demote_event_types: list[str] = field(default_factory=list)


@dataclass
class QualityWarning:
    severity: str
    category: str
    message: str
    location: str


@dataclass
class QualityReport:
    overall_score: int
    warnings: list[QualityWarning] = field(default_factory=list)
    summary: str = ""
    suggestions: list[str] = field(default_factory=list)


@dataclass
class CharacterRelation:
    target_character: str
    relation_type: str  # ally, enemy, master_disciple, lover, rival, family, neutral
    description: str = ""
    established_in: str = ""


@dataclass
class CharacterCard:
    character_id: str
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    identity: str = ""
    stance: str = ""
    relationships: list[CharacterRelation] = field(default_factory=list)
    recent_goals: list[str] = field(default_factory=list)
    known_secrets: list[str] = field(default_factory=list)
    first_appearance: str = ""
    status: str = "active"


@dataclass
class FactionCard:
    faction_id: str
    name: str
    description: str = ""
    members: list[str] = field(default_factory=list)
    stance: str = ""
    goals: list[str] = field(default_factory=list)


@dataclass
class LocationInfo:
    name: str
    description: str = ""
    significance: str = ""


@dataclass
class WorldSetting:
    power_system: str = ""
    locations: list[LocationInfo] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)


@dataclass
class TimelineEvent:
    event_id: str
    chapter: str
    description: str = ""
    characters_involved: list[str] = field(default_factory=list)
    plot_significance: str = ""


@dataclass
class SubplotIndex:
    subplot_id: str
    title: str
    related_characters: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)
    status: str = "active"


@dataclass
class PlotTimeline:
    main_plot_events: list[TimelineEvent] = field(default_factory=list)
    subplots: list[SubplotIndex] = field(default_factory=list)


@dataclass
class KnowledgeLayer:
    characters: list[CharacterCard] = field(default_factory=list)
    factions: list[FactionCard] = field(default_factory=list)
    world_setting: WorldSetting = field(default_factory=WorldSetting)
    timeline: PlotTimeline = field(default_factory=PlotTimeline)


JsonDict = dict[str, Any]
