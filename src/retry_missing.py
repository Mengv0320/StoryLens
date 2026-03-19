"""retry_missing — 补跑 fast_scan 中失败的 segment 或 key_chapter"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, fields
from typing import Any

logger = logging.getLogger(__name__)


def retry_failed_segments(
    artifacts_dir: str,
    client,
    chapters_map: dict,
    cache=None,
) -> dict[str, Any]:
    """补跑失败的 segment 摘要。

    读取 segments.json，找出 status=="failed" 的条目，
    重新调用 summarize_segment 生成摘要，更新 segments.json。

    Returns: {"retried": int, "succeeded": int, "still_failed": int}
    """
    from .segment_summary import summarize_segment
    from .fast_scan_types import Segment, SegmentSummary

    segments_path = os.path.join(artifacts_dir, "segments.json")
    segments_meta_path = os.path.join(artifacts_dir, "segments_meta.json")

    if not os.path.exists(segments_path):
        return {"retried": 0, "succeeded": 0, "still_failed": 0, "error": "segments.json not found"}

    with open(segments_path, "r", encoding="utf-8") as f:
        segments_data = json.load(f)

    # Load segment metadata for rebuilding Segment objects
    seg_meta: dict[str, dict] = {}
    if os.path.exists(segments_meta_path):
        with open(segments_meta_path, "r", encoding="utf-8") as f:
            for item in json.load(f):
                seg_meta[item["segment_id"]] = item

    failed_indices = [i for i, s in enumerate(segments_data) if s.get("status") == "failed"]
    if not failed_indices:
        return {"retried": 0, "succeeded": 0, "still_failed": 0}

    retried = 0
    succeeded = 0

    for idx in failed_indices:
        seg_data = segments_data[idx]
        seg_id = seg_data.get("segment_id", "")
        meta = seg_meta.get(seg_id, {})

        # Rebuild Segment object from metadata or fallback to seg_data
        segment = Segment(
            segment_id=seg_id,
            chapter_ids=meta.get("chapter_ids", seg_data.get("chapter_ids", [])),
            chapter_range_label=meta.get("chapter_range_label", seg_data.get("chapter_range", "")),
            candidate_chapters=meta.get("candidate_chapters", seg_data.get("candidate_chapters", [])),
            estimated_priority=meta.get("estimated_priority", seg_data.get("estimated_priority", "normal")),
        )

        logger.info("Retrying segment %s", seg_id)
        retried += 1

        try:
            result = summarize_segment(client, segment, chapters_map)
            segments_data[idx] = asdict(result)
            if result.status == "completed":
                succeeded += 1
                if cache:
                    seg_payload = {"segment_id": seg_id, "chapter_ids": segment.chapter_ids}
                    cache.set("segment_summary", seg_payload, asdict(result))
        except Exception as e:
            logger.error("Retry failed for segment %s: %s", seg_id, e)
            segments_data[idx]["error"] = str(e)

    # Save updated segments
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump(segments_data, f, ensure_ascii=False, indent=2)

    still_failed = retried - succeeded
    logger.info("Segment retry: %d retried, %d succeeded, %d still failed", retried, succeeded, still_failed)

    return {"retried": retried, "succeeded": succeeded, "still_failed": still_failed}


def retry_failed_key_chapters(
    artifacts_dir: str,
    client,
    chapters_map: dict,
    cache=None,
) -> dict[str, Any]:
    """补跑失败的关键章节精摘要。

    读取 key_chapters.json，找出 status=="failed" 的条目，
    重新调用 summarize_key_chapter 生成摘要，更新 key_chapters.json。

    Returns: {"retried": int, "succeeded": int, "still_failed": int}
    """
    from .key_chapter_summary import summarize_key_chapter

    kc_path = os.path.join(artifacts_dir, "key_chapters.json")

    if not os.path.exists(kc_path):
        return {"retried": 0, "succeeded": 0, "still_failed": 0, "error": "key_chapters.json not found"}

    with open(kc_path, "r", encoding="utf-8") as f:
        kc_data = json.load(f)

    failed_indices = [i for i, k in enumerate(kc_data) if k.get("status") == "failed"]
    if not failed_indices:
        return {"retried": 0, "succeeded": 0, "still_failed": 0}

    retried = 0
    succeeded = 0

    for idx in failed_indices:
        kc = kc_data[idx]
        chapter_id = kc.get("chapter_id", "")
        chapter = chapters_map.get(chapter_id)

        if not chapter:
            logger.warning("Chapter %s not found in chapters_map, skipping", chapter_id)
            continue

        logger.info("Retrying key chapter %s", chapter_id)
        retried += 1

        try:
            result = summarize_key_chapter(client, chapter, chapter_id)
            kc_data[idx] = asdict(result)
            if result.status == "completed":
                succeeded += 1
                if cache:
                    cache.set("key_chapter_summary", {"chapter_id": chapter_id}, asdict(result))
        except Exception as e:
            logger.error("Retry failed for key chapter %s: %s", chapter_id, e)
            kc_data[idx]["error"] = str(e)

    # Save updated key chapters
    with open(kc_path, "w", encoding="utf-8") as f:
        json.dump(kc_data, f, ensure_ascii=False, indent=2)

    still_failed = retried - succeeded
    logger.info("Key chapter retry: %d retried, %d succeeded, %d still failed", retried, succeeded, still_failed)

    return {"retried": retried, "succeeded": succeeded, "still_failed": still_failed}


def regenerate_overview_and_guide(
    artifacts_dir: str,
    client,
    total_chapters: int,
    total_words: int,
    cache=None,
) -> dict[str, Any]:
    """补跑后重新生成全书总览和阅读指南。

    读取最新的 segments.json 和 key_chapters.json，
    重新调用 generate_overview 和 generate_reading_guide。
    """
    from .book_overview import generate_overview, generate_reading_guide
    from .fast_scan_types import SegmentSummary, KeyChapter

    segments_path = os.path.join(artifacts_dir, "segments.json")
    kc_path = os.path.join(artifacts_dir, "key_chapters.json")

    if not os.path.exists(segments_path):
        return {"status": "error", "error": "segments.json not found"}

    with open(segments_path, "r", encoding="utf-8") as f:
        seg_data = json.load(f)

    kc_data = []
    if os.path.exists(kc_path):
        with open(kc_path, "r", encoding="utf-8") as f:
            kc_data = json.load(f)

    # Reconstruct dataclass instances (only pass valid fields)
    def _make(cls, d):
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in valid})

    segment_summaries = [_make(SegmentSummary, s) for s in seg_data]
    key_chapters = [_make(KeyChapter, k) for k in kc_data]

    overview = generate_overview(client, segment_summaries, key_chapters, total_chapters, total_words)
    reading_guide = generate_reading_guide(client, overview, segment_summaries, key_chapters)

    with open(os.path.join(artifacts_dir, "book_overview.json"), "w", encoding="utf-8") as f:
        json.dump(asdict(overview), f, ensure_ascii=False, indent=2)
    with open(os.path.join(artifacts_dir, "reading_guide.json"), "w", encoding="utf-8") as f:
        json.dump(asdict(reading_guide), f, ensure_ascii=False, indent=2)

    if cache:
        overview_payload = {
            "segment_ids": [s.segment_id for s in segment_summaries if s.status == "completed"],
            "key_chapter_ids": [k.chapter_id for k in key_chapters if k.status == "completed"],
            "total_chapters": total_chapters,
        }
        cache.set("book_overview", overview_payload, asdict(overview))
        guide_payload = {
            "overview_title": overview.title,
            "segment_ids": overview_payload["segment_ids"],
            "key_chapter_ids": overview_payload["key_chapter_ids"],
        }
        cache.set("reading_guide", guide_payload, asdict(reading_guide))

    return {"status": "completed"}
