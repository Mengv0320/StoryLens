# Task 2: 记忆更新 Prompt + Schema

## 目标

新建记忆更新的 LLM prompt 模板和输出 schema。这两个文件定义了"每章分析后 LLM 如何增量更新记忆"的契约。

**本任务只新增 2 个文件，不修改任何 Python 代码或已有 prompt/schema。**

## 涉及文件

| 操作 | 文件 | 说明 |
|------|------|------|
| **新建** | `prompts/memory_update.md` | 记忆更新 prompt 模板 |
| **新建** | `schemas/memory_update.schema.json` | 记忆更新输出 schema |

## 禁止触碰的文件

- `src/*.py`（所有 Python 文件）
- `prompts/chapter_key_events.md`
- `prompts/narrative_summary.md`
- `prompts/book_synthesis.md`
- `schemas/chapter_key_events.schema.json`
- `schemas/narrative_summary.schema.json`

---

## prompts/memory_update.md

### 模板变量

| 变量 | 类型 | 说明 |
|------|------|------|
| `{{current_memory}}` | JSON string | 当前记忆快照的完整 JSON（StoryMemory.to_dict() 的输出） |
| `{{chapter_id}}` | string | 当前章节 ID |
| `{{chapter_title}}` | string | 当前章节标题 |
| `{{chapter_summary}}` | string | 本章一句话概要（来自 chapter_key_events 提取结果） |
| `{{chapter_events}}` | JSON string | 本章提取的事件列表 JSON（key_events 数组） |
| `{{genre_hint}}` | string | 体裁提示 |

### Prompt 内容要求

按以下结构编写 prompt：

```
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
```

然后给出 JSON 结构示例（与 StoryMemory.to_dict() 输出格式一致）和 Few-Shot 示例。

### Few-Shot 示例

提供一个完整示例，包含：

**输入场景**：第 10 章，主角林动在比武中击败对手，暴露了隐藏实力，引起某势力注意。

**示例输出**：展示如何：
- 更新林动的 power_level
- 新增被击败角色（如果够重要）
- 新增/更新关系
- 更新 recent_events_digest
- 保持其他未变化的条目不变

### 关键注意事项

在 prompt 末尾强调：

```
### 注意
- 输出完整的记忆 JSON，不是增量 diff
- 不要发明角色档案中未提及的信息（如编造角色的过去经历）
- 如果本章没有任何需要更新的信息，直接返回原记忆（只更新 last_chapter_id/title/total_chapters_processed）
- characters 列表中每个角色的 name 必须是唯一的归一化主名
- recent_events_digest 是滚动窗口，保留最近内容，旧内容自然被覆盖
- 所有文本字段用中文
- 不要输出 JSON 以外的内容
```

---

## schemas/memory_update.schema.json

### Schema 结构

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "MemoryUpdate",
  "description": "Updated story memory after processing a chapter",
  "type": "object",
  "required": [
    "characters", "relationships", "factions", "plot_state",
    "last_chapter_id", "last_chapter_title", "total_chapters_processed"
  ],
  "properties": {
    "characters": {
      "type": "array",
      "maxItems": 30,
      "items": { "$ref": "#/$defs/CharacterProfile" }
    },
    "relationships": {
      "type": "array",
      "maxItems": 40,
      "items": { "$ref": "#/$defs/Relationship" }
    },
    "factions": {
      "type": "array",
      "maxItems": 10,
      "items": { "$ref": "#/$defs/FactionInfo" }
    },
    "plot_state": { "$ref": "#/$defs/PlotState" },
    "last_chapter_id": { "type": "string" },
    "last_chapter_title": { "type": "string" },
    "total_chapters_processed": { "type": "integer", "minimum": 0 }
  },
  "additionalProperties": false,
  "$defs": { ... }
}
```

### $defs 中的子类型

**CharacterProfile**：
```json
{
  "type": "object",
  "required": ["name", "role", "status", "summary", "last_seen_chapter"],
  "properties": {
    "name": { "type": "string" },
    "aliases": { "type": "array", "items": { "type": "string" }, "default": [] },
    "role": { "type": "string", "enum": ["protagonist", "antagonist", "supporting", "minor"] },
    "faction": { "type": "string", "default": "" },
    "status": { "type": "string", "enum": ["alive", "dead", "missing", "unknown"] },
    "power_level": { "type": "string", "default": "" },
    "personality_traits": { "type": "array", "items": { "type": "string" }, "maxItems": 5, "default": [] },
    "summary": { "type": "string", "maxLength": 160 },
    "last_seen_chapter": { "type": "string" }
  },
  "additionalProperties": false
}
```

**Relationship**：
```json
{
  "type": "object",
  "required": ["character_a", "character_b", "relation_type", "description", "since_chapter"],
  "properties": {
    "character_a": { "type": "string" },
    "character_b": { "type": "string" },
    "relation_type": {
      "type": "string",
      "enum": ["hostile", "suspicious", "allied", "subordinate", "mentor", "family", "romantic", "rival", "unknown"]
    },
    "description": { "type": "string", "maxLength": 100 },
    "since_chapter": { "type": "string" }
  },
  "additionalProperties": false
}
```

**FactionInfo**：
```json
{
  "type": "object",
  "required": ["name", "description", "status"],
  "properties": {
    "name": { "type": "string" },
    "description": { "type": "string", "maxLength": 160 },
    "key_members": { "type": "array", "items": { "type": "string" }, "maxItems": 10, "default": [] },
    "status": { "type": "string", "enum": ["active", "disbanded", "destroyed", "unknown"] }
  },
  "additionalProperties": false
}
```

**PlotState**：
```json
{
  "type": "object",
  "required": ["current_arc", "recent_events_digest"],
  "properties": {
    "current_arc": { "type": "string", "maxLength": 60 },
    "arc_summary": { "type": "string", "maxLength": 300, "default": "" },
    "active_threads": { "type": "array", "items": { "type": "string" }, "maxItems": 10, "default": [] },
    "unresolved_foreshadowing": { "type": "array", "items": { "type": "string" }, "maxItems": 15, "default": [] },
    "recent_events_digest": { "type": "string", "maxLength": 500 }
  },
  "additionalProperties": false
}
```

## 验证方式

1. 用 `src/schema_validator.py` 的 `SchemaValidator` 加载 `memory_update.schema.json`，确认能解析
2. 手工构造一个符合 schema 的 JSON 样例，验证通过
3. 手工构造一个违反约束的 JSON（如 characters 超过 30 个），验证被拒
4. `prompts/memory_update.md` 中所有 `{{变量}}` 与 Task 4 集成时的 `render_prompt()` 调用匹配

## 编码约束

- Schema 使用 JSON Schema draft 2020-12（与项目已有 schema 一致）
- 字段名使用 snake_case（与 Python 数据类一致，区别于前端的 camelCase）
- Prompt 模板变量用 `{{double_braces}}`（与 `src/prompt_loader.py` 的 `render_prompt` 一致）
- Schema 的 `$defs` 命名用 PascalCase（与已有 schema 风格一致）
- Prompt 语言为中文，JSON 字段名为英文
