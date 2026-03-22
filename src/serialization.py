"""Shared serialization utilities: case conversion, JSON repair."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def snake_to_camel(key: str) -> str:
    """Convert snake_case key to camelCase."""
    parts = key.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def camelize(obj: Any) -> Any:
    """Recursively convert all dict keys from snake_case to camelCase."""
    if isinstance(obj, dict):
        return {snake_to_camel(k): camelize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [camelize(item) for item in obj]
    return obj


def repair_json(text: str) -> str:
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
    max_attempts = 20
    prev_text = None
    stale_count = 0
    for attempt in range(max_attempts):
        try:
            json.loads(text)
            logger.debug("repair_json: succeeded after %d attempt(s)", attempt)
            return text
        except json.JSONDecodeError as e:
            pos = e.pos
            if pos is None or pos < 0:
                logger.debug("repair_json: giving up at attempt %d — no error position", attempt)
                break
            msg = e.msg

            # Early exit: if text hasn't changed for 2 consecutive rounds, stop
            if text == prev_text:
                stale_count += 1
                if stale_count >= 2:
                    logger.debug("repair_json: no progress for %d rounds, stopping at attempt %d", stale_count, attempt)
                    break
            else:
                stale_count = 0
            prev_text = text

            if "Unterminated string" in msg:
                # Close the unterminated string at the nearest logical boundary
                newline_pos = text.find('\n', pos)
                if newline_pos != -1:
                    text = text[:newline_pos] + '"' + text[newline_pos:]
                else:
                    text = text + '"'
                text = _balance_brackets(text)
                continue
            if "Invalid control character" in msg:
                ch = text[pos]
                escape_map = {'\n': '\\n', '\r': '\\r', '\t': '\\t'}
                replacement = escape_map.get(ch, f'\\u{ord(ch):04x}')
                text = text[:pos] + replacement + text[pos + 1:]
                continue
            if "Expecting ',' delimiter" in msg:
                # Insert missing comma before the current token
                text = text[:pos] + ',' + text[pos:]
                continue
            if "Expecting ':' separator" in msg:
                text = text[:pos] + ':' + text[pos:]
                continue
            if "Expecting value" in msg:
                # Possibly a trailing comma — remove it
                before = text[:pos].rstrip()
                if before.endswith(','):
                    text = before[:-1] + text[pos:]
                    continue
                break
            if "Extra data" in msg:
                # Truncate everything after the first valid JSON object
                text = text[:pos]
                break
            logger.debug("repair_json: unhandled error '%s' at pos %d, stopping at attempt %d", msg, pos, attempt)
            break

    logger.debug("repair_json: finished after %d attempt(s) (may not be valid JSON)", max_attempts)
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


