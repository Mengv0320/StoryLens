"""关键章节精摘要"""
from __future__ import annotations

import logging
from typing import List

from .chaptering import Chapter
from .fast_scan_types import KeyChapter

logger = logging.getLogger(__name__)


KEY_CHAPTER_PROMPT = """你是一个小说分析助手。请阅读以下章节，生成精细摘要。

## 章节：{title}

{text}

## 要求
请用 JSON 格式输出：
{{
  "summary": "章节详细摘要（300字以内）",
  "why_it_matters": "为什么这章重要（100字以内）",
  "related_characters": ["相关角色"],
  "related_threads": ["相关剧情线索"]
}}

只输出 JSON。"""


def summarize_key_chapter(
    client,
    chapter: Chapter,
    chapter_id: str,
) -> KeyChapter:
    """为单个关键章节生成精摘要。"""
    try:
        text = chapter.text
        if len(text) > 8000:
            text = text[:4000] + "\n...(省略中间部分)...\n" + text[-3000:]

        prompt = KEY_CHAPTER_PROMPT.format(
            title=chapter.title,
            text=text,
        )

        result = client.complete_json(prompt)

        return KeyChapter(
            chapter_id=chapter_id,
            importance_level="high",
            summary=result.get("summary", ""),
            why_it_matters=result.get("why_it_matters", ""),
            related_characters=result.get("related_characters", []),
            related_threads=result.get("related_threads", []),
            status="completed",
        )
    except Exception as e:
        logger.error("关键章节 %s 摘要失败: %s", chapter_id, e)
        return KeyChapter(
            chapter_id=chapter_id,
            status="failed",
            error=str(e),
        )


def summarize_key_chapters(
    client,
    key_chapter_ids: List[str],
    chapters_map: dict[str, Chapter],
) -> List[KeyChapter]:
    """批量生成关键章节摘要。"""
    results: list[KeyChapter] = []
    for cid in key_chapter_ids:
        ch = chapters_map.get(cid)
        if not ch:
            logger.warning("关键章节 %s 未找到文本，跳过", cid)
            continue
        logger.info("正在精摘要关键章节 %s (%s)", cid, ch.title)
        kc = summarize_key_chapter(client, ch, cid)
        results.append(kc)
    return results
