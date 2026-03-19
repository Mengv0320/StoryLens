from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChapterIndex:
    """章节粗索引"""
    chapter_id: str
    title: str
    word_count: int
    feature_tags: list[str] = field(default_factory=list)
    importance_score: float = 0.0
    candidate_reason: str = ""
    is_candidate: bool = False


@dataclass
class Segment:
    """段落划分"""
    segment_id: str
    chapter_ids: list[str] = field(default_factory=list)
    chapter_range_label: str = ""
    candidate_chapters: list[str] = field(default_factory=list)
    estimated_priority: str = "normal"  # low/normal/high


@dataclass
class SegmentSummary:
    """段落摘要"""
    segment_id: str
    chapter_range: str = ""
    summary: str = ""
    main_plot: str = ""
    key_characters: list[str] = field(default_factory=list)
    must_read_chapters: list[str] = field(default_factory=list)
    skippable_ranges: list[str] = field(default_factory=list)
    open_threads: list[str] = field(default_factory=list)
    status: str = "pending"  # pending/completed/failed
    error: str = ""


@dataclass
class KeyChapter:
    """关键章节"""
    chapter_id: str
    importance_level: str = "high"  # critical/high/medium
    summary: str = ""
    why_it_matters: str = ""
    related_characters: list[str] = field(default_factory=list)
    related_threads: list[str] = field(default_factory=list)
    status: str = "pending"
    error: str = ""


@dataclass
class BookOverview:
    """全书总览"""
    title: str = ""
    total_chapters: int = 0
    total_words: int = 0
    main_plotline: str = ""
    key_stages: list[str] = field(default_factory=list)
    core_characters: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    completeness: float = 1.0  # 0-1, 标记结果完整度


@dataclass
class ReadingGuide:
    """阅读指南"""
    must_read_chapters: list[str] = field(default_factory=list)
    skippable_ranges: list[str] = field(default_factory=list)
    reading_order_suggestion: str = ""
    estimated_essential_ratio: float = 0.0  # 必读章节占比
    summary_by_stage: list[dict] = field(default_factory=list)


@dataclass
class FastScanResult:
    """fast_scan 完整结果"""
    chapter_index: list[ChapterIndex] = field(default_factory=list)
    segments: list[Segment] = field(default_factory=list)
    segment_summaries: list[SegmentSummary] = field(default_factory=list)
    key_chapters: list[KeyChapter] = field(default_factory=list)
    overview: BookOverview | None = None
    reading_guide: ReadingGuide | None = None
    run_stats: dict = field(default_factory=dict)
