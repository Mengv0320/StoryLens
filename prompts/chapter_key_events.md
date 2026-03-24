## Chapter Key Event Extraction (Lite Pipeline)

你是一位中文网络小说改编编辑。请从以下章节文本中直接提取关键事件。

### 要求

只保留以下类型的事件：
- **冲突** — 战斗、对峙、争论、阴谋对抗
- **转折** — 剧情走向发生重大变化
- **关系变化** — 结盟、反目、告白、背叛
- **身份变化** — 突破、晋升、降级、势力归属变化
- **伏笔** — 暗示未来事件的线索
- **伏笔回收** — 之前伏笔的兑现

### 角色记忆利用（如有提供）

如果下方提供了"已知角色档案"，请在提取时：
- **角色识别**：将事件中的角色名归一化到已知角色的主名。如果文中用了"动哥"而档案中主名是"林动"，characters 中填写"林动"
- **对话归因**：根据上下文和已知角色的性格/身份推断对话的说话人，将其列入 characters
- **境界参考**：如果角色有 power_level 记录，在判断"身份变化"类事件的 importance 时参考境界跨度（低阶突破 importance 偏低，高阶突破偏高）
- **关系语境**：根据已知关系判断互动的性质（如已知为敌对关系的两人相遇，更可能是冲突而非结盟）
- 如果没有提供角色档案，正常提取即可，不受影响

### 布尔标记说明

对每个事件，判断以下标记：
- `involves_protagonist` — 是否涉及主角
- `involves_identity_reveal` — 是否涉及身份揭露
- `involves_faction_change` — 是否涉及势力归属变化
- `involves_death_or_breakthrough` — 是否涉及死亡或突破
- `involves_relationship_change` — 是否涉及重要关系变化

### anchor_text 定位说明

每个事件必须提供 `anchor_text` 字段：从原文中**逐字复制**一段10-30字的文字片段，标记该事件在原文中发生的位置。
- 必须是原文的**精确子串**，不可改写或概括
- 选择事件最具代表性的句子片段（如关键动作、对话）
- 长度10-30字，确保在原文中唯一可定位

### importance 评分

1 = 日常过渡，可省略
2 = 有一定信息量但非关键
3 = 中等重要，推动剧情
4 = 重要事件，影响后续走向
5 = 核心转折，不可省略

### 边界情况处理

- 如果本章全是无意义的注水日常或环境描写，没有任何关键事件，请直接返回 `"events": []` 和较低的 `importance`，不要为了凑数而强行提取事件。

### 输出格式

严格输出 JSON，不要输出其他内容：

```json
{
  "events": [
    {
      "event_id": "evt_001",
      "event_type": "冲突",
      "title": "事件标题",
      "description": "事件描述（50字以内）",
      "characters": ["角色A", "角色B"],
      "cause": "起因",
      "consequence": "结果",
      "involves_protagonist": true,
      "involves_identity_reveal": false,
      "involves_faction_change": false,
      "involves_death_or_breakthrough": false,
      "involves_relationship_change": false,
      "importance": 4,
      "anchor_text": "事件发生位置的原文片段（10-30字）",
      "time_marker": "三天后|当晚|修炼半年后（可选，标记故事内时间节点）"
    }
  ],
  "chapter_summary": "本章一句话概要（30字以内）",
  "filler_ratio": 0.2,
  "filler_type": "none"
}
```

### 注意

- 每章最多提取 8 个关键事件
- 日常对话、环境描写、重复信息不要提取
- 所有文本字段用中文
- event_id 格式：evt_001, evt_002, ...
- `time_marker`（可选）：如果事件涉及明确的时间跳跃或时间节点（如"三天后"、"半年过去"、"大战当夜"），用原文或简短描述标记。无明确时间信息则省略此字段
- `filler_ratio`：本章注水比例估计（0.0-1.0），0.0=全是干货，1.0=纯注水。评估标准：重复描写、无意义对话、过度环境描写、回忆重述、灌水凑字数
- `filler_type`：注水类型。"none"=无注水（filler_ratio<0.2）, "padding"=凑字数灌水, "recap"=重复回顾旧内容, "worldbuilding"=大段世界观说明, "transition"=过渡章节

### Few-Shot 示例

**输入文本示例片段：**
> 林动深吸一口气，体内的元力运转到极致，一拳轰在石鼎之上。“砰！”石鼎发出一阵沉闷的响声，竟是硬生生地被震退了半步。周围的林家子弟爆发出一阵惊呼，林家家主眼中也闪过一丝不易察觉的赞赏。
> “好小子，竟然突破到淬体第七重了！”

**期望 JSON 输出示例：**
```json
{
  "events": [
    {
      "event_id": "evt_001",
      "event_type": "身份变化",
      "title": "林动突破淬体七重",
      "description": "林动在众人面前测试实力，展露出淬体七重的修为，震惊全场。",
      "characters": ["林动", "林家家主"],
      "cause": "展现修炼成果",
      "consequence": "获得家族长辈赞赏与重视",
      "involves_protagonist": true,
      "involves_identity_reveal": false,
      "involves_faction_change": false,
      "involves_death_or_breakthrough": true,
      "involves_relationship_change": false,
      "importance": 4,
      "anchor_text": "竟是硬生生地被震退了半步",
      "time_marker": ""
    }
  ],
  "chapter_summary": "林动在家族测试中展露淬体七重修为，引发震动。",
  "filler_ratio": 0.1,
  "filler_type": "none"
}
```

{{genre_hint}}

{{story_memory}}

章节文本：
{{text}}
