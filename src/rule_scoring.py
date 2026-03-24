"""Rule-based chapter importance scoring engine (no LLM calls)."""

from __future__ import annotations

from .models import ChapterKeyEvent, ChapterKeyEventSet


# --- weights & bonuses ---

_TYPE_WEIGHT: dict[str, float] = {
    "转折": 1.5,
    "伏笔回收": 1.5,
    # Legacy English keys (backward compat with old data)
    "turning_point": 1.5,
    "payoff": 1.5,
}
_DEFAULT_TYPE_WEIGHT = 1.0

_BOOL_BONUS: list[tuple[str, float, str]] = [
    # (attribute, bonus, reason_label)
    ("involves_identity_reveal", 0.5, "涉及身份揭露"),
    ("involves_death_or_breakthrough", 0.4, "涉及死亡或突破"),
    ("involves_faction_change", 0.3, "涉及阵营变动"),
    ("involves_protagonist", 0.3, "涉及主角"),
    ("involves_relationship_change", 0.2, "涉及关系变化"),
]

_EVENT_TYPE_BONUS: list[tuple[str, float, str]] = [
    ("转折", 0.3, "含转折点事件"),
    ("伏笔回收", 0.2, "含伏笔回收"),
    ("turning_point", 0.3, "含转折点事件"),
    ("payoff", 0.2, "含伏笔回收"),
]


def _clamp(value: float, lo: int = 1, hi: int = 5) -> int:
    return max(lo, min(hi, round(value)))


def score_chapter(events: ChapterKeyEventSet) -> dict:
    """Score a single chapter based on its extracted key events.

    Returns dict with importance_score (1-5), importance_reason, and flags.
    """
    if not events.events:
        return {
            "importance_score": 1,
            "importance_reason": "无关键事件",
            "event_count": 0,
            "has_protagonist_event": False,
            "has_turning_point": False,
            "has_identity_reveal": False,
        }

    # --- weighted average of event importance ---
    weighted_sum = 0.0
    weight_total = 0.0
    for ev in events.events:
        w = _TYPE_WEIGHT.get(ev.event_type, _DEFAULT_TYPE_WEIGHT)
        weighted_sum += ev.importance * w
        weight_total += w
    base = weighted_sum / weight_total

    # --- boolean bonuses (take max across all events) ---
    reasons: list[tuple[float, str]] = []
    for attr, bonus, label in _BOOL_BONUS:
        if any(getattr(ev, attr, False) for ev in events.events):
            base += bonus
            reasons.append((bonus, label))

    # --- event type bonuses ---
    event_types = {ev.event_type for ev in events.events}
    for etype, bonus, label in _EVENT_TYPE_BONUS:
        if etype in event_types:
            base += bonus
            reasons.append((bonus, label))

    score = _clamp(base)

    # build reason string from top contributors
    if reasons:
        reasons.sort(key=lambda r: r[0], reverse=True)
        reason = "、".join(r[1] for r in reasons[:3])
    else:
        reason = "常规剧情推进"

    return {
        "importance_score": score,
        "importance_reason": reason,
        "event_count": len(events.events),
        "has_protagonist_event": any(ev.involves_protagonist for ev in events.events),
        "has_turning_point": any(ev.event_type in ("转折", "turning_point") for ev in events.events),
        "has_identity_reveal": any(ev.involves_identity_reveal for ev in events.events),
    }


def score_chapters(chapter_results: list[dict]) -> list[dict]:
    """Batch-score chapters. Each dict must have an 'events' key holding a
    ChapterKeyEventSet. Scoring fields are merged into each dict in-place and
    the list is returned for convenience."""
    for ch in chapter_results:
        event_set = ch.get("events")
        if event_set is None:
            event_set = ChapterKeyEventSet()
        scoring = score_chapter(event_set)
        ch.update(scoring)
    return chapter_results
