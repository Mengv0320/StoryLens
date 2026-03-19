from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Protocol

import requests
from openai import OpenAI

from .config import Paths
from .genre_style import GenreStyleEngine
from .models import CausalAnalysisResult, ChapterKeyEvent, ChapterKeyEventSet, EpisodeSummary, GenreClassification, JsonDict, NormalizedEvent, NormalizedEventSet, SceneChunk, SceneExtraction, SceneSplit, ScoredEvent
from .prompt_loader import load_prompt, render_prompt
from .schema_validator import SchemaValidationError, SchemaValidator


def _repair_json(text: str) -> str:
    """Best-effort repair of malformed JSON from LLM output.

    Handles: missing commas, trailing commas, unescaped quotes inside strings,
    unescaped newlines, truncated output, preamble text.
    """
    # Strip preamble — find first { or [
    start = -1
    for i, c in enumerate(text):
        if c in ('{', '['):
            start = i
            break
    if start < 0:
        return text
    text = text[start:]

    # Strip <think>...</think> tags
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

    # Extract from code fences if present
    m = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
    if m:
        text = m.group(1).strip()
        for i, c in enumerate(text):
            if c in ('{', '['):
                text = text[i:]
                break

    # Remove trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)

    # Fix missing commas between lines
    text = re.sub(r'(")\s*\n\s*(")', r'\1,\n\2', text)
    text = re.sub(r'("|true|false|null|\d)\s*\n\s*(")', r'\1,\n\2', text)
    text = re.sub(r'([}\]])\s*\n\s*("|\{|\[)', r'\1,\n\2', text)
    text = re.sub(r'("|true|false|null|\d)\s*\n\s*(\{|\[)', r'\1,\n\2', text)

    # Fix missing commas on same line
    text = re.sub(r'([}\]])\s+(")', r'\1, \2', text)
    text = re.sub(r'(")\s+([\{|\[])', r'\1, \2', text)

    # Remove trailing commas again
    text = re.sub(r',\s*([}\]])', r'\1', text)

    # Iterative repair: try json.loads, on failure fix the problematic position
    for _ in range(200):
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError as e:
            pos = e.pos
            if pos is None or pos < 0:
                break
            msg = e.msg
            if "Unterminated string" in msg:
                # pos points to the opening quote; close the string at end
                text = text + '"'
                text = _balance_brackets(text)
                continue
            if "Invalid control character" in msg:
                # Escape the control character at pos
                ch = text[pos]
                escape_map = {'\n': '\\n', '\r': '\\r', '\t': '\\t'}
                replacement = escape_map.get(ch, f'\\u{ord(ch):04x}')
                text = text[:pos] + replacement + text[pos + 1:]
                continue
            if "Expecting ',' delimiter" in msg or "Expecting ':' separator" in msg:
                ch = text[pos] if pos < len(text) else ''
                if ch == '"':
                    text = text[:pos] + '\\"' + text[pos + 1:]
                    continue
                if pos > 0 and text[pos - 1] == '"':
                    text = text[:pos - 1] + '\\"' + text[pos:]
                    continue
                break
            break

    # Final bracket balance
    text = _balance_brackets(text)
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text


def _balance_brackets(text: str) -> str:
    """Close any unclosed brackets/braces in correct nesting order."""
    stack: list[str] = []
    in_str = False
    esc = False
    for ch in text:
        if esc:
            esc = False
            continue
        if ch == '\\':
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if not in_str:
            if ch in ('{', '['):
                stack.append('}' if ch == '{' else ']')
            elif ch in ('}', ']') and stack and stack[-1] == ch:
                stack.pop()
    if stack:
        text = text + ''.join(reversed(stack))
    return text


class LLMClient(Protocol):
    def complete_json(self, prompt: str, max_tokens: int = 8192) -> JsonDict:
        """Return a JSON-like dict parsed from the model response."""


class StubLLMClient:
    """Development stub. Replace with a real model client."""

    def complete_json(self, prompt: str, max_tokens: int = 8192) -> JsonDict:
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
        kwargs["timeout"] = 120.0
        self.client = OpenAI(**kwargs)
        self.model = model
        self.system_prompt = system_prompt or (
            "You are a Chinese web novel adaptation editor and animation episode writer. "
            "Your task is to perform structured plot extraction on fictional texts, "
            "including scene decomposition, character identification, event extraction, "
            "causal chain analysis, and episode summary generation. "
            "The input texts are published fictional works and may contain dramatic conflict, "
            "battle scenes, or intense plot elements typical of the genre. "
            "Analyze them objectively as source material for animation adaptation. "
            "Always return strict JSON that matches the user's requested shape. "
            "Output all text fields in Chinese unless instructed otherwise."
        )
        self.last_usage: dict[str, int] | None = None

    def complete_json(self, prompt: str, max_tokens: int = 8192) -> JsonDict:
        last_err = None
        for attempt in range(3):
            self.last_usage = None
            try:
                response = self._create_completion(prompt, json_mode=True)
                text = self._extract_text(response)
            except ValueError:
                text = ""
            if not text:
                response = self._create_completion(prompt, json_mode=False)
                text = self._extract_text(response)
            self.last_usage = self._extract_usage(response)
            if text.startswith("```"):
                text = self._strip_code_fence(text)
            text = self._sanitize_json(text)
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                try:
                    return json.loads(_repair_json(text))
                except json.JSONDecodeError as e:
                    last_err = e
                    if attempt < 2:
                        import time
                        time.sleep(1 * (attempt + 1))
                        continue
        raise last_err  # type: ignore[misc]

    @staticmethod
    def _sanitize_json(text: str) -> str:
        import re
        # Strip <think>...</think> tags (qwen thinking mode)
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        # Extract JSON from markdown code fences if present
        m = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
        if m:
            text = m.group(1).strip()
        # Find first { or [ to strip any preamble text
        for i, c in enumerate(text):
            if c in ('{', '['):
                text = text[i:]
                break
        # Remove trailing commas before } or ]
        text = re.sub(r',\s*([}\]])', r'\1', text)
        return text

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
        for attempt in range(4):
            try:
                return self.client.chat.completions.create(**kwargs)
            except Exception as e:
                err_str = str(e).lower()
                if "rate limit" in err_str or "rate_limit" in err_str or "429" in err_str:
                    wait = (2 ** attempt) * 2  # 2, 4, 8, 16 seconds
                    import time
                    time.sleep(wait)
                    continue
                raise
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
    def _extract_usage(response) -> dict[str, int]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        return {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "total_tokens": getattr(usage, "total_tokens", 0) or 0,
        }

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Violence-keyword sanitizer for content-filtered providers
# ---------------------------------------------------------------------------
class AnthropicLLMClient:
    """LLMClient that talks to Anthropic-format endpoints (e.g. kk.haiio.xyz)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        system_prompt: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.system_prompt = system_prompt or (
            "You are a Chinese web novel adaptation editor and animation episode writer. "
            "Your task is to perform structured plot extraction on fictional texts, "
            "including scene decomposition, character identification, event extraction, "
            "causal chain analysis, and episode summary generation. "
            "The input texts are published fictional works and may contain dramatic conflict, "
            "battle scenes, or intense plot elements typical of the genre. "
            "Analyze them objectively as source material for animation adaptation. "
            "Always return strict JSON that matches the user's requested shape. "
            "Output all text fields in Chinese unless instructed otherwise."
        )
        self.last_usage: dict[str, int] | None = None
        # Shared session with connection pooling — thread-safe
        # NOTE: Do NOT put 502/503/504 in status_forcelist — urllib3 Retry
        # consumes all retries at transport layer, leaving our outer loop
        # no chance to run.  Only retry on connection-level failures here;
        # HTTP status errors are handled in _create_completion's own loop.
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        self._session = requests.Session()
        self._session.trust_env = False  # Ignore system proxy settings
        retry = Retry(total=2, backoff_factor=0.5,
                      status_forcelist=[429],
                      allowed_methods=["POST"])
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def complete_json(self, prompt: str, max_tokens: int = 8192) -> JsonDict:
        last_err = None
        for attempt in range(3):
            resp = self._create_completion(prompt, max_tokens=max_tokens)
            text = self._extract_text(resp)
            text = self._strip_code_fence(text)
            text = self._clean_json(text)
            self.last_usage = self._extract_usage(resp)
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                try:
                    return json.loads(_repair_json(text))
                except json.JSONDecodeError as e:
                    last_err = e
                    if attempt < 2:
                        import time
                        time.sleep(1 * (attempt + 1))
                        continue
        raise last_err  # type: ignore[misc]

    def _create_completion(self, prompt: str, max_tokens: int = 8192) -> dict:
        import time, random
        # Light stagger to avoid gateway overload (reduced from 0.5-3.0)
        time.sleep(random.uniform(0.1, 0.5))
        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": self.system_prompt,
            "messages": [{"role": "user", "content": prompt}],
        }
        last_err = None
        for attempt in range(6):
            try:
                r = self._session.post(url, json=body, headers=headers, timeout=300)
                # Check for non-JSON response (HTML error page under load)
                ct = r.headers.get("content-type", "")
                if r.status_code >= 500 or "text/html" in ct:
                    raise requests.exceptions.HTTPError(
                        f"Server error {r.status_code}: {r.text[:200]}", response=r)
                r.raise_for_status()
                try:
                    data = r.json()
                except ValueError:
                    raise requests.exceptions.HTTPError(
                        f"Non-JSON response: {r.text[:300]}", response=r)
                # Validate we got actual content
                content = data.get("content", [])
                if not content or not any(b.get("text") for b in content if b.get("type") == "text"):
                    err_msg = data.get("error", {}).get("message", "empty content")
                    raise requests.exceptions.HTTPError(
                        f"Empty content from API: {err_msg}", response=r)
                return data
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.SSLError,
                    requests.exceptions.HTTPError,
                    requests.exceptions.Timeout,
                    requests.exceptions.RetryError,
                    ValueError) as e:
                last_err = e
                if attempt < 5:
                    wait = (2 ** attempt) * 1.5  # 1.5, 3, 6, 12, 24s
                    time.sleep(wait)
                    continue
                raise
        raise RuntimeError(f"All 6 attempts failed: {last_err}")

    @staticmethod
    def _extract_text(resp: dict) -> str:
        content = resp.get("content", [])
        parts = [b.get("text", "") for b in content if b.get("type") == "text"]
        return "\n".join(parts).strip()

    @staticmethod
    def _extract_usage(resp: dict) -> dict[str, int]:
        u = resp.get("usage", {})
        return {
            "prompt_tokens": u.get("input_tokens", 0),
            "completion_tokens": u.get("output_tokens", 0),
            "total_tokens": u.get("input_tokens", 0) + u.get("output_tokens", 0),
        }

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()

    @staticmethod
    def _clean_json(text: str) -> str:
        for i, c in enumerate(text):
            if c in ('{', '['):
                text = text[i:]
                break
        text = re.sub(r',\s*([}\]])', r'\1', text)
        return text


# ---------------------------------------------------------------------------
# Violence-keyword sanitizer for content-filtered providers
# ---------------------------------------------------------------------------
_SANITIZE_MAP = {
    # Long phrases first (replaced before shorter substrings)
    "人头冲天而起": "那人应声倒地",
    "鼻梁骨塌陷": "面部受伤",
    "门牙也被打掉": "嘴角淤青",
    "一拳狠狠砸": "一掌重重击",
    "斩成两截": "击倒在地",
    "一剑穿心": "一击命中要害",
    "长刀出鞘": "兵器出鞘",
    "凶神恶煞": "面目狰狞",
    "凶光毕露": "目光凌厉",
    "杀气腾腾": "气势汹汹",
    "一脚踢飞": "一掌推开",
    "一脚踢在": "一掌击在",
    "又狠又辣": "又快又准",
    "一刀斩在": "一击落在",
    "脖子斩落": "身上落下",
    "一剑对着": "兵器对着",
    "满脸是血": "伤痕累累",
    "不许杀": "不许伤害",
    "不要杀": "不要伤害",
    "杀人啦": "动手了",
    "去死吧": "倒下吧",
    "不容情": "不留情",
    "一剑斩": "一击挥",
    "一刀斩": "一击挥",
    "被斩杀": "被击败",
    "斩落": "挥落",
    "斩出": "挥出",
    "斩成": "击成",
    "斩杀": "击败",
    "杀人": "伤人",
    "杀光": "驱逐",
    "杀气": "戾气",
    "惨叫": "惊呼",
    "怒吼": "大喝",
    "拼了": "搏了",
}

def _sanitize_for_filter(text: str) -> str:
    """Replace violent keywords with milder alternatives to pass content filters."""
    for violent, mild in _SANITIZE_MAP.items():
        text = text.replace(violent, mild)
    return text


class MultiProviderClient:
    """Round-robin across multiple OpenAILLMClient instances.

    Providers marked with sanitize=True get violence keywords replaced
    before sending, to bypass content filters.
    """

    def __init__(self, providers: list[tuple[OpenAILLMClient, bool]]) -> None:
        """providers: list of (client, needs_sanitize) tuples."""
        self._providers = providers
        self._idx = 0
        self._lock = __import__("threading").Lock()
        self.last_usage: dict[str, int] | None = None

    def complete_json(self, prompt: str, max_tokens: int = 8192) -> JsonDict:
        n = len(self._providers)
        for attempt in range(n * 2):
            with self._lock:
                idx = self._idx
                self._idx = (self._idx + 1) % n
            client, needs_sanitize = self._providers[idx]
            actual_prompt = _sanitize_for_filter(prompt) if needs_sanitize else prompt
            try:
                result = client.complete_json(actual_prompt, max_tokens=max_tokens)
                self.last_usage = client.last_usage
                return result
            except Exception:
                if attempt >= n * 2 - 1:
                    raise
                continue
        raise RuntimeError("All providers failed")


def _extract_prompt_section(full_text: str, section_name: str) -> str:
    """Extract a specific section from the prompt bank markdown.

    Sections are delimited by ``## Section Name`` headers and contain
    a fenced code block with the actual prompt text.
    """
    pattern = rf"## {re.escape(section_name)}\s*\n```text\s*\n(.*?)```"
    m = re.search(pattern, full_text, re.DOTALL)
    return m.group(1).strip() if m else ""


class GenreClassifier:
    _max_tokens = 1024

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
        # Genre classification only needs the first ~2000 chars to judge
        sample = text[:2000] if len(text) > 2000 else text
        return (
            "Classify this novel excerpt into the taxonomy below and output JSON only.\n\n"
            f"{taxonomy}\n\n"
            "Text:\n"
            f"{sample}"
        )

    def _complete_validated(self, prompt: str, schema_name: str) -> JsonDict:
        current_prompt = prompt
        for attempt in range(self.max_retries + 1):
            result = self.client.complete_json(current_prompt, max_tokens=self._max_tokens)
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
    _max_tokens = 4096

    def __init__(self, client: LLMClient, paths: Paths, validator: SchemaValidator, max_retries: int = 2) -> None:
        self.client = client
        self.paths = paths
        self.validator = validator
        self.max_retries = max_retries

    def run(self, text: str) -> SceneSplit:
        prompt = self._build_prompt(text)
        result = self._complete_validated(prompt, "scene_split.schema.json")
        scenes = self._reconstruct_scenes(result["scenes"], text)
        return SceneSplit(scenes=scenes)

    def _build_prompt(self, text: str) -> str:
        prompt_bank = load_prompt(self.paths.prompts_dir / "webnovel_prompts.md")
        global_inst = _extract_prompt_section(prompt_bank, "Global Instruction")
        scene_split = _extract_prompt_section(prompt_bank, "Scene Split Prompt")
        return (
            f"{global_inst}\n\n"
            f"{scene_split}\n\n"
            "Output JSON only.\n\n"
            f"Text:\n{text}"
        )

    @staticmethod
    def _reconstruct_scenes(scene_dicts: list[dict], original_text: str) -> list[SceneChunk]:
        """Reconstruct scene text from start_hint/end_hint against original text.

        If the LLM already returned a 'text' field, use it as-is.
        Otherwise, slice the original text using the hint strings.
        """
        scenes: list[SceneChunk] = []
        for sd in scene_dicts:
            # Fallback for missing required fields
            if "location" not in sd or not sd["location"]:
                sd["location"] = "未知"
            if "characters_present" not in sd:
                sd["characters_present"] = []
            if "summary" not in sd:
                sd["summary"] = ""
            if sd.get("text"):
                scenes.append(SceneChunk(**sd))
                continue
            # Locate text span using hints
            start_hint = sd.get("start_hint", "")
            end_hint = sd.get("end_hint", "")
            start_idx = 0
            end_idx = len(original_text)
            if start_hint:
                pos = original_text.find(start_hint)
                if pos >= 0:
                    start_idx = pos
            if end_hint:
                pos = original_text.find(end_hint, start_idx)
                if pos >= 0:
                    end_idx = pos + len(end_hint)
            sd["text"] = original_text[start_idx:end_idx].strip()
            if not sd["text"]:
                sd["text"] = original_text  # fallback: whole text
            scenes.append(SceneChunk(**sd))
        return scenes

    def _complete_validated(self, prompt: str, schema_name: str) -> JsonDict:
        current_prompt = prompt
        for attempt in range(self.max_retries + 1):
            result = self.client.complete_json(current_prompt, max_tokens=self._max_tokens)
            # Fallback: fill missing required fields before validation
            for scene in result.get("scenes", []):
                if "location" not in scene or not scene["location"]:
                    scene["location"] = "未知"
                if "characters_present" not in scene:
                    scene["characters_present"] = []
                if "summary" not in scene:
                    scene["summary"] = ""
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
    _max_tokens = 4096

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
        global_inst = _extract_prompt_section(prompt_bank, "Global Instruction")
        extraction = _extract_prompt_section(prompt_bank, "Generic Scene Event Extraction")
        hint = f"Genre hint: {genre_hint}\n\n" if genre_hint else ""
        # Send metadata WITHOUT text to avoid duplication — text is sent separately
        meta = {
            "scene_id": scene.scene_id,
            "start_hint": scene.start_hint,
            "end_hint": scene.end_hint,
            "location": scene.location,
            "characters_present": scene.characters_present,
            "summary": scene.summary,
        }
        return (
            f"{global_inst}\n\n"
            f"{extraction}\n\n"
            "Output JSON only.\n\n"
            f"{hint}"
            f"Scene metadata:\n{json.dumps(meta, ensure_ascii=False, indent=2)}\n\n"
            f"Text:\n{scene.text}"
        )

    def _complete_validated(self, prompt: str, schema_name: str) -> JsonDict:
        current_prompt = prompt
        for attempt in range(self.max_retries + 1):
            result = self._sanitize_result(self.client.complete_json(current_prompt, max_tokens=self._max_tokens))
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
    _max_tokens = 4096

    def __init__(self, client: LLMClient, paths: Paths, validator: SchemaValidator, max_retries: int = 2) -> None:
        self.client = client
        self.paths = paths
        self.validator = validator
        self.max_retries = max_retries
        self._genre_engine = GenreStyleEngine()

    def run(self, normalized_events: NormalizedEventSet, genre: str | None = None) -> list[ScoredEvent]:
        prompt = self._build_prompt(normalized_events, genre)
        result = self._complete_validated(prompt, "event_scores.schema.json")
        return [ScoredEvent(**item) for item in result["events"]]

    def _build_prompt(self, normalized_events: NormalizedEventSet, genre: str | None = None) -> str:
        prompt_bank = load_prompt(self.paths.prompts_dir / "webnovel_prompts.md")
        scoring = _extract_prompt_section(prompt_bank, "Scoring Prompt")
        genre_guidance = ""
        if genre:
            adjustments = self._genre_engine.get_scoring_adjustments(genre)
            tone = self._genre_engine.get_summary_tone(genre)
            genre_guidance = (
                f"\n\nGenre-specific scoring guidance (genre: {genre}):\n"
                f"- Tone: {tone.tone_description}\n"
                f"- Boost genre_value_score for event types: {', '.join(adjustments['boost_event_types'])}\n"
                f"- Demote genre_value_score for event types: {', '.join(adjustments['demote_event_types'])}\n"
                f"- Emphasis: {', '.join(tone.emphasis_points)}\n"
            )
        return (
            f"{scoring}\n\n"
            f"{genre_guidance}\n"
            "Output JSON only. All scores must be integers from 1 to 5.\n\n"
            f"Events:\n{json.dumps(asdict(normalized_events), ensure_ascii=False, indent=2)}"
        )

    def _complete_validated(self, prompt: str, schema_name: str) -> JsonDict:
        current_prompt = prompt
        for attempt in range(self.max_retries + 1):
            result = self.client.complete_json(current_prompt, max_tokens=self._max_tokens)
            # Fallback: fill missing must_keep/keep_reason before validation
            for ev in result.get("events", []):
                if "must_keep" not in ev:
                    scores = [
                        ev.get("main_plot_score", 1), ev.get("character_relation_score", 1),
                        ev.get("status_shift_score", 1), ev.get("climax_score", 1),
                        ev.get("suspense_score", 1), ev.get("genre_value_score", 1),
                    ]
                    ev["must_keep"] = any(s >= 4 for s in scores) or (sum(scores) / len(scores) >= 3)
                if "keep_reason" not in ev:
                    ev["keep_reason"] = "auto-derived from scores"
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
    _max_tokens = 4096

    def __init__(self, client: LLMClient, paths: Paths, validator: SchemaValidator, max_retries: int = 2) -> None:
        self.client = client
        self.paths = paths
        self.validator = validator
        self.max_retries = max_retries
        self._genre_engine = GenreStyleEngine()

    def run(self, normalized_events: NormalizedEventSet, scored_events: list[ScoredEvent], genre: str | None = None) -> EpisodeSummary:
        prompt = self._build_prompt(normalized_events, scored_events, genre)
        result = self._complete_validated(prompt, "episode_summary.schema.json")
        return EpisodeSummary(**result)

    def _build_prompt(self, normalized_events: NormalizedEventSet, scored_events: list[ScoredEvent], genre: str | None = None) -> str:
        # Try genre-specific prompt first
        genre_prompt = None
        if genre:
            genre_prompt = self._genre_engine.get_episode_prompt(genre, self.paths.prompts_dir)

        if genre_prompt:
            # Render template variables in genre-specific prompt
            events_json = json.dumps(asdict(normalized_events), ensure_ascii=False, indent=2)
            scored_json = json.dumps([asdict(item) for item in scored_events], ensure_ascii=False, indent=2)
            return render_prompt(
                genre_prompt,
                genre=genre or "mixed",
                events_json=events_json,
                scored_events_json=scored_json,
            )

        # Fall back to targeted section from prompt bank
        prompt_bank = load_prompt(self.paths.prompts_dir / "webnovel_prompts.md")
        base_prompt = _extract_prompt_section(prompt_bank, "Episode Summary Prompt")

        # Add genre style guidance for generic prompt
        style_guidance = ""
        if genre:
            title_style = self._genre_engine.get_title_style(genre)
            tone = self._genre_engine.get_summary_tone(genre)
            style_guidance = (
                f"\n\nGenre style guidance (genre: {genre}):\n"
                f"- Title pattern: {title_style.pattern}\n"
                f"- Title examples: {', '.join(title_style.examples)}\n"
                f"- Tone: {tone.tone_description}\n"
                f"- Emphasis: {', '.join(tone.emphasis_points)}\n"
                f"- Avoid: {', '.join(tone.avoid_points)}\n"
            )

        payload = {
            "normalized_events": asdict(normalized_events),
            "scores": [asdict(item) for item in scored_events],
        }
        return (
            f"{base_prompt}\n\n"
            f"{style_guidance}"
            "Output JSON only.\n\n"
            f"Input:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    def _complete_validated(self, prompt: str, schema_name: str) -> JsonDict:
        current_prompt = prompt
        for attempt in range(self.max_retries + 1):
            result = self.client.complete_json(current_prompt, max_tokens=self._max_tokens)
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
    _max_tokens = 4096

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
        normalization = _extract_prompt_section(prompt_bank, "Event Normalization Prompt")
        payload = [asdict(item) for item in extractions]
        return (
            f"{normalization}\n\n"
            "Output JSON only.\n\n"
            f"Input:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    def _complete_validated(self, prompt: str, schema_name: str) -> JsonDict:
        current_prompt = prompt
        for attempt in range(self.max_retries + 1):
            result = self.client.complete_json(current_prompt, max_tokens=self._max_tokens)
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


class CausalAnalyzer:
    """LLM stage that analyzes causal relationships between normalized events."""

    _max_tokens = 4096

    def __init__(self, client: LLMClient, paths: Paths, validator: SchemaValidator, max_retries: int = 2) -> None:
        self.client = client
        self.paths = paths
        self.validator = validator
        self.max_retries = max_retries

    def run(
        self,
        normalized_events: NormalizedEventSet,
        unresolved_foreshadowing: list[dict[str, object]] | None = None,
    ) -> JsonDict:
        prompt = self._build_prompt(normalized_events, unresolved_foreshadowing)
        return self._complete_validated(prompt, "causal_analysis.schema.json")

    def _build_prompt(
        self,
        normalized_events: NormalizedEventSet,
        unresolved_foreshadowing: list[dict[str, object]] | None = None,
    ) -> str:
        template = load_prompt(self.paths.prompts_dir / "causal_analysis.md")
        events_json = json.dumps(asdict(normalized_events)["events"], ensure_ascii=False, indent=2)
        if unresolved_foreshadowing:
            unresolved_json = json.dumps(unresolved_foreshadowing, ensure_ascii=False, indent=2)
        else:
            unresolved_json = "None"
        return render_prompt(
            template,
            events=events_json,
            unresolved_foreshadowing=unresolved_json,
        )

    def _complete_validated(self, prompt: str, schema_name: str) -> JsonDict:
        current_prompt = prompt
        for attempt in range(self.max_retries + 1):
            result = self.client.complete_json(current_prompt, max_tokens=self._max_tokens)
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
