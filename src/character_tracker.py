from __future__ import annotations

from dataclasses import asdict, field
from typing import Any

from .alias_memory import CharacterAliasMemory
from .models import (
    CharacterCard,
    CharacterRelation,
    NormalizedEvent,
    NormalizedEventSet,
    ScoredEvent,
)

RELATION_EVENT_TYPES = frozenset({
    "relationship",
    "alliance",
    "betrayal",
    "romance",
    "rivalry",
    "master_disciple",
    "family",
    "enmity",
})

GOAL_EVENT_TYPES = frozenset({
    "goal_progress",
    "goal_set",
    "quest",
    "mission",
    "ambition",
})

SECRET_EVENT_TYPES = frozenset({
    "revelation",
    "secret_reveal",
    "identity_reveal",
    "truth",
    "expose",
})

STATUS_EVENT_TYPES = frozenset({
    "status_shift",
    "death",
    "departure",
    "return",
    "promotion",
    "demotion",
})


class CharacterTracker:
    """Maintains CharacterCard collection across chapters, building on CharacterAliasMemory."""

    def __init__(self, alias_memory: CharacterAliasMemory | None = None) -> None:
        self.alias_memory = alias_memory or CharacterAliasMemory()
        self._cards: dict[str, CharacterCard] = {}
        self._next_id: int = 1

    def _get_or_create(self, name: str, chapter_id: str = "") -> CharacterCard:
        canonical = self.alias_memory.resolve_or_register(name)
        if canonical in self._cards:
            return self._cards[canonical]
        card = CharacterCard(
            character_id=f"char_{self._next_id:04d}",
            canonical_name=canonical,
            aliases=[name] if name != canonical else [],
            first_appearance=chapter_id,
        )
        self._next_id += 1
        self._cards[canonical] = card
        return card

    def update_from_events(
        self,
        events: list[NormalizedEvent],
        scored: list[ScoredEvent],
        chapter_id: str = "",
    ) -> None:
        score_map: dict[str, ScoredEvent] = {s.event_id: s for s in scored}
        for event in events:
            for name in event.characters:
                card = self._get_or_create(name, chapter_id)
                if name not in card.aliases and name != card.canonical_name:
                    card.aliases.append(name)
            self._extract_relationships(event, chapter_id)
            self._extract_goals(event)
            self._extract_secrets(event)
            self._extract_status(event)

    def _extract_relationships(self, event: NormalizedEvent, chapter_id: str) -> None:
        event_type_lower = event.event_type.lower()
        event_group_lower = event.event_group.lower()
        is_relation = (
            any(t in event_type_lower for t in RELATION_EVENT_TYPES)
            or event_group_lower in ("relationship", "emotion_romance")
        )
        if not is_relation or len(event.characters) < 2:
            return
        relation_type = self._infer_relation_type(event_type_lower, event.description)
        source = event.characters[0]
        for target in event.characters[1:]:
            source_card = self._get_or_create(source, chapter_id)
            existing = [r for r in source_card.relationships if r.target_character == target]
            if existing:
                existing[0].description = event.description
                existing[0].established_in = event.event_id
            else:
                source_card.relationships.append(CharacterRelation(
                    target_character=target,
                    relation_type=relation_type,
                    description=event.description,
                    established_in=event.event_id,
                ))

    def _extract_goals(self, event: NormalizedEvent) -> None:
        event_type_lower = event.event_type.lower()
        if not any(t in event_type_lower for t in GOAL_EVENT_TYPES):
            return
        for name in event.characters:
            if name in self._cards:
                card = self._cards[name]
                goal_text = event.title or event.description
                if goal_text and goal_text not in card.recent_goals:
                    card.recent_goals.append(goal_text)
                    if len(card.recent_goals) > 5:
                        card.recent_goals = card.recent_goals[-5:]

    def _extract_secrets(self, event: NormalizedEvent) -> None:
        event_type_lower = event.event_type.lower()
        if not any(t in event_type_lower for t in SECRET_EVENT_TYPES):
            return
        secret_text = event.description or event.title
        if not secret_text:
            return
        for name in event.characters:
            if name in self._cards:
                card = self._cards[name]
                if secret_text not in card.known_secrets:
                    card.known_secrets.append(secret_text)

    def _extract_status(self, event: NormalizedEvent) -> None:
        event_type_lower = event.event_type.lower()
        if not any(t in event_type_lower for t in STATUS_EVENT_TYPES):
            return
        for name in event.characters:
            if name in self._cards:
                card = self._cards[name]
                if "death" in event_type_lower:
                    card.status = "deceased"
                elif "departure" in event_type_lower:
                    card.status = "departed"
                elif "return" in event_type_lower:
                    card.status = "active"
                elif "promotion" in event_type_lower or "status_shift" in event_type_lower:
                    card.identity = event.description or card.identity

    def _infer_relation_type(self, event_type: str, description: str) -> str:
        text = f"{event_type} {description}".lower()
        if any(w in text for w in ("敌", "enemy", "enmity", "betrayal", "仇")):
            return "enemy"
        if any(w in text for w in ("师", "master", "disciple", "徒")):
            return "master_disciple"
        if any(w in text for w in ("爱", "romance", "lover", "情", "confession")):
            return "lover"
        if any(w in text for w in ("rival", "竞争", "rivalry")):
            return "rival"
        if any(w in text for w in ("family", "兄", "弟", "父", "母", "族")):
            return "family"
        if any(w in text for w in ("ally", "alliance", "盟", "友")):
            return "ally"
        return "neutral"

    def get_character_summary(self, name: str) -> CharacterCard | None:
        canonical = self.alias_memory.resolve_or_register(name)
        return self._cards.get(canonical)

    def get_all_characters(self) -> list[CharacterCard]:
        return list(self._cards.values())

    def get_relationship_graph(self) -> dict[str, Any]:
        nodes = []
        edges = []
        for card in self._cards.values():
            nodes.append({
                "id": card.character_id,
                "name": card.canonical_name,
                "status": card.status,
            })
            for rel in card.relationships:
                edges.append({
                    "source": card.canonical_name,
                    "target": rel.target_character,
                    "relation_type": rel.relation_type,
                    "description": rel.description,
                })
        return {"nodes": nodes, "edges": edges}

    def full_snapshot(self) -> dict:
        """Full serializable snapshot for cross-run checkpoint."""
        return {
            "cards": {name: asdict(card) for name, card in self._cards.items()},
            "next_id": self._next_id,
            "alias_memory": self.alias_memory.snapshot(),
        }

    def restore(self, data: dict) -> None:
        """Restore tracker state from a previous full_snapshot."""
        from .serialization import character_card_from_dict
        self._cards = {
            name: character_card_from_dict(d)
            for name, d in data.get("cards", {}).items()
        }
        self._next_id = data.get("next_id", len(self._cards) + 1)
        alias_data = data.get("alias_memory", {})
        self.alias_memory.restore(alias_data)
