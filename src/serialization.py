"""Shared serialization utilities: case conversion, JSON repair."""

from __future__ import annotations

import json
import re
from typing import Any


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


