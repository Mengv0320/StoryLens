from __future__ import annotations

from pathlib import Path

from .models import RetentionPriority, SummaryTone, TitleStyle
from .prompt_loader import load_prompt


# ---------------------------------------------------------------------------
# Genre style registry
# ---------------------------------------------------------------------------

_TITLE_STYLES: dict[str, TitleStyle] = {
    "power_growth": TitleStyle(
        genre="power_growth",
        pattern="热血中二·境界突破",
        examples=["万剑归宗·剑心觉醒", "破境·踏入金丹", "一拳镇杀·威震四方"],
        tone_keywords=["热血", "觉醒", "突破", "震慑", "逆天", "崛起"],
    ),
    "political_intrigue": TitleStyle(
        genre="political_intrigue",
        pattern="权谋暗涌·棋局变换",
        examples=["暗棋·朝堂风云再起", "毒计·后宫暗流", "夺嫡·终局之战"],
        tone_keywords=["暗涌", "棋局", "权谋", "布局", "反击", "清算"],
    ),
    "romance_relationship": TitleStyle(
        genre="romance_relationship",
        pattern="情感细腻·心意流转",
        examples=["雨夜·心意终相通", "误会·渐行渐远", "重逢·旧情难忘"],
        tone_keywords=["心动", "误解", "守护", "心意", "温柔", "告白"],
    ),
    "adventure_survival": TitleStyle(
        genre="adventure_survival",
        pattern="冒险紧张·生死一线",
        examples=["深渊·生死一线", "逃亡·黎明之前", "绝境·最后的赌注"],
        tone_keywords=["危机", "生死", "逃亡", "绝境", "希望", "代价"],
    ),
    "mystery_revelation": TitleStyle(
        genre="mystery_revelation",
        pattern="悬疑揭秘·迷雾渐散",
        examples=["迷雾·真相渐明", "线索·拼图成形", "揭露·暗夜终结"],
        tone_keywords=["迷雾", "真相", "线索", "揭露", "反转", "解谜"],
    ),
    "career_reversal": TitleStyle(
        genre="career_reversal",
        pattern="逆袭爽文·一鸣惊人",
        examples=["翻盘·一鸣惊人", "逆袭·打脸全场", "崛起·商战风云"],
        tone_keywords=["逆袭", "翻盘", "打脸", "崛起", "碾压", "反杀"],
    ),
}

_SUMMARY_TONES: dict[str, SummaryTone] = {
    "power_growth": SummaryTone(
        genre="power_growth",
        tone_description="热血激昂，强调境界突破的震撼感和战斗的爽快节奏",
        emphasis_points=[
            "境界突破的具体变化和意义",
            "战斗中的关键转折和逆转",
            "实力对比的变化",
            "获得的功法/宝物/传承",
            "下一阶段的挑战预告",
        ],
        avoid_points=[
            "冗长的修炼过程描写",
            "重复的嘲讽对白",
            "纯环境描写",
            "无后续影响的日常",
        ],
    ),
    "political_intrigue": SummaryTone(
        genre="political_intrigue",
        tone_description="暗流涌动，强调势力消长和计谋布局的精妙",
        emphasis_points=[
            "谁布局、谁中计、谁获利",
            "势力格局的变化",
            "关键情报/把柄/证据的获取",
            "联盟与背叛",
            "权力结构的重新洗牌",
        ],
        avoid_points=[
            "无后果的社交寒暄",
            "仪式流程细节",
            "不改变格局的小摩擦",
            "纯环境描写",
        ],
    ),
    "romance_relationship": SummaryTone(
        genre="romance_relationship",
        tone_description="细腻温情，强调情感变化和心理转折",
        emphasis_points=[
            "关系推进的关键节点",
            "误会的形成与解开",
            "心理变化的转折点",
            "告白/确认/分手/重逢",
            "情敌/家庭阻力的影响",
        ],
        avoid_points=[
            "无情感推进的甜蜜日常",
            "重复的心跳脸红描写",
            "纯氛围烘托",
            "不影响关系走向的事件",
        ],
    ),
    "adventure_survival": SummaryTone(
        genre="adventure_survival",
        tone_description="紧张刺激，强调生存压力和团队抉择",
        emphasis_points=[
            "任务目标和规则变化",
            "生存危机和应对策略",
            "团队分裂/合作/背叛",
            "关键资源的得失",
            "关卡通过/失败的代价",
        ],
        avoid_points=[
            "重复的清怪战斗",
            "普通行路描写",
            "低影响的营地闲聊",
            "已知信息的重复",
        ],
    ),
    "mystery_revelation": SummaryTone(
        genre="mystery_revelation",
        tone_description="层层剥茧，强调线索发现和真相逼近的紧迫感",
        emphasis_points=[
            "新线索的发现",
            "关键推理和排除",
            "误导与反转",
            "真相揭露的震撼",
            "调查者自身的危险",
        ],
        avoid_points=[
            "已排除的无效线索反复提及",
            "日常调查流程",
            "不推进真相的对话",
            "纯恐怖氛围描写",
        ],
    ),
    "career_reversal": SummaryTone(
        genre="career_reversal",
        tone_description="爽快明快，强调身份反转和社会地位跃升",
        emphasis_points=[
            "被压制到反杀的完整弧线",
            "身份/地位的关键变化",
            "项目/商战的胜负结果",
            "社会关系网络的重构",
            "打脸和逆袭的高光时刻",
        ],
        avoid_points=[
            "日常工作流程",
            "不改变地位的小冲突",
            "重复的炫耀/嘲讽描写",
            "纯社交场景",
        ],
    ),
}

_RETENTION_PRIORITIES: dict[str, RetentionPriority] = {
    "power_growth": RetentionPriority(
        genre="power_growth",
        priority_order=["战斗/对决", "突破/升级", "奇遇/传承", "势力变化", "关系变化", "日常"],
        boost_event_types=[
            "breakthrough", "victory", "defeat", "turning_point",
            "power_shift", "treasure_gain", "inheritance",
        ],
        demote_event_types=["daily_life", "travel", "training_routine", "spectator_reaction"],
    ),
    "political_intrigue": RetentionPriority(
        genre="political_intrigue",
        priority_order=["阴谋/布局", "揭露/暴露", "联盟/背叛", "势力变化", "情报获取", "日常"],
        boost_event_types=[
            "scheme_success", "scheme_failure", "betrayal", "secret_exposed",
            "alliance_formed", "alliance_broken", "favor_gained", "favor_lost",
        ],
        demote_event_types=["ceremony", "pleasantry", "trivial_dispute", "daily_life"],
    ),
    "romance_relationship": RetentionPriority(
        genre="romance_relationship",
        priority_order=["情感转折", "误会形成/解开", "告白/确认", "情敌/阻力", "心理变化", "日常"],
        boost_event_types=[
            "confession", "relationship_confirmed", "breakup", "reunion",
            "misunderstanding_formed", "misunderstanding_resolved", "rival_entry",
            "jealousy", "intimacy_escalation",
        ],
        demote_event_types=["daily_life", "sweet_no_progress", "atmosphere", "routine_date"],
    ),
    "adventure_survival": RetentionPriority(
        genre="adventure_survival",
        priority_order=["生存危机", "任务变化", "团队变动", "规则发现", "资源得失", "日常"],
        boost_event_types=[
            "survival_crisis", "mission_change", "team_split", "team_betrayal",
            "rule_discovery", "stage_clear", "stage_failure", "resource_critical",
        ],
        demote_event_types=["monster_clearing", "travel_routine", "camp_banter", "daily_life"],
    ),
    "mystery_revelation": RetentionPriority(
        genre="mystery_revelation",
        priority_order=["真相揭露", "关键线索", "推理突破", "误导/反转", "调查者危机", "日常"],
        boost_event_types=[
            "truth_reveal", "clue_discovery", "key_deduction", "twist",
            "false_lead_exposed", "investigator_danger",
        ],
        demote_event_types=["dead_end", "routine_investigation", "atmosphere", "daily_life"],
    ),
    "career_reversal": RetentionPriority(
        genre="career_reversal",
        priority_order=["逆袭/翻盘", "身份变化", "商战胜负", "社会关系重构", "被压制", "日常"],
        boost_event_types=[
            "status_rise", "face_slapping", "project_success", "reputation_change",
            "identity_reveal", "counterattack", "suppression",
        ],
        demote_event_types=["work_routine", "trivial_conflict", "social_scene", "daily_life"],
    ),
}


class GenreStyleEngine:
    """Provides genre-specific style guidance for title, summary, and retention."""

    def get_title_style(self, genre: str) -> TitleStyle:
        if genre in _TITLE_STYLES:
            return _TITLE_STYLES[genre]
        # hybrid or unknown: fall back to power_growth as default
        return _TITLE_STYLES.get("power_growth", TitleStyle(genre=genre, pattern=""))

    def get_summary_tone(self, genre: str) -> SummaryTone:
        if genre in _SUMMARY_TONES:
            return _SUMMARY_TONES[genre]
        return _SUMMARY_TONES.get(
            "power_growth", SummaryTone(genre=genre, tone_description="")
        )

    def get_retention_priority(self, genre: str) -> RetentionPriority:
        if genre in _RETENTION_PRIORITIES:
            return _RETENTION_PRIORITIES[genre]
        return _RETENTION_PRIORITIES.get(
            "power_growth", RetentionPriority(genre=genre)
        )

    def get_episode_prompt(self, genre: str, prompts_dir: Path) -> str | None:
        """Load genre-specific episode prompt if available."""
        genre_dir = prompts_dir / "genre_episode_styles"
        prompt_file = genre_dir / f"{genre}_episode.md"
        if prompt_file.exists():
            return load_prompt(prompt_file)
        return None

    def get_scoring_adjustments(self, genre: str) -> dict[str, list[str]]:
        """Return boost/demote event type lists for scoring adjustments."""
        priority = self.get_retention_priority(genre)
        return {
            "boost_event_types": priority.boost_event_types,
            "demote_event_types": priority.demote_event_types,
        }
