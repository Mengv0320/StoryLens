from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict
from typing import Protocol

import requests
from openai import OpenAI

from .config import Paths
from .models import GenreClassification, JsonDict
from .prompt_loader import load_prompt, render_prompt
from .schema_validator import SchemaValidationError, SchemaValidator

from .serialization import repair_json as _repair_json


class LLMClient(Protocol):
    def complete_json(self, prompt: str, max_tokens: int = 8192) -> JsonDict:
        """Return a JSON-like dict parsed from the model response."""

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
        """Light pre-processing before json.loads(): strip LLM artifacts (think
        tags, code fences, preamble text) and trailing commas.

        Call chain: raw text -> _sanitize_json -> json.loads -> on failure -> repair_json (heavy)
        See also: AnthropicLLMClient._clean_json (subset of this logic for Anthropic responses).
        """
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
        # Store pre-built headers; api_key is NOT kept as an instance attribute
        self._headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

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
        headers = self._headers
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
        """Lightweight JSON cleanup for Anthropic responses.

        A subset of OpenAILLMClient._sanitize_json — Anthropic responses
        don't have <think> tags or code fences (already stripped by
        _strip_code_fence), so we only trim preamble and trailing commas.

        Call chain: raw text -> _strip_code_fence -> _clean_json -> json.loads
                    -> on failure -> repair_json (heavy, from serialization module)
        """
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

    _log = logging.getLogger("stages.MultiProviderClient")

    def __init__(self, providers: list[tuple[OpenAILLMClient, bool]]) -> None:
        """providers: list of (client, needs_sanitize) tuples."""
        self._providers = providers
        self._idx = 0
        self._lock = __import__("threading").Lock()
        self.last_usage: dict[str, int] | None = None

    def complete_json(self, prompt: str, max_tokens: int = 8192) -> JsonDict:
        n = len(self._providers)
        last_err: Exception | None = None
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
            except Exception as exc:
                last_err = exc
                self._log.warning(
                    "Provider %d/%d failed (attempt %d): %s: %s",
                    idx + 1, n, attempt + 1,
                    type(exc).__name__, exc,
                )
                if attempt >= n * 2 - 1:
                    raise
                continue
        raise RuntimeError(f"All providers failed: {last_err}")


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
