"""fast_scan 快速扫书主流程"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _cached_call(cache, stage: str, payload: dict, producer):
    """Cache wrapper. Returns (result_dict, hit: bool).

    Only caches successful results (status != 'failed').
    """
    if cache:
        cached = cache.get(stage, payload)
        if cached is not None:
            # Skip cached failures — force re-run
            if isinstance(cached, dict) and cached.get("status") == "failed":
                pass
            else:
                return cached, True
    result = producer()
    if cache and not (isinstance(result, dict) and result.get("status") == "failed"):
        cache.set(stage, payload, result)
    return result, False


def run_fast_scan(
    text: str,
    output_dir: str,
    client,  # LLM client with complete_json / _create_completion
    project_name: str = "",
    cache=None,  # StageCache or None
    run_logger=None,  # RunLogger or None
) -> dict[str, Any]:
    """
    快速扫书主流程

    流程：
    1. 切章
    2. 规则预处理（不调用模型）
    3. 保底覆盖
    4. Segment 切分
    5. Segment 粗摘要（调用模型）
    6. 关键章节筛选
    7. 关键章节精摘要（调用模型）
    8. 全书总览（调用模型）
    9. 阅读指南（调用模型）
    10. 保存结果

    Returns: dict with status and result paths
    """
    from .chaptering import split_into_chapters
    from .fast_scan_rules import build_chapter_index
    from .fast_scan_indexer import ensure_coverage, get_chapter_stats
    from .segmenter import split_into_segments
    from .segment_summary import summarize_segment
    from .key_chapter_selector import select_key_chapters
    from .key_chapter_summary import summarize_key_chapter
    from .book_overview import generate_overview, generate_reading_guide
    from .fast_scan_types import SegmentSummary, KeyChapter, BookOverview, ReadingGuide

    os.makedirs(output_dir, exist_ok=True)
    artifacts_dir = os.path.join(output_dir, "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)

    start_time = time.time()
    cache_hits = 0

    def _log(msg: str) -> None:
        logger.info(msg)
        if run_logger:
            run_logger.log("fast_scan", msg=msg)

    # === Step 1: 切章 ===
    _log("Step 1/9: 切章...")
    chapters = split_into_chapters(text)
    chapters_map = {ch.chapter_id: ch for ch in chapters}
    _log(f"  共 {len(chapters)} 章")

    # === Step 2: 规则预处理 ===
    _log("Step 2/9: 规则预处理...")
    chapter_index = build_chapter_index(chapters)

    # === Step 3: 保底覆盖 ===
    _log("Step 3/9: 保底覆盖检查...")
    chapter_index = ensure_coverage(chapter_index)
    stats = get_chapter_stats(chapter_index)
    _log(
        f"  候选章节: {stats['candidate_chapters']}/{stats['total_chapters']}"
        f" ({stats['candidate_ratio']:.1%})"
    )

    # 保存章节索引
    _save_json(artifacts_dir, "chapter_index.json", [_to_dict(ci) for ci in chapter_index])

    # === Step 4: Segment 切分 ===
    _log("Step 4/9: Segment 切分...")
    segments = split_into_segments(chapter_index)
    _log(f"  共 {len(segments)} 个 segment")

    _save_json(artifacts_dir, "segments_meta.json", [_to_dict(s) for s in segments])

    # === Step 5: Segment 粗摘要（per-segment caching） ===
    _log("Step 5/9: Segment 粗摘要（调用模型）...")
    segment_summaries: list[SegmentSummary] = []
    for seg in segments:
        payload = {"segment_id": seg.segment_id, "chapter_ids": seg.chapter_ids}
        result, hit = _cached_call(
            cache, "segment_summary", payload,
            lambda s=seg: _to_dict(summarize_segment(client, s, chapters_map)),
        )
        if hit:
            cache_hits += 1
            segment_summaries.append(SegmentSummary(**result))
            logger.info("  segment %s 缓存命中", seg.segment_id)
        else:
            segment_summaries.append(SegmentSummary(**result))
    completed = sum(1 for s in segment_summaries if s.status == "completed")
    failed = sum(1 for s in segment_summaries if s.status == "failed")
    _log(f"  完成: {completed}, 失败: {failed}")

    _save_json(artifacts_dir, "segments.json", [_to_dict(s) for s in segment_summaries])

    # === Step 6: 关键章节筛选 ===
    _log("Step 6/9: 关键章节筛选...")
    key_chapter_ids = select_key_chapters(chapter_index, segment_summaries)
    _log(f"  筛出 {len(key_chapter_ids)} 个关键章节")

    # === Step 7: 关键章节精摘要（per-chapter caching） ===
    _log("Step 7/9: 关键章节精摘要（调用模型）...")
    key_chapters: list[KeyChapter] = []
    for cid in key_chapter_ids:
        ch = chapters_map.get(cid)
        if not ch:
            logger.warning("关键章节 %s 未找到文本，跳过", cid)
            continue
        payload = {"chapter_id": cid}
        result, hit = _cached_call(
            cache, "key_chapter_summary", payload,
            lambda c=ch, i=cid: _to_dict(summarize_key_chapter(client, c, i)),
        )
        if hit:
            cache_hits += 1
            key_chapters.append(KeyChapter(**result))
            logger.info("  关键章节 %s 缓存命中", cid)
        else:
            key_chapters.append(KeyChapter(**result))
    kc_completed = sum(1 for k in key_chapters if k.status == "completed")
    kc_failed = sum(1 for k in key_chapters if k.status == "failed")
    _log(f"  完成: {kc_completed}, 失败: {kc_failed}")

    _save_json(artifacts_dir, "key_chapters.json", [_to_dict(k) for k in key_chapters])

    # === Step 8: 全书总览（single-call caching） ===
    _log("Step 8/9: 全书总览（调用模型）...")
    overview_payload = {
        "segment_ids": [s.segment_id for s in segment_summaries if s.status == "completed"],
        "key_chapter_ids": [k.chapter_id for k in key_chapters if k.status == "completed"],
        "total_chapters": len(chapters),
    }
    overview_result, overview_hit = _cached_call(
        cache, "book_overview", overview_payload,
        lambda: _to_dict(generate_overview(
            client, segment_summaries, key_chapters,
            total_chapters=len(chapters),
            total_words=sum(ch.word_count for ch in chapter_index),
        )),
    )
    if overview_hit:
        cache_hits += 1
        _log("  全书总览缓存命中")
    overview = BookOverview(**overview_result)
    _save_json(artifacts_dir, "book_overview.json", _to_dict(overview))

    # === Step 9: 阅读指南（single-call caching） ===
    _log("Step 9/9: 阅读指南（调用模型）...")
    guide_payload = {
        "overview_title": overview.title,
        "segment_ids": overview_payload["segment_ids"],
        "key_chapter_ids": overview_payload["key_chapter_ids"],
    }
    guide_result, guide_hit = _cached_call(
        cache, "reading_guide", guide_payload,
        lambda: _to_dict(generate_reading_guide(client, overview, segment_summaries, key_chapters)),
    )
    if guide_hit:
        cache_hits += 1
        _log("  阅读指南缓存命中")
    reading_guide = ReadingGuide(**guide_result)
    _save_json(artifacts_dir, "reading_guide.json", _to_dict(reading_guide))

    # === 汇总 ===
    elapsed = time.time() - start_time
    model_calls = (completed + kc_completed
                   + (1 if overview.completeness > 0 else 0) + 1
                   - cache_hits)
    run_stats: dict[str, Any] = {
        "total_chapters": len(chapters),
        "total_segments": len(segments),
        "segments_completed": completed,
        "segments_failed": failed,
        "key_chapters_count": len(key_chapter_ids),
        "key_chapters_completed": kc_completed,
        "key_chapters_failed": kc_failed,
        "cache_hits": cache_hits,
        "elapsed_seconds": round(elapsed, 1),
        "model_calls": max(model_calls, 0),
    }
    _save_json(artifacts_dir, "run_stats.json", run_stats)

    _log(f"快速扫书完成！耗时 {elapsed:.1f}s，模型调用 {run_stats['model_calls']} 次，缓存命中 {cache_hits} 次")

    return {
        "status": "completed",
        "output_dir": output_dir,
        "artifacts_dir": artifacts_dir,
        "stats": run_stats,
    }


def _to_dict(obj: Any) -> dict[str, Any]:
    """dataclass to dict, with fallback."""
    try:
        return asdict(obj)
    except Exception:
        return obj if isinstance(obj, dict) else {"value": str(obj)}


def _save_json(directory: str, filename: str, data: Any) -> None:
    """保存 JSON 文件"""
    path = os.path.join(directory, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.debug(f"Saved {path}")
