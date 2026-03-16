from __future__ import annotations

from dataclasses import asdict

from .models import EpisodeSummary, ExtractedEvent, GenreClassification, NormalizedEventSet, SceneChunk, SceneExtraction, SceneSplit, ScoredEvent


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
    from .models import NormalizedEvent

    return NormalizedEventSet(events=[NormalizedEvent(**item) for item in data["events"]])


def scored_events_from_dict(items: list[dict]) -> list[ScoredEvent]:
    return [ScoredEvent(**item) for item in items]


def episode_from_dict(data: dict) -> EpisodeSummary:
    return EpisodeSummary(**data)
