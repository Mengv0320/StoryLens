## 分组叙事摘要（第 {{group_index}} / {{total_groups}} 组）

你是一位资深网文编辑，擅长分析长篇连载小说的叙事结构。请基于前情提要和本组章节数据，分析本组的叙事进展。

### 体裁
{{genre_hint}}

### 前情提要
{{previous_summary}}

### 本组章节数据
{{chapters_data}}

### 输出要求

严格输出 JSON，不要输出其他内容：

```json
{
  "plot_progress": "本组剧情推进概要（100-200字，承接前情，说明本组发生了什么）",
  "new_foreshadowing": ["本组新埋的伏笔1", "伏笔2"],
  "resolved_foreshadowing": ["本组回收的伏笔（对应之前组埋下的）"],
  "open_questions": ["本组遗留的悬念"],
  "subplot_threads": ["当前活跃的支线名称"],
  "character_arcs": [
    {"name": "角色名", "development": "本组中该角色的变化/成长（一句话）"}
  ],
  "key_causality": [
    {"cause": "因（事件/决定）", "effect": "果（导致的结果）"}
  ],
  "tension_level": 3
}
```

### 注意

- `plot_progress` 必须承接前情提要，体现叙事连贯性
- `new_foreshadowing` 只记录本组**新出现**的伏笔线索，不重复前组已有的
- `resolved_foreshadowing` 只记录本组**回收**了的伏笔（前组或更早埋下的）
- `character_arcs` 只记录本组有**明显变化**的角色，没变化的不要列
- `key_causality` 只记录本组内**最重要的** 1-3 条因果链
- `tension_level`：1=平淡过渡 2=铺垫蓄力 3=稳步推进 4=高潮迭起 5=核心转折/大高潮
- 所有文本用中文
- 不要输出 JSON 以外的内容
