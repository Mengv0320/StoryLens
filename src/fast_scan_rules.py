"""规则预处理：不调用模型，纯规则分析章节"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .fast_scan_types import ChapterIndex

if TYPE_CHECKING:
    from .chaptering import Chapter

# 特征关键词库（中文网文常见）
FEATURE_KEYWORDS: dict[str, list[str]] = {
    "battle": ["战斗", "厮杀", "出手", "对决", "交手", "大战", "激战", "斩杀", "击杀", "血战", "围攻", "偷袭"],
    "breakthrough": ["突破", "进阶", "晋级", "渡劫", "化形", "筑基", "结丹", "元婴", "化神", "飞升", "觉醒", "蜕变"],
    "reveal": ["身份", "真相", "揭露", "暴露", "原来是", "竟然是", "没想到", "秘密", "隐藏", "伪装"],
    "faction": ["势力", "门派", "宗门", "家族", "帝国", "王朝", "联盟", "组织", "阵营"],
    "romance": ["喜欢", "爱情", "表白", "亲吻", "拥抱", "心动", "倾心", "相思", "情愫"],
    "map_change": ["前往", "离开", "抵达", "进入", "来到", "踏入", "返回", "出发", "启程"],
    "treasure": ["宝物", "神器", "灵药", "秘籍", "传承", "机缘", "宝藏", "圣物"],
    "death": ["死亡", "陨落", "身亡", "殒命", "牺牲", "丧命", "殉道"],
    "plot_twist": ["突然", "意外", "震惊", "不可思议", "逆转", "反转", "背叛", "阴谋"],
}

# 标题特征加分词
_TITLE_BOOST_WORDS = ["大战", "突破", "真相", "决战", "最终", "觉醒", "陨落", "背叛", "秘密"]

# 标签价值分级
_HIGH_VALUE_TAGS = {"battle", "breakthrough", "reveal", "death", "plot_twist"}
_MID_VALUE_TAGS = {"faction", "romance", "treasure"}


def analyze_chapter(chapter: Chapter) -> ChapterIndex:
    """分析单章，返回粗索引"""
    text = chapter.text
    title = chapter.title
    word_count = len(text)

    # 特征标签
    feature_tags: list[str] = []
    tag_scores: dict[str, int] = {}
    for tag, keywords in FEATURE_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits > 0:
            feature_tags.append(tag)
            tag_scores[tag] = hits

    # 重要度评分 (0-100)
    score = 0.0

    # 标题特征加分
    for w in _TITLE_BOOST_WORDS:
        if w in title:
            score += 15

    # 关键词密度加分
    for tag, hits in tag_scores.items():
        if tag in _HIGH_VALUE_TAGS:
            score += min(hits * 5, 20)
        elif tag in _MID_VALUE_TAGS:
            score += min(hits * 3, 12)
        else:
            score += min(hits * 2, 8)

    # 字数异常加分
    if word_count > 5000:
        score += 5
    if word_count < 500:
        score += 3  # 短章可能是过渡/公告

    # 对话密度
    quote_count = (
        text.count("\u201c") + text.count("\u201d")
        + text.count('"')
        + text.count("\u300c") + text.count("\u300d")
    )
    if quote_count > 20:
        score += 5

    score = min(score, 100)

    # 候选判定
    is_candidate = score >= 25

    # 候选原因
    _tag_reason_map = {
        "battle": "战斗场景",
        "breakthrough": "突破/进阶",
        "reveal": "身份/真相揭露",
        "death": "角色死亡",
        "plot_twist": "剧情反转",
        "romance": "感情推进",
        "treasure": "重要获取",
    }
    reasons = [_tag_reason_map[t] for t in feature_tags if t in _tag_reason_map]

    return ChapterIndex(
        chapter_id=chapter.chapter_id,
        title=title,
        word_count=word_count,
        feature_tags=feature_tags,
        importance_score=score,
        candidate_reason="\uff1b".join(reasons) if reasons else "普通章节",
        is_candidate=is_candidate,
    )


def build_chapter_index(chapters: list[Chapter]) -> list[ChapterIndex]:
    """批量生成章节粗索引"""
    return [analyze_chapter(ch) for ch in chapters]
