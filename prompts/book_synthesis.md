## 全书叙事综合分析

你是一位资深网文编辑，正在为一部长篇小说撰写深度叙事分析报告。请基于所有分组摘要数据，生成全书综合分析。

### 体裁
{{genre}}

### 基本信息
- 书名：{{book_title}}
- 总章节数：{{total_chapters}}
- 总分组数：{{total_groups}}

### 所有分组摘要
{{group_summaries}}

### 边界情况处理
- 如果全书没有任何支线，`subplot_summary` 输出 `[]`。
- 如果全书没有伏笔或者没回收，`foreshadowing_tracker` 输出 `[]`。
- 如果没有明显角色的弧线，`character_arcs` 输出 `[]`。

### 输出要求

严格输出 JSON，不要输出其他内容：

```json
{
  "main_plotline": "主线剧情完整概要（200-400字，从开篇到最新进展）",
  "subplot_summary": [
    {"thread": "支线名称", "summary": "支线概要", "status": "active"}
  ],
  "foreshadowing_tracker": [
    {"setup": "伏笔描述", "setup_group": "grp_001", "resolved_group": "grp_003"}
  ],
  "character_arcs": [
    {
      "name": "角色名",
      "arc_summary": "该角色的完整成长弧线（50-100字）",
      "key_moments": ["grp_001:具体事件", "grp_005:具体事件"]
    }
  ],
  "tension_curve": [
    {"group_id": "grp_001", "level": 3, "reason": "简要原因"}
  ],
  "themes": ["核心主题1", "核心主题2"],
  "open_questions": ["全书未解悬念1", "悬念2"],
  "quality_notes": ["节奏问题/叙事断裂等备注"]
}
```

### 注意

- `main_plotline` 要有完整的起承转合，不是简单拼接各组摘要
- `foreshadowing_tracker` 要跨组追踪，`resolved_group` 可以是 `null`
- `character_arcs` 只列出有**完整弧线**的重要角色（≤10个）
- `tension_curve` 每组一条，反映全书节奏曲线
- `quality_notes` 如果发现节奏失衡、支线断裂、伏笔遗忘等问题要指出
- `subplot_summary` 中 status 取值：`active`=进行中 `resolved`=已完结 `abandoned`=被遗忘/放弃
- 所有文本用中文
- 不要输出 JSON 以外的内容

### Few-Shot 示例
```json
{
  "main_plotline": "主角重生后拜入仙宗，发现宗门暗藏玄机，通过外门大比展现实力，随后卷入真传弟子间的夺嫡斗争，并在神秘秘境中获得上古传承...",
  "subplot_summary": [
    {"thread": "重建家族", "summary": "主角暗中扶持破败家族重新崛起", "status": "active"}
  ],
  "foreshadowing_tracker": [
    {"setup": "后山的神秘呼吸声", "setup_group": "grp_001", "resolved_group": "grp_004"}
  ],
  "character_arcs": [
    {
      "name": "林婉儿",
      "arc_summary": "从傲娇的千金小姐成长为能独当一面的剑修",
      "key_moments": ["grp_002:败给主角后觉醒", "grp_005:生死关头突破"]
    }
  ],
  "tension_curve": [
    {"group_id": "grp_001", "level": 2, "reason": "日常修炼奠基"},
    {"group_id": "grp_002", "level": 4, "reason": "外门大比激烈冲突"}
  ],
  "themes": ["修仙求道", "利益与背叛"],
  "open_questions": ["上古宗门覆灭的真凶是谁？"],
  "quality_notes": ["前两组节奏偏慢，秘境剧情紧凑"]
}
```
