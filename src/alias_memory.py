from __future__ import annotations

from dataclasses import dataclass, field

from .models import NormalizedEventSet


GENERIC_NAME_TOKENS = (
    "众人",
    "弟子",
    "长老",
    "执事",
    "护卫",
    "少女",
    "少年",
    "男人",
    "女人",
    "老者",
    "路人",
    "族人",
    "师兄",
    "师姐",
    "同门",
)

TITLE_PREFIXES = (
    "小",
    "老",
    "大",
    "阿",
)

TITLE_SUFFIXES = (
    "师兄",
    "师姐",
    "长老",
    "执事",
    "师父",
    "师尊",
    "前辈",
    "公子",
    "小姐",
    "姑娘",
    "殿下",
    "陛下",
    "真人",
)


@dataclass
class CharacterAliasMemory:
    canonical_to_aliases: dict[str, set[str]] = field(default_factory=dict)

    def apply(self, normalized_events: NormalizedEventSet) -> NormalizedEventSet:
        for event in normalized_events.events:
            canonical_characters: list[str] = []
            seen: set[str] = set()
            for name in event.characters:
                canonical = self.resolve_or_register(name)
                if canonical not in seen:
                    seen.add(canonical)
                    canonical_characters.append(canonical)
            event.characters = canonical_characters
        return normalized_events

    def resolve_or_register(self, raw_name: str) -> str:
        name = self._clean_name(raw_name)
        if not name or self._is_generic(name):
            return raw_name

        existing = self._find_existing(name)
        if existing:
            self.canonical_to_aliases.setdefault(existing, set()).add(raw_name)
            self.canonical_to_aliases[existing].add(name)
            return existing

        canonical = name
        self.canonical_to_aliases.setdefault(canonical, set()).update({raw_name, name})
        return canonical

    def snapshot(self) -> dict[str, list[str]]:
        return {
            canonical: sorted(alias for alias in aliases if alias != canonical)
            for canonical, aliases in sorted(self.canonical_to_aliases.items())
        }

    def _find_existing(self, name: str) -> str | None:
        for canonical, aliases in self.canonical_to_aliases.items():
            candidates = {canonical, *aliases}
            if name in candidates:
                return canonical
            if self._is_alias_like(name, canonical):
                return canonical
            if any(self._is_alias_like(name, alias) for alias in aliases):
                return canonical
        return None

    def _clean_name(self, name: str) -> str:
        cleaned = name.strip()
        for suffix in TITLE_SUFFIXES:
            if cleaned.endswith(suffix) and len(cleaned) > len(suffix) + 1:
                cleaned = cleaned[: -len(suffix)]
                break
        for prefix in TITLE_PREFIXES:
            if cleaned.startswith(prefix) and len(cleaned) > 2:
                cleaned = cleaned[1:]
                break
        return cleaned.strip()

    def _is_alias_like(self, left: str, right: str) -> bool:
        if left == right:
            return True
        short, long = sorted((left, right), key=len)
        if len(short) < 2:
            return False
        if short in long and len(long) - len(short) <= 3 and not self._is_generic(short):
            return True
        return False

    def _is_generic(self, name: str) -> bool:
        return any(token in name for token in GENERIC_NAME_TOKENS)
