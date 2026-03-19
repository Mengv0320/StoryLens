"""全书总览 + 阅读指南生成"""
from __future__ import annotations

import logging
from typing import List

from .fast_scan_types import (
    BookOverview,
    KeyChapter,
    ReadingGuide,
    SegmentSummary,
)

logger = logging.getLogger(__name__)


# ── 全书总览 ──────────────────────────────────────────────

OVERVIEW_PROMPT = """你是一个小说分析助手。根据以下分段摘要，生成全书总览。

## 分段摘要
{segment_summaries_text}

## 关键章节
{key_chapters_text}

## 要求
请用 JSON 格式输出：
{{
  "title": "推测的书名或主题",
  "main_plotline": "全书主线概述（500字以内）",
  "key_stages": ["主要阶段划分，如'初入江湖'、'势力崛起'等"],
  "core_characters": ["核心角色列表"],
  "open_questions": ["未解决的悬念"]
}}

只输出 JSON。"""


def generate_overview(
    client,
    segment_summaries: List[SegmentSummary],
    key_chapters: List[KeyChapter],
    total_chapters: int,
    total_words: int,
) -> BookOverview:
    """根据 segment 摘要和关键章节生成全书总览。"""
    try:
        seg_parts = []
        for ss in segment_summaries:
            if ss.status == "completed":
                seg_parts.append(f"[{ss.chapter_range}] {ss.summary}")
        seg_text = "\n".join(seg_parts)

        kc_parts = []
        for kc in key_chapters:
            if kc.status == "completed":
                kc_parts.append(f"[{kc.chapter_id}] {kc.summary[:100]}")
        kc_text = "\n".join(kc_parts)

        prompt = OVERVIEW_PROMPT.format(
            segment_summaries_text=seg_text[:6000],
            key_chapters_text=kc_text[:3000],
        )

        result = client.complete_json(prompt)

        completed_segs = sum(1 for s in segment_summaries if s.status == "completed")
        completeness = completed_segs / max(len(segment_summaries), 1)

        return BookOverview(
            title=result.get("title", ""),
            total_chapters=total_chapters,
            total_words=total_words,
            main_plotline=result.get("main_plotline", ""),
            key_stages=result.get("key_stages", []),
            core_characters=result.get("core_characters", []),
            open_questions=result.get("open_questions", []),
            completeness=round(completeness, 2),
        )
    except Exception as e:
        logger.error("全书总览生成失败: %s", e)
        return BookOverview(
            total_chapters=total_chapters,
            total_words=total_words,
            completeness=0.0,
        )


# ── 阅读指南 ──────────────────────────────────────────────

READING_GUIDE_PROMPT = """你是一个小说阅读顾问。根据以下分析结果，生成阅读指南。

## 全书概览
{overview_text}

## 分段摘要
{segment_summaries_text}

## 关键章节
{key_chapters_text}

## 要求
请用 JSON 格式输出：
{{
  "must_read_chapters": ["必读章节ID列表"],
  "skippable_ranges": ["可跳过的章节范围，如'chapter_050~chapter_070'"],
  "reading_order_suggestion": "阅读建议（200字以内）",
  "estimated_essential_ratio": 0.3,
  "summary_by_stage": [
    {{"stage": "阶段名", "chapters": "章节范围", "summary": "阶段摘要"}}
  ]
}}

只输出 JSON。"""


def generate_reading_guide(
    client,
    overview: BookOverview,
    segment_summaries: List[SegmentSummary],
    key_chapters: List[KeyChapter],
) -> ReadingGuide:
    """根据总览和摘要生成阅读指南。"""
    try:
        overview_text = (
            f"主线：{overview.main_plotline}\n"
            f"核心角色：{', '.join(overview.core_characters)}"
        )

        seg_parts: list[str] = []
        for ss in segment_summaries:
            if ss.status == "completed":
                seg_parts.append(f"[{ss.chapter_range}] {ss.main_plot}")
                if ss.must_read_chapters:
                    seg_parts.append(f"  必看: {', '.join(ss.must_read_chapters)}")
                if ss.skippable_ranges:
                    seg_parts.append(f"  可跳: {', '.join(ss.skippable_ranges)}")

        kc_parts: list[str] = []
        for kc in key_chapters:
            if kc.status == "completed":
                kc_parts.append(f"[{kc.chapter_id}] {kc.why_it_matters}")

        prompt = READING_GUIDE_PROMPT.format(
            overview_text=overview_text[:2000],
            segment_summaries_text="\n".join(seg_parts)[:4000],
            key_chapters_text="\n".join(kc_parts)[:2000],
        )

        result = client.complete_json(prompt)

        return ReadingGuide(
            must_read_chapters=result.get("must_read_chapters", []),
            skippable_ranges=result.get("skippable_ranges", []),
            reading_order_suggestion=result.get("reading_order_suggestion", ""),
            estimated_essential_ratio=result.get("estimated_essential_ratio", 0.0),
            summary_by_stage=result.get("summary_by_stage", []),
        )
    except Exception as e:
        logger.error("阅读指南生成失败: %s", e)
        return ReadingGuide()
