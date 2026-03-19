"""关键章节选择器：结合规则分数和 segment 结果筛选关键章节"""
from __future__ import annotations

from typing import List, Set

from .fast_scan_types import ChapterIndex, SegmentSummary


def select_key_chapters(
    chapter_index: List[ChapterIndex],
    segment_summaries: List[SegmentSummary],
    max_ratio: float = 0.15,
    min_score: float = 30,
) -> List[str]:
    """选出关键章节 ID 列表。

    来源：
    1. 规则打分的高分候选章节
    2. segment 摘要中 LLM 推荐的 must_read 章节

    最终按 max_ratio 限制总数，按分数排序保留 top-N。
    """
    key_ids: Set[str] = set()

    # 1. 规则分数筛选
    for ch in chapter_index:
        if ch.importance_score >= min_score and ch.is_candidate:
            key_ids.add(ch.chapter_id)

    # 2. segment 摘要的 must_read 补充
    for ss in segment_summaries:
        if ss.status == "completed":
            for cid in ss.must_read_chapters:
                key_ids.add(cid)

    # 3. 限制总数
    max_count = max(int(len(chapter_index) * max_ratio), 5)
    if len(key_ids) > max_count:
        score_map = {ch.chapter_id: ch.importance_score for ch in chapter_index}
        scored = [(cid, score_map.get(cid, 0)) for cid in key_ids]
        scored.sort(key=lambda x: x[1], reverse=True)
        key_ids = set(cid for cid, _ in scored[:max_count])

    return sorted(key_ids)
