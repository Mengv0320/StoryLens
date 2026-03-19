from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .character_tracker import CharacterTracker
from .models import (
    FactionCard,
    KnowledgeLayer,
    LocationInfo,
    NormalizedEvent,
    NormalizedEventSet,
    PlotTimeline,
    ScoredEvent,
    SubplotIndex,
    TimelineEvent,
    WorldSetting,
)

FACTION_EVENT_GROUPS = frozenset({"status_shift", "scheme_intrigue"})
WORLD_EVENT_GROUPS = frozenset({"world_rule", "setup"})
SUBPLOT_EVENT_GROUPS = frozenset({
    "scheme_intrigue", "emotion_romance", "revelation",
    "goal_progress", "conflict",
})


class KnowledgeManager:
    """Accumulates structured knowledge across chapters."""

    def __init__(self, character_tracker: CharacterTracker | None = None) -> None:
        self.tracker = character_tracker or CharacterTracker()
        self._factions: dict[str, FactionCard] = {}
        self._next_faction_id: int = 1
        self._world = WorldSetting()
        self._timeline = PlotTimeline()
        self._subplots: dict[str, SubplotIndex] = {}
        self._next_subplot_id: int = 1
        self._next_timeline_id: int = 1

    def update_from_chapter(
        self,
        chapter_id: str,
        normalized_events: NormalizedEventSet,
        scored_events: list[ScoredEvent],
        genre: str = "",
    ) -> None:
        self.tracker.update_from_events(normalized_events.events, scored_events, chapter_id)
        score_map: dict[str, ScoredEvent] = {s.event_id: s for s in scored_events}
        for event in normalized_events.events:
            scored = score_map.get(event.event_id)
            self._update_timeline(event, chapter_id, scored)
            self._update_factions(event, chapter_id)
            self._update_world(event)
            self._update_subplots(event, chapter_id, scored)

    def export(self) -> KnowledgeLayer:
        return KnowledgeLayer(
            characters=self.tracker.get_all_characters(),
            factions=list(self._factions.values()),
            world_setting=self._world,
            timeline=PlotTimeline(
                main_plot_events=self._timeline.main_plot_events,
                subplots=list(self._subplots.values()),
            ),
        )

    def export_for_artifact(self) -> dict[str, Any]:
        """Return a fully JSON-serializable dict for artifact output."""
        layer = self.export()
        return asdict(layer)

    def full_snapshot(self) -> dict[str, Any]:
        """Full serializable snapshot for cross-run checkpoint."""
        return {
            "tracker": self.tracker.full_snapshot(),
            "factions": {k: asdict(v) for k, v in self._factions.items()},
            "world": asdict(self._world),
            "timeline_events": [asdict(e) for e in self._timeline.main_plot_events],
            "subplots": {k: asdict(v) for k, v in self._subplots.items()},
            "next_faction_id": self._next_faction_id,
            "next_subplot_id": self._next_subplot_id,
            "next_timeline_id": self._next_timeline_id,
        }

    def restore(self, data: dict[str, Any]) -> None:
        """Restore full state from a previous full_snapshot."""
        from .serialization import (
            character_card_from_dict,
            faction_card_from_dict,
            world_setting_from_dict,
            timeline_event_from_dict,
            subplot_index_from_dict,
        )
        # Restore character tracker
        tracker_data = data.get("tracker", {})
        if tracker_data:
            self.tracker.restore(tracker_data)
        # Restore factions
        self._factions = {
            k: faction_card_from_dict(v)
            for k, v in data.get("factions", {}).items()
        }
        self._next_faction_id = data.get("next_faction_id", len(self._factions) + 1)
        # Restore world
        world_data = data.get("world", {})
        if world_data:
            self._world = world_setting_from_dict(world_data)
        # Restore timeline
        self._timeline.main_plot_events = [
            timeline_event_from_dict(e)
            for e in data.get("timeline_events", [])
        ]
        self._next_timeline_id = data.get("next_timeline_id", len(self._timeline.main_plot_events) + 1)
        # Restore subplots
        self._subplots = {
            k: subplot_index_from_dict(v)
            for k, v in data.get("subplots", {}).items()
        }
        self._next_subplot_id = data.get("next_subplot_id", len(self._subplots) + 1)

    def _update_timeline(
        self, event: NormalizedEvent, chapter_id: str, scored: ScoredEvent | None
    ) -> None:
        is_significant = scored and (scored.main_plot_score >= 3 or scored.must_keep)
        if not is_significant:
            return
        te = TimelineEvent(
            event_id=event.event_id,
            chapter=chapter_id,
            description=event.title or event.description,
            characters_involved=list(event.characters),
            plot_significance="high" if (scored and scored.main_plot_score >= 4) else "medium",
        )
        self._timeline.main_plot_events.append(te)

    def _update_factions(self, event: NormalizedEvent, chapter_id: str) -> None:
        if event.event_group not in FACTION_EVENT_GROUPS:
            return
        desc_lower = (event.description + " " + event.title).lower()
        faction_keywords = ("宗", "门", "派", "族", "帮", "盟", "教", "殿", "阁", "府")
        for keyword in faction_keywords:
            if keyword not in desc_lower:
                continue
            faction_name = self._extract_faction_name(desc_lower, keyword)
            if not faction_name:
                continue
            if faction_name not in self._factions:
                self._factions[faction_name] = FactionCard(
                    faction_id=f"faction_{self._next_faction_id:04d}",
                    name=faction_name,
                    description=event.description,
                )
                self._next_faction_id += 1
            faction = self._factions[faction_name]
            for char in event.characters:
                if char not in faction.members:
                    faction.members.append(char)

    def _extract_faction_name(self, text: str, keyword: str) -> str:
        idx = text.find(keyword)
        if idx < 0:
            return ""
        start = max(0, idx - 4)
        end = idx + len(keyword)
        candidate = text[start:end].strip()
        if len(candidate) < 2:
            return ""
        return candidate

    def _update_world(self, event: NormalizedEvent) -> None:
        if event.event_group not in WORLD_EVENT_GROUPS:
            return
        desc = event.description or event.title
        if not desc:
            return
        event_type_lower = event.event_type.lower()
        if any(w in event_type_lower for w in ("power", "cultivation", "修炼", "境界", "力量")):
            if not self._world.power_system:
                self._world.power_system = desc
            elif desc not in self._world.power_system:
                self._world.power_system += f"; {desc}"
        elif any(w in event_type_lower for w in ("location", "地点", "place", "realm")):
            existing_names = {loc.name for loc in self._world.locations}
            loc_name = event.title or desc[:20]
            if loc_name not in existing_names:
                self._world.locations.append(LocationInfo(
                    name=loc_name,
                    description=desc,
                ))
        else:
            if desc not in self._world.rules:
                self._world.rules.append(desc)
                if len(self._world.rules) > 20:
                    self._world.rules = self._world.rules[-20:]

    def _update_subplots(
        self, event: NormalizedEvent, chapter_id: str, scored: ScoredEvent | None
    ) -> None:
        if event.event_group not in SUBPLOT_EVENT_GROUPS:
            return
        if scored and scored.main_plot_score >= 4:
            return
        key_chars = tuple(sorted(event.characters[:3]))
        if not key_chars:
            return
        subplot_key = f"{event.event_group}::{','.join(key_chars)}"
        if subplot_key not in self._subplots:
            self._subplots[subplot_key] = SubplotIndex(
                subplot_id=f"subplot_{self._next_subplot_id:04d}",
                title=event.title or event.description[:40],
                related_characters=list(key_chars),
            )
            self._next_subplot_id += 1
        subplot = self._subplots[subplot_key]
        if event.event_id not in subplot.event_ids:
            subplot.event_ids.append(event.event_id)
