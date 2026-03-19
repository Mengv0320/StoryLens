"""章节索引器：汇总规则预处理结果"""
from __future__ import annotations

from .fast_scan_types import ChapterIndex


def get_candidate_chapters(index: list[ChapterIndex]) -> list[ChapterIndex]:
    """获取候选重点章节"""
    return [ch for ch in index if ch.is_candidate]


def get_chapter_stats(index: list[ChapterIndex]) -> dict:
    """章节统计"""
    total = len(index)
    candidates = sum(1 for ch in index if ch.is_candidate)
    total_words = sum(ch.word_count for ch in index)
    avg_score = sum(ch.importance_score for ch in index) / max(total, 1)

    tag_dist: dict[str, int] = {}
    for ch in index:
        for tag in ch.feature_tags:
            tag_dist[tag] = tag_dist.get(tag, 0) + 1

    return {
        "total_chapters": total,
        "candidate_chapters": candidates,
        "candidate_ratio": round(candidates / max(total, 1), 3),
        "total_words": total_words,
        "avg_importance_score": round(avg_score, 2),
        "tag_distribution": tag_dist,
    }


def ensure_coverage(
    index: list[ChapterIndex],
    min_per_window: int = 2,
    window_size: int = 30,
) -> list[ChapterIndex]:
    """保底覆盖：每 window_size 章至少选 min_per_window 章"""
    selected_ids = {ch.chapter_id for ch in index if ch.is_candidate}

    for start in range(0, len(index), window_size):
        window = index[start:start + window_size]
        window_selected = [ch for ch in window if ch.chapter_id in selected_ids]

        if len(window_selected) < min_per_window:
            remaining = sorted(
                [ch for ch in window if ch.chapter_id not in selected_ids],
                key=lambda c: c.importance_score,
                reverse=True,
            )
            need = min_per_window - len(window_selected)
            for ch in remaining[:need]:
                selected_ids.add(ch.chapter_id)
                ch.is_candidate = True
                ch.candidate_reason = (ch.candidate_reason + "\uff1b保底抽样").lstrip("\uff1b")

    return index
