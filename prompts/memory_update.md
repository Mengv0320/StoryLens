## 角色/故事记忆增量更新

你是一位专业的小说数据库管理员。你的任务是根据新章节的分析结果，增量更新故事记忆数据库。

### 更新原则（必须严格遵守）

1. **只增量更新** — 只修改本章涉及的条目，未提及的角色/关系保持不变
2. **严禁编造** — 只能使用本章事件中明确提到的信息，不可推测
3. **别名合并** — 如果本章出现了已知角色的新称呼，添加到 aliases，不要创建新角色
4. **状态连续** — 角色状态只在有明确证据时才改变（如明确写到角色死亡才改 status）
5. **数量限制** — characters ≤ 30，relationships ≤ 40，factions ≤ 10，unresolved_foreshadowing ≤ 15

### 体裁
{{genre_hint}}

### 当前记忆快照
{{current_memory}}

### 本章信息
- 章节 ID：{{chapter_id}}
- 章节标题：{{chapter_title}}
- 章节概要：{{chapter_summary}}

### 本章提取事件
{{chapter_events}}

### 你需要做的

分析本章事件，输出更新后的完整记忆 JSON。具体地：

**角色更新**：
- 新角色：只有在事件中出现 ≥2 次或 importance ≥ 3 的事件中提到时才新增
- 已有角色：更新 last_seen_chapter，如有新信息则更新对应字段
- 别名发现：本章对某角色使用了新的称呼 → 加入该角色 aliases
- 境界变化：如事件类型为"身份变化"且 involves_death_or_breakthrough=true → 更新 power_level
- 状态变化：角色死亡/失踪需事件明确记录
- 角色超过 30 个时：移除 last_seen_chapter 最旧且 role="minor" 的角色

**关系更新**：
- 新关系：两个角色首次在事件中产生有意义的互动 → 新增关系
- 关系变化：involves_relationship_change=true 的事件 → 更新 relation_type 和 description
- 关系超过 40 条时：移除最旧的 minor 角色间的关系

**势力更新**：
- 新势力：本章首次提及的组织/门派/势力
- 成员变动：involves_faction_change=true 的事件 → 更新 key_members
- 势力状态：如势力被消灭/解散，更新 status

**剧情状态更新**：
- current_arc：如本章标志着新篇章/弧开始，更新弧名
- active_threads：新增/结束支线
- unresolved_foreshadowing：新增伏笔（event_type="伏笔"），移除已回收伏笔（event_type="伏笔回收"）
- recent_events_digest：用 ≤250 字概括**最近 3-5 章**的关键剧情（覆盖旧摘要）

### 输出格式

严格输出 JSON，不要输出其他内容。输出更新后的**完整记忆对象**（不是 diff）：

```json
{
  "characters": [
    {
      "name": "角色名",
      "aliases": ["别名1"],
      "role": "protagonist|antagonist|supporting|minor",
      "faction": "势力名",
      "status": "alive|dead|missing|unknown",
      "power_level": "境界",
      "personality_traits": ["特质1"],
      "summary": "一句话概要（≤160字）",
      "last_seen_chapter": "ch_010"
    }
  ],
  "relationships": [
    {
      "character_a": "角色A",
      "character_b": "角色B",
      "relation_type": "hostile|suspicious|allied|subordinate|mentor|family|romantic|rival|unknown",
      "description": "关系描述（≤100字）",
      "since_chapter": "ch_001"
    }
  ],
  "factions": [
    {
      "name": "势力名",
      "description": "势力简介（≤160字）",
      "key_members": ["成员1"],
      "status": "active|disbanded|destroyed|unknown"
    }
  ],
  "plot_state": {
    "current_arc": "当前弧名（≤60字）",
    "arc_summary": "弧概要（≤300字）",
    "active_threads": ["支线1"],
    "unresolved_foreshadowing": ["伏笔1"],
    "recent_events_digest": "最近3-5章剧情摘要（≤500字）"
  },
  "last_chapter_id": "ch_010",
  "last_chapter_title": "第十章 标题",
  "total_chapters_processed": 10
}
```

### Few-Shot 示例

**输入场景**：第 10 章「比武大会」，主角林动在比武中以淬体八重的实力击败雷冲，暴露了吞噬祖符的隐藏实力，引起炎城林家长老注意。

**当前记忆快照（部分）**：
```json
{
  "characters": [
    {
      "name": "林动",
      "aliases": ["小子"],
      "role": "protagonist",
      "faction": "青阳镇林家",
      "status": "alive",
      "power_level": "淬体六重",
      "personality_traits": ["坚韧", "隐忍", "重情义"],
      "summary": "青阳镇林家天才少年，意外获得神秘石符",
      "last_seen_chapter": "ch_009"
    },
    {
      "name": "林啸",
      "aliases": [],
      "role": "supporting",
      "faction": "青阳镇林家",
      "status": "alive",
      "power_level": "天元境初期",
      "personality_traits": ["沉稳", "慈爱"],
      "summary": "林动的祖父，青阳镇林家族长",
      "last_seen_chapter": "ch_007"
    }
  ],
  "relationships": [
    {
      "character_a": "林动",
      "character_b": "林啸",
      "relation_type": "family",
      "description": "祖孙关系，林啸是林动最亲近的长辈",
      "since_chapter": "ch_001"
    }
  ],
  "factions": [
    {
      "name": "青阳镇林家",
      "description": "林家旁支，实力较弱，依附炎城林家",
      "key_members": ["林动", "林啸"],
      "status": "active"
    }
  ],
  "plot_state": {
    "current_arc": "青阳镇篇",
    "arc_summary": "林动在青阳镇修炼成长，为参加家族比武做准备",
    "active_threads": ["石符秘密", "林家比武大会"],
    "unresolved_foreshadowing": ["石符中的神秘老人身份未明"],
    "recent_events_digest": "林动通过石符修炼突飞猛进，秘密突破至淬体六重。"
  },
  "last_chapter_id": "ch_009",
  "last_chapter_title": "第九章 暗中突破",
  "total_chapters_processed": 9
}
```

**本章事件**：
```json
[
  {
    "event_id": "evt_001",
    "event_type": "身份变化",
    "title": "林动实力曝光",
    "description": "林动暴露出远超预期的淬体八重修为，震惊全场",
    "characters": ["林动"],
    "involves_death_or_breakthrough": true,
    "importance": 4
  },
  {
    "event_id": "evt_002",
    "event_type": "冲突",
    "title": "林动击败雷冲",
    "description": "林动以淬体八重实力击败淬体九重的雷冲",
    "characters": ["林动", "雷冲"],
    "involves_relationship_change": true,
    "importance": 5
  },
  {
    "event_id": "evt_003",
    "event_type": "伏笔",
    "title": "炎城林家长老关注",
    "description": "炎城林家长老林奎暗中观察林动，似有图谋",
    "characters": ["林动", "林奎"],
    "importance": 3
  }
]
```

**期望 JSON 输出**：
```json
{
  "characters": [
    {
      "name": "林动",
      "aliases": ["小子"],
      "role": "protagonist",
      "faction": "青阳镇林家",
      "status": "alive",
      "power_level": "淬体八重",
      "personality_traits": ["坚韧", "隐忍", "重情义"],
      "summary": "青阳镇林家天才少年，在比武大会上击败雷冲一战成名",
      "last_seen_chapter": "ch_010"
    },
    {
      "name": "林啸",
      "aliases": [],
      "role": "supporting",
      "faction": "青阳镇林家",
      "status": "alive",
      "power_level": "天元境初期",
      "personality_traits": ["沉稳", "慈爱"],
      "summary": "林动的祖父，青阳镇林家族长",
      "last_seen_chapter": "ch_007"
    },
    {
      "name": "雷冲",
      "aliases": [],
      "role": "minor",
      "faction": "",
      "status": "alive",
      "power_level": "淬体九重",
      "personality_traits": ["好斗"],
      "summary": "比武大会参赛者，淬体九重高手，被林动击败",
      "last_seen_chapter": "ch_010"
    },
    {
      "name": "林奎",
      "aliases": [],
      "role": "supporting",
      "faction": "炎城林家",
      "status": "alive",
      "power_level": "",
      "personality_traits": ["老练"],
      "summary": "炎城林家长老，在比武大会上注意到林动的异常实力",
      "last_seen_chapter": "ch_010"
    }
  ],
  "relationships": [
    {
      "character_a": "林动",
      "character_b": "林啸",
      "relation_type": "family",
      "description": "祖孙关系，林啸是林动最亲近的长辈",
      "since_chapter": "ch_001"
    },
    {
      "character_a": "林动",
      "character_b": "雷冲",
      "relation_type": "rival",
      "description": "林动在比武大会上击败雷冲",
      "since_chapter": "ch_010"
    }
  ],
  "factions": [
    {
      "name": "青阳镇林家",
      "description": "林家旁支，实力较弱，依附炎城林家",
      "key_members": ["林动", "林啸"],
      "status": "active"
    },
    {
      "name": "炎城林家",
      "description": "林家主脉，掌控炎城及周边领地",
      "key_members": ["林奎"],
      "status": "active"
    }
  ],
  "plot_state": {
    "current_arc": "青阳镇篇",
    "arc_summary": "林动在青阳镇修炼成长，在比武大会上崭露头角",
    "active_threads": ["石符秘密", "炎城林家对林动的关注"],
    "unresolved_foreshadowing": ["石符中的神秘老人身份未明", "炎城林家长老林奎暗中观察林动"],
    "recent_events_digest": "林动通过石符秘密修炼至淬体八重，在比武大会上击败淬体九重的雷冲，实力曝光引起炎城林家长老林奎注意。"
  },
  "last_chapter_id": "ch_010",
  "last_chapter_title": "第十章 比武大会",
  "total_chapters_processed": 10
}
```

### 注意
- 输出完整的记忆 JSON，不是增量 diff
- 不要发明角色档案中未提及的信息（如编造角色的过去经历）
- 如果本章没有任何需要更新的信息，直接返回原记忆（只更新 last_chapter_id/title/total_chapters_processed）
- characters 列表中每个角色的 name 必须是唯一的归一化主名
- recent_events_digest 是滚动窗口，保留最近内容，旧内容自然被覆盖
- 所有文本字段用中文
- 不要输出 JSON 以外的内容
