from __future__ import annotations

from dataclasses import asdict

from .models import (
    CausalAnalysisResult,
    CausalChain,
    CharacterCard,
    CharacterRelation,
    EpisodeBoundary,
    EpisodeSummary,
    ExtractedEvent,
    FactionCard,
    Foreshadowing,
    GenreClassification,
    KnowledgeLayer,
    LocationInfo,
    NormalizedEvent,
    NormalizedEventSet,
    PlotTimeline,
    QualityReport,
    QualityWarning,
    SceneChunk,
    SceneExtraction,
    SceneSplit,
    ScoredEvent,
    SubplotIndex,
    TimelineEvent,
    WorldSetting,
)


def to_dict(obj):
    return asdict(obj)


def scene_split_from_dict(data: dict) -> SceneSplit:
    return SceneSplit(scenes=[SceneChunk(**item) for item in data["scenes"]])


def extraction_from_dict(data: dict) -> SceneExtraction:
    return SceneExtraction(
        scene_id=data["scene_id"],
        genre_guess=data["genre_guess"],
        scene_function=data["scene_function"],
        events=[ExtractedEvent(**event) for event in data["events"]],
    )


def genre_from_dict(data: dict) -> GenreClassification:
    return GenreClassification(**data)


def normalized_events_from_dict(data: dict) -> NormalizedEventSet:
    return NormalizedEventSet(events=[NormalizedEvent(**item) for item in data["events"]])


def scored_events_from_dict(items: list[dict]) -> list[ScoredEvent]:
    return [ScoredEvent(**item) for item in items]


def episode_from_dict(data: dict) -> EpisodeSummary:
    return EpisodeSummary(**data)


def causal_chain_from_dict(data: dict) -> CausalChain:
    return CausalChain(**data)


def foreshadowing_from_dict(data: dict) -> Foreshadowing:
    return Foreshadowing(**data)


def causal_analysis_from_dict(data: dict) -> CausalAnalysisResult:
    return CausalAnalysisResult(
        causal_links=data.get("causal_links", []),
        chains=[causal_chain_from_dict(c) for c in data.get("chains", [])],
        foreshadowing=[foreshadowing_from_dict(f) for f in data.get("foreshadowing", [])],
    )


def character_relation_from_dict(data: dict) -> CharacterRelation:
    return CharacterRelation(**data)


def character_card_from_dict(data: dict) -> CharacterCard:
    d = dict(data)
    d["relationships"] = [character_relation_from_dict(r) for r in d.get("relationships", [])]
    return CharacterCard(**d)


def faction_card_from_dict(data: dict) -> FactionCard:
    return FactionCard(**data)


def location_info_from_dict(data: dict) -> LocationInfo:
    return LocationInfo(**data)


def world_setting_from_dict(data: dict) -> WorldSetting:
    return WorldSetting(
        power_system=data.get("power_system", ""),
        locations=[location_info_from_dict(loc) for loc in data.get("locations", [])],
        rules=data.get("rules", []),
    )


def timeline_event_from_dict(data: dict) -> TimelineEvent:
    return TimelineEvent(**data)


def subplot_index_from_dict(data: dict) -> SubplotIndex:
    return SubplotIndex(**data)


def plot_timeline_from_dict(data: dict) -> PlotTimeline:
    return PlotTimeline(
        main_plot_events=[timeline_event_from_dict(e) for e in data.get("main_plot_events", [])],
        subplots=[subplot_index_from_dict(s) for s in data.get("subplots", [])],
    )


def knowledge_layer_from_dict(data: dict) -> KnowledgeLayer:
    return KnowledgeLayer(
        characters=[character_card_from_dict(c) for c in data.get("characters", [])],
        factions=[faction_card_from_dict(f) for f in data.get("factions", [])],
        world_setting=world_setting_from_dict(data.get("world_setting", {})),
        timeline=plot_timeline_from_dict(data.get("timeline", {})),
    )


def episode_boundary_from_dict(data: dict) -> EpisodeBoundary:
    return EpisodeBoundary(**data)


def quality_warning_from_dict(data: dict) -> QualityWarning:
    return QualityWarning(**data)


def quality_report_from_dict(data: dict) -> QualityReport:
    d = dict(data)
    d["warnings"] = [quality_warning_from_dict(w) for w in d.get("warnings", [])]
    return QualityReport(**d)
