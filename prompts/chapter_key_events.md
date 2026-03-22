## Chapter Key Event Extraction (Lite Pipeline)

你是一位中文网络小说改编编辑。请从以下章节文本中直接提取关键事件。

### 要求

只保留以下类型的事件：
- **conflict** — 冲突（战斗、对峙、争论、阴谋对抗）
- **turning_point** — 转折（剧情走向发生重大变化）
- **relationship_change** — 关系变化（结盟、反目、告白、背叛）
- **status_change** — 身份/地位变化（突破、晋升、降级、势力归属变化）
- **foreshadowing** — 伏笔（暗示未来事件的线索）
- **payoff** — 回收（之前伏笔的兑现）

### 布尔标记说明

对每个事件，判断以下标记：
- `involves_protagonist` — 是否涉及主角
- `involves_identity_reveal` — 是否涉及身份揭露
- `involves_faction_change` — 是否涉及势力归属变化
- `involves_death_or_breakthrough` — 是否涉及死亡或突破
- `involves_relationship_change` — 是否涉及重要关系变化

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
      "event_type": "conflict",
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
      "importance": 4
    }
  ],
  "chapter_summary": "本章一句话概要（30字以内）"
}
```

### 注意

- 每章最多提取 8 个关键事件
- 日常对话、环境描写、重复信息不要提取
- 所有文本字段用中文
- event_id 格式：evt_001, evt_002, ...

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
      "event_type": "status_change",
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
      "importance": 4
    }
  ],
  "chapter_summary": "林动在家族测试中展露淬体七重修为，引发震动。"
}
```

{{genre_hint}}

章节文本：
{{text}}
