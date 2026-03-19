from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .models import QualityReport, QualityWarning, ScoredEvent


class QualityAssessor:
    """Assesses pipeline output quality across multiple dimensions."""

    def __init__(self) -> None:
        self._warnings: list[QualityWarning] = []

    def check_event_completeness(self, chapters_data: list[dict[str, Any]]) -> list[QualityWarning]:
        warnings: list[QualityWarning] = []
        for chapter in chapters_data:
            chapter_info = chapter.get("chapter", {})
            chapter_id = chapter_info.get("chapter_id", "unknown")
            chapter_title = chapter_info.get("title", chapter_id)
            location = f"chapter:{chapter_id}"

            normalized = chapter.get("normalized_events", {})
            events = normalized.get("events", [])
            if len(events) < 2:
                warnings.append(QualityWarning(
                    severity="warning",
                    category="completeness",
                    message=f"Chapter '{chapter_title}' has only {len(events)} event(s), expected at least 2.",
                    location=location,
                ))

            scores = chapter.get("scores", [])
            has_climax = any(
                int(s.get("climax_score", 0)) >= 4 for s in scores
            )
            if events and not has_climax:
                warnings.append(QualityWarning(
                    severity="info",
                    category="completeness",
                    message=f"Chapter '{chapter_title}' has no high-climax event (climax_score >= 4).",
                    location=location,
                ))

            has_foreshadowing = any(
                e.get("event_type", "") and "foreshadow" in str(e.get("event_type", "")).lower()
                for e in events
            )
            has_payoff = any(
                e.get("event_type", "") and "payoff" in str(e.get("event_type", "")).lower()
                for e in events
            )
            if has_foreshadowing and not has_payoff:
                warnings.append(QualityWarning(
                    severity="info",
                    category="completeness",
                    message=f"Chapter '{chapter_title}' has foreshadowing events but no payoff events.",
                    location=location,
                ))

        self._warnings.extend(warnings)
        return warnings

    def check_timeline_consistency(self, events: list[dict[str, Any]]) -> list[QualityWarning]:
        warnings: list[QualityWarning] = []
        event_map: dict[str, dict[str, Any]] = {}
        for event in events:
            eid = event.get("event_id", "")
            if eid:
                event_map[eid] = event

        # Check cause-before-effect ordering
        for event in events:
            eid = event.get("event_id", "unknown")
            cause = event.get("cause", "")
            if cause and cause in event_map:
                cause_idx = events.index(event_map[cause]) if event_map[cause] in events else -1
                current_idx = events.index(event) if event in events else -1
                if cause_idx >= 0 and current_idx >= 0 and cause_idx > current_idx:
                    warnings.append(QualityWarning(
                        severity="warning",
                        category="timeline",
                        message=f"Event '{eid}' references cause '{cause}' that appears later in sequence.",
                        location=f"event:{eid}",
                    ))

            # Also check causal chain fields (causes list)
            for cause_id in event.get("causes", []):
                if cause_id in event_map:
                    cause_idx = events.index(event_map[cause_id]) if event_map[cause_id] in events else -1
                    current_idx = events.index(event) if event in events else -1
                    if cause_idx >= 0 and current_idx >= 0 and cause_idx > current_idx:
                        warnings.append(QualityWarning(
                            severity="warning",
                            category="timeline",
                            message=f"Event '{eid}' lists cause '{cause_id}' that appears later in sequence.",
                            location=f"event:{eid}",
                        ))

        # Check character status transitions (dead -> active without explanation)
        char_statuses: dict[str, list[tuple[int, str, str]]] = {}
        for idx, event in enumerate(events):
            eid = event.get("event_id", "")
            event_type = str(event.get("event_type", "")).lower()
            for char in event.get("characters", []):
                if "death" in event_type or "kill" in event_type or "die" in event_type:
                    char_statuses.setdefault(char, []).append((idx, eid, "dead"))
                elif "resurrect" in event_type or "revive" in event_type:
                    char_statuses.setdefault(char, []).append((idx, eid, "alive"))

        for char, transitions in char_statuses.items():
            last_status = None
            for idx, eid, status in sorted(transitions, key=lambda x: x[0]):
                if last_status == "dead" and status != "alive":
                    # Character appears active after death without resurrection
                    pass
                last_status = status
            # Check if character appears in events after death without resurrection
            death_idx = None
            for idx, eid, status in sorted(transitions, key=lambda x: x[0]):
                if status == "dead":
                    death_idx = idx
                elif status == "alive":
                    death_idx = None
            if death_idx is not None:
                later_events = [
                    e for i, e in enumerate(events)
                    if i > death_idx and char in e.get("characters", [])
                ]
                if later_events:
                    warnings.append(QualityWarning(
                        severity="warning",
                        category="timeline",
                        message=f"Character '{char}' appears in events after apparent death without resurrection.",
                        location=f"character:{char}",
                    ))

        self._warnings.extend(warnings)
        return warnings

    def check_character_consistency(self, events: list[dict[str, Any]]) -> list[QualityWarning]:
        warnings: list[QualityWarning] = []
        character_event_groups: dict[str, list[str]] = {}
        character_event_count: dict[str, int] = {}
        for event in events:
            for char in event.get("characters", []):
                character_event_groups.setdefault(char, []).append(
                    event.get("event_group", "")
                )
                character_event_count[char] = character_event_count.get(char, 0) + 1

        # Check relationship events without supporting narrative
        for char, groups in character_event_groups.items():
            relationship_events = [g for g in groups if g in ("relationship", "emotion_romance")]
            if len(relationship_events) > 0:
                has_supporting = any(
                    g in ("conflict", "goal_progress", "revelation", "setup")
                    for g in groups
                )
                if not has_supporting:
                    warnings.append(QualityWarning(
                        severity="info",
                        category="character",
                        message=f"Character '{char}' has relationship events but no supporting narrative events.",
                        location=f"character:{char}",
                    ))

        # Check characters appearing only once (possible alias issue)
        for char, count in character_event_count.items():
            if count == 1:
                warnings.append(QualityWarning(
                    severity="info",
                    category="character",
                    message=f"Character '{char}' appears in only 1 event (possible unresolved alias).",
                    location=f"character:{char}",
                ))

        # Check characters with contradictory roles in close events
        char_roles: dict[str, list[tuple[int, str]]] = {}
        for idx, event in enumerate(events):
            group = event.get("event_group", "")
            for char in event.get("characters", []):
                char_roles.setdefault(char, []).append((idx, group))
        for char, roles in char_roles.items():
            if len(roles) < 2:
                continue
            for i in range(len(roles) - 1):
                idx_a, group_a = roles[i]
                idx_b, group_b = roles[i + 1]
                # Contradictory: helping in one event, conflicting in the next within 3 events
                if abs(idx_b - idx_a) <= 3:
                    contradictions = {
                        frozenset({"relationship", "conflict"}),
                        frozenset({"emotion_romance", "conflict"}),
                    }
                    if frozenset({group_a, group_b}) in contradictions:
                        warnings.append(QualityWarning(
                            severity="info",
                            category="character",
                            message=f"Character '{char}' has contradictory roles ({group_a} -> {group_b}) in close events.",
                            location=f"character:{char}",
                        ))
                        break  # One warning per character is enough

        self._warnings.extend(warnings)
        return warnings

    def check_plot_classification(
        self,
        events: list[dict[str, Any]],
        scored_events: list[dict[str, Any]],
    ) -> list[QualityWarning]:
        warnings: list[QualityWarning] = []
        score_map: dict[str, dict[str, Any]] = {}
        for se in scored_events:
            eid = se.get("event_id", "")
            if eid:
                score_map[eid] = se

        # Check if any high main-plot events exist
        main_plot_events = [
            e for e in events
            if score_map.get(e.get("event_id", ""), {}).get("main_plot_score", 0) >= 4
        ]
        if events and len(main_plot_events) < 1:
            warnings.append(QualityWarning(
                severity="warning",
                category="plot",
                message="No events classified as high main-plot relevance (main_plot_score >= 4).",
                location="global",
            ))

        # Check for main-plot score inflation (> 50% events marked high)
        if events:
            high_ratio = len(main_plot_events) / len(events)
            if high_ratio > 0.5:
                warnings.append(QualityWarning(
                    severity="warning",
                    category="plot",
                    message=f"{len(main_plot_events)}/{len(events)} ({high_ratio:.0%}) events have high main_plot_score -- possible inflation.",
                    location="global",
                ))

        # Check main-plot event coherence: do they cluster or scatter?
        if len(main_plot_events) >= 3:
            main_indices = []
            for e in main_plot_events:
                eid = e.get("event_id", "")
                for idx, ev in enumerate(events):
                    if ev.get("event_id") == eid:
                        main_indices.append(idx)
                        break
            if len(main_indices) >= 3:
                main_indices.sort()
                gaps = [main_indices[i + 1] - main_indices[i] for i in range(len(main_indices) - 1)]
                avg_gap = sum(gaps) / len(gaps) if gaps else 0
                max_gap = max(gaps) if gaps else 0
                # If max gap is more than 3x average, main plot is fragmented
                if avg_gap > 0 and max_gap > avg_gap * 3:
                    warnings.append(QualityWarning(
                        severity="info",
                        category="plot",
                        message=f"Main plot events are fragmented (max gap: {max_gap}, avg gap: {avg_gap:.1f}).",
                        location="global",
                    ))

        # Check subplot groups with unreasonably high scores
        subplot_events: dict[str, list[int]] = {}
        for e in events:
            eid = e.get("event_id", "")
            group = e.get("event_group", "")
            se = score_map.get(eid, {})
            main_score = int(se.get("main_plot_score", 0))
            if main_score < 5 and group:
                subplot_events.setdefault(group, []).append(main_score)

        for group, scores in subplot_events.items():
            avg = sum(scores) / len(scores) if scores else 0
            if avg >= 4:
                warnings.append(QualityWarning(
                    severity="warning",
                    category="plot",
                    message=f"Subplot group '{group}' has unreasonably high average main_plot_score ({avg:.1f}).",
                    location=f"event_group:{group}",
                ))

        self._warnings.extend(warnings)
        return warnings

    def generate_report(self) -> QualityReport:
        error_count = sum(1 for w in self._warnings if w.severity == "error")
        warning_count = sum(1 for w in self._warnings if w.severity == "warning")
        info_count = sum(1 for w in self._warnings if w.severity == "info")

        score = 100
        score -= error_count * 15
        score -= warning_count * 5
        score -= info_count * 1
        score = max(0, min(100, score))

        categories = set(w.category for w in self._warnings)
        parts = []
        if error_count:
            parts.append(f"{error_count} error(s)")
        if warning_count:
            parts.append(f"{warning_count} warning(s)")
        if info_count:
            parts.append(f"{info_count} info(s)")
        summary = f"Quality score: {score}/100."
        if parts:
            summary += f" Found {', '.join(parts)} across categories: {', '.join(sorted(categories))}."
        else:
            summary = f"Quality score: {score}/100. No issues detected."

        suggestions: list[str] = []
        if any(w.category == "completeness" and "few event" in w.message.lower() for w in self._warnings):
            suggestions.append("Consider reviewing chapters with very few events for missed extraction.")
        if any(w.category == "completeness" and "no high-climax" in w.message.lower() for w in self._warnings):
            suggestions.append("Some chapters lack climax events -- consider adjusting extraction prompts.")
        if any(w.category == "completeness" and "foreshadowing" in w.message.lower() for w in self._warnings):
            suggestions.append("Foreshadowing events detected without payoff -- check cross-chapter linkage.")
        if any(w.category == "timeline" for w in self._warnings):
            suggestions.append("Check causal ordering of events -- some causes appear after their effects.")
        if any(w.category == "character" and "only 1 event" in w.message.lower() for w in self._warnings):
            suggestions.append("Some characters appear only once -- may indicate unresolved aliases.")
        if any(w.category == "character" and "relationship" in w.message.lower() for w in self._warnings):
            suggestions.append("Some characters have relationship changes without supporting narrative context.")
        if any(w.category == "plot" and "inflation" in w.message.lower() for w in self._warnings):
            suggestions.append("Too many events marked as main plot -- scoring may need recalibration.")
        if any(w.category == "plot" and "fragmented" in w.message.lower() for w in self._warnings):
            suggestions.append("Main plot events are scattered -- narrative coherence may be weak.")
        if any(w.category == "plot" and "no events classified" in w.message.lower() for w in self._warnings):
            suggestions.append("No main plot detected -- review scoring thresholds.")

        # Build per-category stats
        stats: dict[str, int] = {}
        for w in self._warnings:
            stats[w.category] = stats.get(w.category, 0) + 1

        return QualityReport(
            overall_score=score,
            warnings=self._warnings,
            summary=summary,
            suggestions=suggestions,
        )

    def run_all_checks(
        self,
        chapters_data: list[dict[str, Any]],
    ) -> QualityReport:
        self._warnings = []

        self.check_event_completeness(chapters_data)

        all_events: list[dict[str, Any]] = []
        all_scored: list[dict[str, Any]] = []
        for chapter in chapters_data:
            normalized = chapter.get("normalized_events", {})
            events = normalized.get("events", [])
            all_events.extend(events)
            all_scored.extend(chapter.get("scores", []))

        self.check_timeline_consistency(all_events)
        self.check_character_consistency(all_events)
        self.check_plot_classification(all_events, all_scored)

        return self.generate_report()
