"""Segment 切分器：将章节分组为适合摘要的段"""
from __future__ import annotations

from .fast_scan_types import ChapterIndex, Segment

DEFAULT_SEGMENT_SIZE = 30  # 默认每段30章
MIN_SEGMENT_SIZE = 10
MAX_SEGMENT_SIZE = 50


def split_into_segments(
    chapter_index: list[ChapterIndex],
    target_size: int = DEFAULT_SEGMENT_SIZE,
) -> list[Segment]:
    """将章节索引切分为 segment"""
    if not chapter_index:
        return []

    segments: list[Segment] = []
    total = len(chapter_index)

    seg_id = 0
    i = 0
    while i < total:
        end = min(i + target_size, total)

        # 边界微调：如果切点附近有高分章节，尝试包含进来
        if end < total and end - i >= MIN_SEGMENT_SIZE:
            look_ahead = min(end + 5, total)
            for j in range(end, look_ahead):
                if chapter_index[j].importance_score >= 40:
                    end = j + 1
                    break

        # 不超过最大限制
        end = min(end, i + MAX_SEGMENT_SIZE, total)

        chunk = chapter_index[i:end]
        seg_id += 1

        chapter_ids = [ch.chapter_id for ch in chunk]
        candidates = [ch.chapter_id for ch in chunk if ch.is_candidate]

        # 优先级估算
        avg_score = sum(ch.importance_score for ch in chunk) / len(chunk)
        if avg_score >= 35:
            priority = "high"
        elif avg_score >= 15:
            priority = "normal"
        else:
            priority = "low"

        first_title = chunk[0].title
        last_title = chunk[-1].title
        range_label = f"{first_title} ~ {last_title}"

        segments.append(Segment(
            segment_id=f"seg_{seg_id:03d}",
            chapter_ids=chapter_ids,
            chapter_range_label=range_label,
            candidate_chapters=candidates,
            estimated_priority=priority,
        ))

        i = end

    return segments
