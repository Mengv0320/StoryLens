"""Data types for narrative analysis results."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class GroupSummary:
    group_id: str                          # "grp_001"
    chapter_range: str                     # "第1章 ~ 第5章"
    chapter_ids: list[str]                 # ["ch_001", ..., "ch_005"]
    plot_progress: str                     # 本组剧情推进概要（100-200字）
    new_foreshadowing: list[str]           # 本组新埋的伏笔
    resolved_foreshadowing: list[str]      # 本组回收的伏笔
    open_questions: list[str]              # 本组遗留的悬念
    subplot_threads: list[str]             # 活跃的支线
    character_arcs: list[dict]             # [{"name": "角色", "development": "变化描述"}]
    key_causality: list[dict]              # [{"cause": "因", "effect": "果"}]
    tension_level: int                     # 1-5 紧张度


@dataclass
class BookSynthesis:
    title: str                             # 书名/推断书名
    main_plotline: str                     # 主线剧情概要（200-400字）
    subplot_summary: list[dict]            # [{"thread": "支线名", "summary": "概要", "status": "active|resolved"}]
    foreshadowing_tracker: list[dict]      # [{"setup": "伏笔描述", "setup_group": "grp_001", "resolved_group": "grp_003"|null}]
    character_arcs: list[dict]             # [{"name": "角色", "arc_summary": "完整弧线", "key_moments": ["grp_001:事件"]}]
    tension_curve: list[dict]              # [{"group_id": "grp_001", "level": 3, "reason": "原因"}]
    themes: list[str]                      # 核心主题
    open_questions: list[str]              # 全书未解悬念
    quality_notes: list[str]              # 叙事质量备注


@dataclass
class NarrativeResult:
    group_summaries: list[GroupSummary] = field(default_factory=list)
    book_synthesis: BookSynthesis | None = None

    def to_dict(self) -> dict:
        return {
            "group_summaries": [asdict(g) for g in self.group_summaries],
            "book_synthesis": asdict(self.book_synthesis) if self.book_synthesis else None,
        }


def default_book_synthesis() -> BookSynthesis:
    """Return a placeholder BookSynthesis for error fallback."""
    return BookSynthesis(
        title="未知",
        main_plotline="全书综合分析失败",
        subplot_summary=[],
        foreshadowing_tracker=[],
        character_arcs=[],
        tension_curve=[],
        themes=[],
        open_questions=[],
        quality_notes=["全书综合分析未能完成"],
    )


def default_group_summary(
    group_id: str,
    chapter_range: str,
    chapter_ids: list[str],
) -> GroupSummary:
    """Return a placeholder GroupSummary for error fallback."""
    return GroupSummary(
        group_id=group_id,
        chapter_range=chapter_range,
        chapter_ids=chapter_ids,
        plot_progress="分析失败",
        new_foreshadowing=[],
        resolved_foreshadowing=[],
        open_questions=[],
        subplot_threads=[],
        character_arcs=[],
        key_causality=[],
        tension_level=1,
    )
