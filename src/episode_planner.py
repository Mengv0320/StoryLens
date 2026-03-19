from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass, field

from .models import EpisodeBoundary

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

TURNING_POINT_TOKENS = (
    "victory",
    "defeat",
    "betrayal",
    "identity_reveal",
    "secret_exposed",
    "traitor_exposed",
    "turning_point",
)

HOOK_TOKENS = (
    "new_arc_hook",
    "foreshadowing",
    "suspense",
    "cliffhanger",
    "unresolved",
)

GOAL_CHANGE_TOKENS = (
    "goal_change",
    "mission_change",
    "objective_shift",
    "new_quest",
    "new_mission",
)


@dataclass
class PlannedEpisodeChunk:
    episode_id: str
    chapter_ids: list[str]
    chapter_titles: list[str]
    boundary: EpisodeBoundary | None = None


# ---------------------------------------------------------------------------
# V1 scoring (original)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# V2 multi-dimensional scoring
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS = {
    "event_density": 0.25,
    "goal_change": 0.20,
    "turning_point": 0.30,
    "hook_potential": 0.25,
    "climax_continuation_penalty": -0.10,
}


def _event_density_score(
    chapter_results: list[dict[str, object]],
    window_center: int,
    window_half: int = 1,
) -> float:
    start = max(0, window_center - window_half)
    end = min(len(chapter_results), window_center + window_half + 1)
    high_score_count = 0
    total_events = 0
    for idx in range(start, end):
        scores = chapter_results[idx].get("scores", [])
        for score in scores:
            total = (
                int(score.get("climax_score", 0))
                + int(score.get("main_plot_score", 0))
                + int(score.get("suspense_score", 0))
            )
            if total > 3:
                high_score_count += 1
            total_events += 1
    if total_events == 0:
        return 0.0
    return min(high_score_count / max(total_events, 1) * 5, 5.0)


def _goal_change_score(chapter_result: dict[str, object]) -> float:
    events = chapter_result.get("normalized_events", {}).get("events", [])
    for event in events:
        event_type = str(event.get("event_type", "")).lower()
        if any(token in event_type for token in GOAL_CHANGE_TOKENS):
            return 5.0
    return 0.0


def _turning_point_score(chapter_result: dict[str, object]) -> float:
    events = chapter_result.get("normalized_events", {}).get("events", [])
    score = 0.0
    for event in events:
        event_type = str(event.get("event_type", "")).lower()
        for token in TURNING_POINT_TOKENS:
            if token in event_type:
                score += 2.5
                break
    return min(score, 5.0)


def _hook_potential_score(chapter_result: dict[str, object]) -> float:
    events = chapter_result.get("normalized_events", {}).get("events", [])
    scores_list = chapter_result.get("scores", [])
    hook_score = 0.0
    for event in events:
        event_type = str(event.get("event_type", "")).lower()
        if any(token in event_type for token in HOOK_TOKENS):
            hook_score += 1.5
        if event.get("foreshadowing"):
            hook_score += 1.0
    max_suspense = 0
    for score in scores_list:
        max_suspense = max(max_suspense, int(score.get("suspense_score", 0)))
    hook_score += max_suspense * 0.5
    return min(hook_score, 5.0)


def _climax_continuation_penalty(
    chapter_results: list[dict[str, object]], index: int
) -> float:
    """Penalty if next chapter continues the current climax (bad cut point)."""
    if index + 1 >= len(chapter_results):
        return 0.0
    current_climax = 0
    for score in chapter_results[index].get("scores", []):
        current_climax = max(current_climax, int(score.get("climax_score", 0)))
    if current_climax < 4:
        return 0.0
    next_climax = 0
    for score in chapter_results[index + 1].get("scores", []):
        next_climax = max(next_climax, int(score.get("climax_score", 0)))
    if next_climax >= 3:
        return -min((current_climax + next_climax) * 0.3, 5.0)
    return 0.0


def chapter_boundary_score_v2(
    chapter_results: list[dict[str, object]],
    index: int,
    weights: dict[str, float] | None = None,
) -> dict[str, float]:
    w = weights or DEFAULT_WEIGHTS
    chapter = chapter_results[index]
    density = _event_density_score(chapter_results, index)
    goal = _goal_change_score(chapter)
    turning = _turning_point_score(chapter)
    hook = _hook_potential_score(chapter)
    penalty = _climax_continuation_penalty(chapter_results, index)
    composite = (
        w.get("event_density", 0.25) * density
        + w.get("goal_change", 0.20) * goal
        + w.get("turning_point", 0.30) * turning
        + w.get("hook_potential", 0.25) * hook
        + w.get("climax_continuation_penalty", -0.10) * abs(penalty)
    )
    return {
        "event_density_score": round(density, 3),
        "goal_change_score": round(goal, 3),
        "turning_point_score": round(turning, 3),
        "hook_potential_score": round(hook, 3),
        "climax_continuation_penalty": round(penalty, 3),
        "composite_score": round(composite, 3),
    }


def _is_mid_climax(chapter_results: list[dict[str, object]], index: int) -> bool:
    """Check if the next chapter continues a climax (don't cut mid-climax)."""
    if index + 1 >= len(chapter_results):
        return False
    next_chapter = chapter_results[index + 1]
    for score in next_chapter.get("scores", []):
        climax = int(score.get("climax_score", 0))
        if climax >= 4:
            return True
    return False


def _is_valley_start(chapter_results: list[dict[str, object]], index: int) -> bool:
    """Check if the next chapter is a valley (bad place to start new episode)."""
    if index + 1 >= len(chapter_results):
        return False
    next_scores = chapter_results[index + 1].get("scores", [])
    if not next_scores:
        return True
    max_total = 0
    for score in next_scores:
        total = (
            int(score.get("climax_score", 0))
            + int(score.get("main_plot_score", 0))
            + int(score.get("suspense_score", 0))
        )
        max_total = max(max_total, total)
    return max_total <= 3


def _compute_dynamic_threshold(
    all_scores: list[float],
    percentile: float = 0.70,
) -> float:
    if not all_scores:
        return 2.0
    sorted_scores = sorted(all_scores)
    idx = int(len(sorted_scores) * percentile)
    idx = min(idx, len(sorted_scores) - 1)
    threshold = sorted_scores[idx]
    return max(threshold, 1.0)


def _determine_cut_reason(scores: dict[str, float]) -> str:
    parts = []
    if scores.get("turning_point_score", 0) >= 2.5:
        parts.append("关键转折点")
    if scores.get("goal_change_score", 0) >= 3.0:
        parts.append("角色目标变更")
    if scores.get("event_density_score", 0) >= 3.0:
        parts.append("高分事件密集区")
    if scores.get("hook_potential_score", 0) >= 3.0:
        parts.append("悬念/钩子强度高")
    if not parts:
        parts.append("综合评分达到阈值")
    return "；".join(parts)


def _determine_hook_description(chapter_result: dict[str, object]) -> str:
    events = chapter_result.get("normalized_events", {}).get("events", [])
    hooks = []
    for event in events:
        event_type = str(event.get("event_type", "")).lower()
        if any(token in event_type for token in HOOK_TOKENS):
            hooks.append(str(event.get("title", event_type)))
        elif event.get("foreshadowing"):
            hooks.append(str(event.get("title", "伏笔")))
    if hooks:
        return "；".join(hooks[:3])
    scores_list = chapter_result.get("scores", [])
    max_suspense_score = 0
    for score in scores_list:
        s = int(score.get("suspense_score", 0))
        if s > max_suspense_score:
            max_suspense_score = s
    if max_suspense_score >= 3:
        return "悬念未解"
    return ""


# ---------------------------------------------------------------------------
# V1 plan (backward compat)
# ---------------------------------------------------------------------------


def plan_episode_chunks_v1(
    chapter_results: list[dict[str, object]], target_size: int = 5
) -> list[PlannedEpisodeChunk]:
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


# ---------------------------------------------------------------------------
# V2 plan (multi-dimensional, climax-aware)
# ---------------------------------------------------------------------------


def plan_episode_chunks(
    chapter_results: list[dict[str, object]],
    target_size: int = 5,
    strategy: str = "v2",
    weights: dict[str, float] | None = None,
) -> list[PlannedEpisodeChunk]:
    if strategy == "v1":
        return plan_episode_chunks_v1(chapter_results, target_size)

    if not chapter_results:
        return []

    min_size = max(2, target_size // 2)
    max_size = max(min_size + 1, target_size + 3)

    # Phase 1: compute all boundary scores
    all_boundary_scores: list[dict[str, float]] = []
    for i in range(len(chapter_results)):
        all_boundary_scores.append(
            chapter_boundary_score_v2(chapter_results, i, weights)
        )
    composite_values = [s["composite_score"] for s in all_boundary_scores]
    threshold = _compute_dynamic_threshold(composite_values, percentile=0.70)

    # Phase 2: build chunks with lookback/lookahead
    chunks: list[PlannedEpisodeChunk] = []
    current: list[dict[str, object]] = []
    current_start_idx = 0

    def flush(boundary_idx: int | None = None) -> None:
        nonlocal current_start_idx
        if not current:
            return
        index = len(chunks) + 1
        boundary = None
        if boundary_idx is not None:
            last_chapter = current[-1]
            boundary_scores = all_boundary_scores[boundary_idx]
            boundary = EpisodeBoundary(
                boundary_chapter_id=str(last_chapter["chapter"]["chapter_id"]),
                scores=boundary_scores,
                cut_reason=_determine_cut_reason(boundary_scores),
                hook_description=_determine_hook_description(last_chapter),
            )
        chunks.append(
            PlannedEpisodeChunk(
                episode_id=f"episode_{index:03d}",
                chapter_ids=[item["chapter"]["chapter_id"] for item in current],
                chapter_titles=[item["chapter"]["title"] for item in current],
                boundary=boundary,
            )
        )
        current_start_idx = current_start_idx + len(current)
        current.clear()

    for i, chapter in enumerate(chapter_results):
        current.append(chapter)
        size = len(current)

        # Hard max: always cut
        if size >= max_size:
            flush(i)
            continue

        if size < min_size:
            continue

        composite = all_boundary_scores[i]["composite_score"]

        # Not above threshold => don't cut
        if composite < threshold:
            continue

        # Lookback: don't cut mid-climax
        if _is_mid_climax(chapter_results, i):
            continue

        # Lookahead: don't start new episode in a valley
        if _is_valley_start(chapter_results, i) and size < target_size:
            continue

        flush(i)

    # Flush remaining chapters
    if current:
        last_global_idx = current_start_idx + len(current) - 1
        flush(last_global_idx)

    return chunks


def build_episode_plan_entry(episode_result: dict[str, object]) -> dict[str, object]:
    episode = episode_result["episode"]
    chapter_ids = episode_result["chapter_ids"]
    entry: dict[str, object] = {
        "episode_id": episode_result["episode_id"],
        "title": episode["title"],
        "chapter_ids": chapter_ids,
        "chapter_titles": episode_result.get("chapter_titles", []),
        "core_theme": episode["core_theme"],
        "main_conflict": episode["main_conflict"],
        "climax": episode["climax"],
        "ending_hook": episode["ending_hook"],
    }
    # Include boundary info if present
    if "boundary" in episode_result and episode_result["boundary"] is not None:
        boundary = episode_result["boundary"]
        if isinstance(boundary, dict):
            entry["boundary"] = boundary
        elif isinstance(boundary, EpisodeBoundary):
            entry["boundary"] = asdict(boundary)
    return entry
