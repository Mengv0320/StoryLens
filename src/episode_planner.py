from __future__ import annotations

from dataclasses import asdict, dataclass


TRIGGER_EVENT_TOKENS = (
    "turning_point",
    "victory",
    "defeat",
    "new_arc_hook",
    "identity_reveal",
    "secret_exposed",
    "traitor_exposed",
    "breakthrough",
    "relationship_confirmed",
    "confession",
    "betrayal",
)


@dataclass
class PlannedEpisodeChunk:
    episode_id: str
    chapter_ids: list[str]
    chapter_titles: list[str]


def chapter_boundary_score(chapter_result: dict[str, object]) -> int:
    scores = chapter_result.get("scores", [])
    max_peak = 0
    trigger_bonus = 0
    for score in scores:
        climax = int(score.get("climax_score", 0))
        suspense = int(score.get("suspense_score", 0))
        main_plot = int(score.get("main_plot_score", 0))
        max_peak = max(max_peak, climax + suspense + main_plot)
    for event in chapter_result.get("normalized_events", {}).get("events", []):
        event_type = str(event.get("event_type", ""))
        if any(token in event_type for token in TRIGGER_EVENT_TOKENS):
            trigger_bonus = 2
            break
    return max_peak + trigger_bonus


def plan_episode_chunks(chapter_results: list[dict[str, object]], target_size: int = 5) -> list[PlannedEpisodeChunk]:
    if not chapter_results:
        return []

    min_size = max(1, target_size // 2)
    max_size = max(min_size + 1, target_size + 2)
    chunks: list[PlannedEpisodeChunk] = []
    current: list[dict[str, object]] = []

    def flush() -> None:
        if not current:
            return
        index = len(chunks) + 1
        chunks.append(
            PlannedEpisodeChunk(
                episode_id=f"episode_{index:03d}",
                chapter_ids=[item["chapter"]["chapter_id"] for item in current],
                chapter_titles=[item["chapter"]["title"] for item in current],
            )
        )
        current.clear()

    for chapter in chapter_results:
        current.append(chapter)
        size = len(current)
        boundary = chapter_boundary_score(chapter)
        if size >= max_size:
            flush()
            continue
        if size >= min_size and boundary >= 12:
            flush()
            continue
        if size >= target_size and boundary >= 9:
            flush()
            continue

    flush()
    return chunks


def build_episode_plan_entry(episode_result: dict[str, object]) -> dict[str, object]:
    episode = episode_result["episode"]
    chapter_ids = episode_result["chapter_ids"]
    return {
        "episode_id": episode_result["episode_id"],
        "title": episode["title"],
        "chapter_ids": chapter_ids,
        "core_theme": episode["core_theme"],
        "main_conflict": episode["main_conflict"],
        "climax": episode["climax"],
        "ending_hook": episode["ending_hook"],
    }
