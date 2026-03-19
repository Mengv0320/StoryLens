"""Segment 粗摘要：用 LLM 为每个 segment 生成摘要"""
from __future__ import annotations

import logging
from typing import List

from .chaptering import Chapter
from .fast_scan_types import Segment, SegmentSummary

logger = logging.getLogger(__name__)


SEGMENT_SUMMARY_PROMPT = """你是一个小说分析助手。请阅读以下小说片段（包含多个章节），生成结构化摘要。

## 章节范围
{chapter_range}

## 文本内容
{text}

## 要求
请用 JSON 格式输出以下内容：
{{
  "summary": "这一段的整体摘要（200字以内）",
  "main_plot": "这一段的主线发展（100字以内）",
  "key_characters": ["出场的重要角色名"],
  "must_read_chapters": ["必看章节ID列表，如 chapter_001"],
  "skippable_ranges": ["可跳过的章节范围描述"],
  "open_threads": ["未解决的悬念或伏笔"]
}}

只输出 JSON，不要其他内容。"""


def _build_segment_text(
    segment_chapter_ids: List[str],
    candidate_ids: List[str],
    chapters_map: dict[str, Chapter],
    max_total_chars: int = 15000,
) -> str:
    """构建 segment 输入文本，控制长度。

    候选章节保留全文，非候选章节只取首尾各200字。
    """
    parts: list[str] = []
    total = 0

    for cid in segment_chapter_ids:
        ch = chapters_map.get(cid)
        if not ch:
            continue

        if cid in candidate_ids:
            text = ch.text
        else:
            t = ch.text
            if len(t) > 500:
                text = t[:200] + "\n...(省略)...\n" + t[-200:]
            else:
                text = t

        header = f"\n### {ch.title}\n"
        chunk = header + text

        if total + len(chunk) > max_total_chars:
            remaining = max_total_chars - total
            if remaining > 200:
                parts.append(chunk[:remaining] + "\n...(截断)...")
            break

        parts.append(chunk)
        total += len(chunk)

    return "\n".join(parts)


def summarize_segment(
    client,
    segment: Segment,
    chapters_map: dict[str, Chapter],
) -> SegmentSummary:
    """为单个 segment 生成摘要。失败时返回 status='failed'。"""
    try:
        text = _build_segment_text(
            segment.chapter_ids,
            segment.candidate_chapters,
            chapters_map,
        )

        prompt = SEGMENT_SUMMARY_PROMPT.format(
            chapter_range=segment.chapter_range_label,
            text=text,
        )

        result = client.complete_json(prompt)

        return SegmentSummary(
            segment_id=segment.segment_id,
            chapter_range=segment.chapter_range_label,
            summary=result.get("summary", ""),
            main_plot=result.get("main_plot", ""),
            key_characters=result.get("key_characters", []),
            must_read_chapters=result.get("must_read_chapters", []),
            skippable_ranges=result.get("skippable_ranges", []),
            open_threads=result.get("open_threads", []),
            status="completed",
        )
    except Exception as e:
        logger.error("Segment %s 摘要失败: %s", segment.segment_id, e)
        return SegmentSummary(
            segment_id=segment.segment_id,
            chapter_range=segment.chapter_range_label,
            status="failed",
            error=str(e),
        )


def summarize_all_segments(
    client,
    segments: List[Segment],
    chapters_map: dict[str, Chapter],
) -> List[SegmentSummary]:
    """批量生成 segment 摘要，逐个执行，失败不中断。"""
    results: list[SegmentSummary] = []
    for seg in segments:
        logger.info("正在摘要 segment %s (%s)", seg.segment_id, seg.chapter_range_label)
        summary = summarize_segment(client, seg, chapters_map)
        results.append(summary)
        if summary.status == "completed":
            logger.info("  segment %s 完成", seg.segment_id)
        else:
            logger.warning("  segment %s 失败: %s", seg.segment_id, summary.error)
    return results
