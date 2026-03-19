from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from .models import CausalAnalysisResult, CausalChain, Foreshadowing, NormalizedEvent
from .prompt_loader import load_prompt, render_prompt


class CausalEngine:
    """Processes LLM causal analysis output and applies it to normalized events.

    Maintains cross-chapter state for foreshadowing accumulation.
    """

    def __init__(self, prompts_dir: Path | None = None) -> None:
        self._unresolved_foreshadowing: list[Foreshadowing] = []
        self._active_chains: list[CausalChain] = []
        self._prompts_dir = prompts_dir

    @property
    def unresolved_foreshadowing(self) -> list[Foreshadowing]:
        return [f for f in self._unresolved_foreshadowing if f.status == "planted"]

    def unresolved_foreshadowing_dicts(self) -> list[dict[str, Any]]:
        return [asdict(f) for f in self.unresolved_foreshadowing]

    def get_unresolved_foreshadowing(self) -> list[Foreshadowing]:
        """Return all foreshadowing items still in 'planted' status."""
        return self.unresolved_foreshadowing

    def analyze_chapter(
        self,
        chapter_id: str,
        normalized_events: list[dict[str, Any]],
        llm_analyze_fn: Callable[[str], dict[str, Any]],
    ) -> CausalAnalysisResult:
        """Main entry point: build prompt, call LLM, process result.

        Args:
            chapter_id: Identifier for the current chapter.
            normalized_events: Events as dicts (from pipeline normalization stage).
            llm_analyze_fn: Callable that takes a prompt string and returns parsed JSON dict.

        Returns:
            CausalAnalysisResult with links, chains, and foreshadowing.
        """
        prompt = self._build_prompt(normalized_events)
        llm_result = llm_analyze_fn(prompt)
        events = [self._event_from_dict(e) for e in normalized_events]
        return self.process_llm_result(events, llm_result, chapter_id)

    def _build_prompt(self, normalized_events: list[dict[str, Any]]) -> str:
        """Load the causal_analysis.md template and render with current data."""
        if self._prompts_dir is not None:
            template = load_prompt(self._prompts_dir / "causal_analysis.md")
        else:
            template = load_prompt(Path(__file__).resolve().parent.parent / "prompts" / "causal_analysis.md")
        events_json = json.dumps(normalized_events, ensure_ascii=False, indent=2)
        unresolved = self.unresolved_foreshadowing_dicts()
        unresolved_json = json.dumps(unresolved, ensure_ascii=False, indent=2) if unresolved else "None"
        return render_prompt(
            template,
            events=events_json,
            unresolved_foreshadowing=unresolved_json,
        )

    @staticmethod
    def _event_from_dict(d: dict[str, Any]) -> NormalizedEvent:
        """Convert a normalized event dict back to a NormalizedEvent dataclass."""
        return NormalizedEvent(
            event_id=d.get("event_id", ""),
            source_scene_ids=d.get("source_scene_ids", []),
            event_group=d.get("event_group", ""),
            event_type=d.get("event_type", ""),
            title=d.get("title", ""),
            description=d.get("description", ""),
            characters=d.get("characters", []),
            cause=d.get("cause", ""),
            consequence=d.get("consequence", ""),
            must_keep=d.get("must_keep", False),
            causes=d.get("causes", []),
            effects=d.get("effects", []),
            preconditions=d.get("preconditions", []),
            foreshadowing_for=d.get("foreshadowing_for"),
            foreshadowed_by=d.get("foreshadowed_by"),
            causal_chain_id=d.get("causal_chain_id"),
        )

    def export(self) -> dict[str, Any]:
        """Return accumulated cross-chapter state for artifact output."""
        return self.snapshot()

    def build_causal_links(
        self,
        events: list[NormalizedEvent],
        llm_links: list[dict[str, Any]],
    ) -> list[NormalizedEvent]:
        event_map = {e.event_id: e for e in events}
        valid_ids = set(event_map.keys())
        for link in llm_links:
            cause_id = link.get("cause_event_id", "")
            effect_id = link.get("effect_event_id", "")
            if cause_id not in valid_ids or effect_id not in valid_ids:
                continue
            relation = link.get("relation_type", "")
            cause_evt = event_map[cause_id]
            effect_evt = event_map[effect_id]
            if relation in ("direct_cause", "indirect_influence", "foreshadowing_payoff"):
                if effect_id not in cause_evt.effects:
                    cause_evt.effects.append(effect_id)
                if cause_id not in effect_evt.causes:
                    effect_evt.causes.append(cause_id)
            elif relation == "precondition":
                desc = link.get("description", "")
                if desc and desc not in effect_evt.preconditions:
                    effect_evt.preconditions.append(desc)
                if cause_id not in effect_evt.causes:
                    effect_evt.causes.append(cause_id)
        return events

    def detect_foreshadowing(
        self,
        events: list[NormalizedEvent],
        llm_foreshadowing: list[dict[str, Any]],
        chapter_id: str = "",
    ) -> list[Foreshadowing]:
        event_map = {e.event_id: e for e in events}
        new_items: list[Foreshadowing] = []
        for item in llm_foreshadowing:
            fid = item.get("foreshadow_id", "")
            setup_id = item.get("setup_event_id", "")
            payoff_id = item.get("payoff_event_id") or None
            status = item.get("status", "planted")
            desc = item.get("description", "")
            if not fid or not setup_id:
                continue
            fs = Foreshadowing(
                foreshadow_id=fid,
                setup_event_id=setup_id,
                setup_chapter=chapter_id,
                payoff_event_id=payoff_id,
                payoff_chapter=chapter_id if payoff_id else None,
                description=desc,
                status=status,
            )
            new_items.append(fs)
            # Annotate events with foreshadowing links
            if setup_id in event_map and status == "planted":
                event_map[setup_id].foreshadowing_for = payoff_id
            if payoff_id and payoff_id in event_map and status == "recovered":
                event_map[payoff_id].foreshadowed_by = setup_id
                # Also resolve matching unresolved foreshadowing from history
                for existing in self._unresolved_foreshadowing:
                    if existing.setup_event_id == setup_id and existing.status == "planted":
                        existing.status = "recovered"
                        existing.payoff_event_id = payoff_id
                        existing.payoff_chapter = chapter_id
        # Add new items to accumulator
        for fs in new_items:
            # Avoid duplicates by foreshadow_id
            existing_ids = {f.foreshadow_id for f in self._unresolved_foreshadowing}
            if fs.foreshadow_id not in existing_ids:
                self._unresolved_foreshadowing.append(fs)
        return new_items

    def build_causal_chains(
        self,
        events: list[NormalizedEvent],
        llm_chains: list[dict[str, Any]],
    ) -> list[CausalChain]:
        event_map = {e.event_id: e for e in events}
        valid_ids = set(event_map.keys())
        new_chains: list[CausalChain] = []
        for item in llm_chains:
            chain_id = item.get("chain_id", "")
            title = item.get("title", "")
            chain_events = [eid for eid in item.get("events", []) if eid in valid_ids]
            if not chain_id or len(chain_events) < 2:
                continue
            chain = CausalChain(
                chain_id=chain_id,
                title=title,
                events=chain_events,
                chain_type=item.get("chain_type", "main_plot"),
                status=item.get("status", "active"),
            )
            new_chains.append(chain)
            # Annotate events with chain membership
            for eid in chain_events:
                if eid in event_map:
                    event_map[eid].causal_chain_id = chain_id
        # Merge into active chains accumulator
        existing_chain_ids = {c.chain_id for c in self._active_chains}
        for chain in new_chains:
            if chain.chain_id in existing_chain_ids:
                # Extend existing chain with new events
                for existing in self._active_chains:
                    if existing.chain_id == chain.chain_id:
                        for eid in chain.events:
                            if eid not in existing.events:
                                existing.events.append(eid)
                        existing.status = chain.status
                        break
            else:
                self._active_chains.append(chain)
        return new_chains

    def process_llm_result(
        self,
        events: list[NormalizedEvent],
        llm_result: dict[str, Any],
        chapter_id: str = "",
    ) -> CausalAnalysisResult:
        """Apply full LLM causal analysis output to events. Returns structured result."""
        links = llm_result.get("causal_links", [])
        fs_items = llm_result.get("foreshadowing", [])
        chain_items = llm_result.get("chains", [])

        self.build_causal_links(events, links)
        foreshadowing = self.detect_foreshadowing(events, fs_items, chapter_id)
        chains = self.build_causal_chains(events, chain_items)

        return CausalAnalysisResult(
            causal_links=links,
            chains=chains,
            foreshadowing=foreshadowing,
        )

    def snapshot(self) -> dict[str, Any]:
        """Return accumulated cross-chapter state for artifact output."""
        return {
            "unresolved_foreshadowing": [asdict(f) for f in self.unresolved_foreshadowing],
            "active_chains": [asdict(c) for c in self._active_chains],
        }

    def full_snapshot(self) -> dict[str, Any]:
        """Full serializable snapshot for cross-run checkpoint (lossless)."""
        return {
            "all_foreshadowing": [asdict(f) for f in self._unresolved_foreshadowing],
            "active_chains": [asdict(c) for c in self._active_chains],
        }

    def restore(self, data: dict[str, Any]) -> None:
        """Restore full state from a previous full_snapshot."""
        from .serialization import foreshadowing_from_dict, causal_chain_from_dict
        self._unresolved_foreshadowing = [
            foreshadowing_from_dict(f)
            for f in data.get("all_foreshadowing", [])
        ]
        self._active_chains = [
            causal_chain_from_dict(c)
            for c in data.get("active_chains", [])
        ]
