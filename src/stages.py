from __future__ import annotations

import json
from dataclasses import asdict
from typing import Protocol

from openai import OpenAI

from .config import Paths
from .models import EpisodeSummary, GenreClassification, JsonDict, NormalizedEvent, NormalizedEventSet, SceneChunk, SceneExtraction, SceneSplit, ScoredEvent
from .prompt_loader import load_prompt
from .schema_validator import SchemaValidationError, SchemaValidator


class LLMClient(Protocol):
    def complete_json(self, prompt: str) -> JsonDict:
        """Return a JSON-like dict parsed from the model response."""


class StubLLMClient:
    """Development stub. Replace with a real model client."""

    def complete_json(self, prompt: str) -> JsonDict:
        raise NotImplementedError("Implement LLMClient.complete_json with your model SDK.")


class OpenAILLMClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        system_prompt: str | None = None,
    ) -> None:
        kwargs: dict[str, str] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model = model
        self.system_prompt = system_prompt or (
            "You are a structured information extraction model. "
            "Always return strict JSON that matches the user's requested shape."
        )

    def complete_json(self, prompt: str) -> JsonDict:
        try:
            response = self._create_completion(prompt, json_mode=True)
            text = self._extract_text(response)
        except ValueError:
            text = ""
        if not text:
            response = self._create_completion(prompt, json_mode=False)
            text = self._extract_text(response)
        if text.startswith("```"):
            text = self._strip_code_fence(text)
        return json.loads(text)

    def _create_completion(self, prompt: str, json_mode: bool):
        kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        return self.client.chat.completions.create(**kwargs)

    def _extract_text(self, response) -> str:
        choices = getattr(response, "choices", None)
        if choices:
            message = choices[0].message
            content = message.content
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                text_parts: list[str] = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif hasattr(item, "text"):
                        text_parts.append(getattr(item, "text", ""))
                return "\n".join(part for part in text_parts if part).strip()
        provider_msg = getattr(response, "msg", None)
        if provider_msg:
            raise ValueError(f"Provider returned no choices: {provider_msg}")
        return ""

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()


class GenreClassifier:
    def __init__(self, client: LLMClient, paths: Paths, validator: SchemaValidator, max_retries: int = 2) -> None:
        self.client = client
        self.paths = paths
        self.validator = validator
        self.max_retries = max_retries

    def run(self, text: str) -> GenreClassification:
        prompt = self._build_prompt(text)
        result = self._complete_validated(prompt, "genre_classification.schema.json")
        return GenreClassification(**result)

    def _build_prompt(self, text: str) -> str:
        taxonomy = load_prompt(self.paths.prompts_dir / "novel_genre_taxonomy.md")
        return (
            "Classify this novel excerpt into the taxonomy below and output JSON only.\n\n"
            f"{taxonomy}\n\n"
            "Text:\n"
            f"{text}"
        )

    def _complete_validated(self, prompt: str, schema_name: str) -> JsonDict:
        current_prompt = prompt
        for attempt in range(self.max_retries + 1):
            result = self.client.complete_json(current_prompt)
            try:
                self.validator.validate(schema_name, result)
                return result
            except SchemaValidationError as exc:
                if attempt >= self.max_retries:
                    raise
                current_prompt = (
                    f"{prompt}\n\n"
                    "Your previous response did not match the required JSON shape.\n"
                    f"Validation error: {exc}\n"
                    "Return corrected JSON only."
                )
        raise RuntimeError("Unreachable")


class SceneSplitter:
    def __init__(self, client: LLMClient, paths: Paths, validator: SchemaValidator, max_retries: int = 2) -> None:
        self.client = client
        self.paths = paths
        self.validator = validator
        self.max_retries = max_retries

    def run(self, text: str) -> SceneSplit:
        prompt = self._build_prompt(text)
        result = self._complete_validated(prompt, "scene_split.schema.json")
        scenes = [SceneChunk(**item) for item in result["scenes"]]
        return SceneSplit(scenes=scenes)

    def _build_prompt(self, text: str) -> str:
        prompt_bank = load_prompt(self.paths.prompts_dir / "webnovel_prompts.md")
        return (
            f"{prompt_bank}\n\n"
            "Use the Scene Split Prompt section. Output JSON only.\n\n"
            f"Text:\n{text}"
        )

    def _complete_validated(self, prompt: str, schema_name: str) -> JsonDict:
        current_prompt = prompt
        for attempt in range(self.max_retries + 1):
            result = self.client.complete_json(current_prompt)
            try:
                self.validator.validate(schema_name, result)
                return result
            except SchemaValidationError as exc:
                if attempt >= self.max_retries:
                    raise
                current_prompt = (
                    f"{prompt}\n\n"
                    "Your previous response did not match the required JSON shape.\n"
                    f"Validation error: {exc}\n"
                    "Return corrected JSON only."
                )
        raise RuntimeError("Unreachable")


class SceneExtractor:
    def __init__(self, client: LLMClient, paths: Paths, validator: SchemaValidator, max_retries: int = 2) -> None:
        self.client = client
        self.paths = paths
        self.validator = validator
        self.max_retries = max_retries

    def run(self, scene: SceneChunk, genre_hint: str | None = None) -> SceneExtraction:
        prompt = self._build_prompt(scene, genre_hint)
        result = self._complete_validated(prompt, "extracted_events.schema.json")
        result = self._sanitize_result(result)
        return SceneExtraction(**result)

    def _build_prompt(self, scene: SceneChunk, genre_hint: str | None) -> str:
        prompt_bank = load_prompt(self.paths.prompts_dir / "webnovel_prompts.md")
        hint = f"Genre hint: {genre_hint}\n\n" if genre_hint else ""
        return (
            f"{prompt_bank}\n\n"
            "Use the Generic Scene Event Extraction section. Output JSON only.\n\n"
            f"{hint}"
            f"Scene metadata:\n{json.dumps(asdict(scene), ensure_ascii=False, indent=2)}\n\n"
            f"Text:\n{scene.text}"
        )

    def _complete_validated(self, prompt: str, schema_name: str) -> JsonDict:
        current_prompt = prompt
        for attempt in range(self.max_retries + 1):
            result = self._sanitize_result(self.client.complete_json(current_prompt))
            try:
                self.validator.validate(schema_name, result)
                return result
            except SchemaValidationError as exc:
                if attempt >= self.max_retries:
                    raise
                current_prompt = (
                    f"{prompt}\n\n"
                    "Your previous response did not match the required JSON shape.\n"
                    f"Validation error: {exc}\n"
                    "Return corrected JSON only."
                )
        raise RuntimeError("Unreachable")

    def _sanitize_result(self, result: JsonDict) -> JsonDict:
        allowed_scene_functions = {
            "setup",
            "transition",
            "conflict",
            "reveal",
            "relationship_push",
            "power_shift",
            "climax",
        }
        allowed_event_groups = {
            "setup",
            "goal_progress",
            "conflict",
            "revelation",
            "relationship",
            "status_shift",
            "resource_gain_loss",
            "scheme_intrigue",
            "emotion_romance",
            "world_rule",
            "transition",
            "climax_resolution",
        }
        scene_function_map = {
            "relationship": "relationship_push",
            "relationship_change": "relationship_push",
            "status_change": "power_shift",
            "status_shift": "power_shift",
            "revelation": "reveal",
            "reversal": "climax",
        }
        event_group_map = {
            "reversal": "climax_resolution",
            "climax": "climax_resolution",
            "romance": "emotion_romance",
            "emotion": "emotion_romance",
            "resource": "resource_gain_loss",
            "resource_change": "resource_gain_loss",
            "status": "status_shift",
            "status_change": "status_shift",
            "power_shift": "status_shift",
            "intrigue": "scheme_intrigue",
            "scheme": "scheme_intrigue",
            "reveal": "revelation",
        }
        if "scene_function" in result:
            raw_scene_function = str(result["scene_function"])
            normalized_scene_function = scene_function_map.get(raw_scene_function, raw_scene_function)
            result["scene_function"] = (
                normalized_scene_function if normalized_scene_function in allowed_scene_functions else "conflict"
            )
        for event in result.get("events", []):
            raw_group = str(event.get("event_group", "")).strip()
            if "." in raw_group:
                raw_group = raw_group.split(".", 1)[0]
            if not raw_group and event.get("event_type"):
                raw_group = str(event["event_type"]).split(".", 1)[0]
            normalized_group = event_group_map.get(raw_group, raw_group)
            if normalized_group not in allowed_event_groups:
                event_type = str(event.get("event_type", "")).lower()
                if any(token in event_type for token in ["victory", "defeat", "turn", "payoff", "hook"]):
                    normalized_group = "climax_resolution"
                elif any(token in event_type for token in ["identity", "secret", "truth", "reveal"]):
                    normalized_group = "revelation"
                elif any(token in event_type for token in ["rank", "status", "faction", "power"]):
                    normalized_group = "status_shift"
                elif any(token in event_type for token in ["romance", "confession", "jealousy", "affection"]):
                    normalized_group = "emotion_romance"
                else:
                    normalized_group = "goal_progress"
            event["event_group"] = normalized_group
        return result


class EventScorer:
    def __init__(self, client: LLMClient, paths: Paths, validator: SchemaValidator, max_retries: int = 2) -> None:
        self.client = client
        self.paths = paths
        self.validator = validator
        self.max_retries = max_retries

    def run(self, normalized_events: NormalizedEventSet) -> list[ScoredEvent]:
        prompt = self._build_prompt(normalized_events)
        result = self._complete_validated(prompt, "event_scores.schema.json")
        return [ScoredEvent(**item) for item in result["events"]]

    def _build_prompt(self, normalized_events: NormalizedEventSet) -> str:
        prompt_bank = load_prompt(self.paths.prompts_dir / "webnovel_prompts.md")
        return (
            f"{prompt_bank}\n\n"
            "Use the Scoring Prompt section. Output JSON only.\n\n"
            f"Events:\n{json.dumps(asdict(normalized_events), ensure_ascii=False, indent=2)}"
        )

    def _complete_validated(self, prompt: str, schema_name: str) -> JsonDict:
        current_prompt = prompt
        for attempt in range(self.max_retries + 1):
            result = self.client.complete_json(current_prompt)
            try:
                self.validator.validate(schema_name, result)
                return result
            except SchemaValidationError as exc:
                if attempt >= self.max_retries:
                    raise
                current_prompt = (
                    f"{prompt}\n\n"
                    "Your previous response did not match the required JSON shape.\n"
                    f"Validation error: {exc}\n"
                    "Return corrected JSON only."
                )
        raise RuntimeError("Unreachable")


class EpisodeBuilder:
    def __init__(self, client: LLMClient, paths: Paths, validator: SchemaValidator, max_retries: int = 2) -> None:
        self.client = client
        self.paths = paths
        self.validator = validator
        self.max_retries = max_retries

    def run(self, normalized_events: NormalizedEventSet, scored_events: list[ScoredEvent]) -> EpisodeSummary:
        prompt = self._build_prompt(normalized_events, scored_events)
        result = self._complete_validated(prompt, "episode_summary.schema.json")
        return EpisodeSummary(**result)

    def _build_prompt(self, normalized_events: NormalizedEventSet, scored_events: list[ScoredEvent]) -> str:
        prompt_bank = load_prompt(self.paths.prompts_dir / "webnovel_prompts.md")
        payload = {
            "normalized_events": asdict(normalized_events),
            "scores": [asdict(item) for item in scored_events],
        }
        return (
            f"{prompt_bank}\n\n"
            "Use the Episode Summary Prompt section. Output JSON only.\n\n"
            f"Input:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    def _complete_validated(self, prompt: str, schema_name: str) -> JsonDict:
        current_prompt = prompt
        for attempt in range(self.max_retries + 1):
            result = self.client.complete_json(current_prompt)
            try:
                self.validator.validate(schema_name, result)
                return result
            except SchemaValidationError as exc:
                if attempt >= self.max_retries:
                    raise
                current_prompt = (
                    f"{prompt}\n\n"
                    "Your previous response did not match the required JSON shape.\n"
                    f"Validation error: {exc}\n"
                    "Return corrected JSON only."
                )
        raise RuntimeError("Unreachable")


class EventNormalizer:
    def __init__(self, client: LLMClient, paths: Paths, validator: SchemaValidator, max_retries: int = 2) -> None:
        self.client = client
        self.paths = paths
        self.validator = validator
        self.max_retries = max_retries

    def run(self, extractions: list[SceneExtraction]) -> NormalizedEventSet:
        prompt = self._build_prompt(extractions)
        result = self._complete_validated(prompt, "normalized_events.schema.json")
        return NormalizedEventSet(events=[NormalizedEvent(**item) for item in result["events"]])

    def _build_prompt(self, extractions: list[SceneExtraction]) -> str:
        prompt_bank = load_prompt(self.paths.prompts_dir / "webnovel_prompts.md")
        payload = [asdict(item) for item in extractions]
        return (
            f"{prompt_bank}\n\n"
            "Use the Event Normalization Prompt section. Output JSON only.\n\n"
            f"Input:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    def _complete_validated(self, prompt: str, schema_name: str) -> JsonDict:
        current_prompt = prompt
        for attempt in range(self.max_retries + 1):
            result = self.client.complete_json(current_prompt)
            try:
                self.validator.validate(schema_name, result)
                return result
            except SchemaValidationError as exc:
                if attempt >= self.max_retries:
                    raise
                current_prompt = (
                    f"{prompt}\n\n"
                    "Your previous response did not match the required JSON shape.\n"
                    f"Validation error: {exc}\n"
                    "Return corrected JSON only."
                )
        raise RuntimeError("Unreachable")
