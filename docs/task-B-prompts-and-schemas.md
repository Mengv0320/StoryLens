# 任务 B：叙事分析 Prompt 模板 + JSON Schema

## 目标

新建 2 个 prompt 模板和 2 个 JSON Schema，供分层叙事分析引擎使用。

## 约束

- **只新建以下文件**，不碰任何 .py / .ts / .tsx 文件：
  - 新建：`prompts/narrative_summary.md`
  - 新建：`prompts/book_synthesis.md`
  - 新建：`schemas/narrative_summary.schema.json`
  - 新建：`schemas/book_synthesis.schema.json`
- 不修改任何已有文件

## 参考：已有 prompt 风格

参考 `prompts/chapter_key_events.md` 的风格：
- 中文指令
- 明确的输出 JSON 格式示例
- 用 `{{变量名}}` 做模板占位符
- 末尾放输入数据

参考 `schemas/chapter_key_events.schema.json` 的风格：
- 标准 JSON Schema draft-07
- 所有字段都有 `type` 和 `description`
- `required` 列出必填字段
- `additionalProperties: false`

## 文件 1：`prompts/narrative_summary.md`

### 用途
对一组章节（约5章）生成叙事摘要，带滚动上下文。

### 模板变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `{{previous_summary}}` | 上一组的 plot_progress 输出，第一组为"（本组为开篇，无前情提要）" | "主角进入宗门..." |
| `{{chapters_data}}` | 本组章节的 JSON 数据（chapter_id, title, chapter_summary, key_events 精简版） | JSON 字符串 |
| `{{genre_hint}}` | 体裁提示 | "玄幻·升级流" |
| `{{group_index}}` | 当前组序号（从1开始） | "3" |
| `{{total_groups}}` | 总组数 | "20" |

### Prompt 内容要求

1. 角色设定：你是一位资深网文编辑，擅长分析长篇连载小说的叙事结构
2. 任务说明：基于前情提要和本组章节数据，分析本组的叙事进展
3. 输出要求（严格 JSON）：

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

4. 注意事项：
   - `plot_progress` 必须承接 `{{previous_summary}}`，体现连贯性
   - `new_foreshadowing` 只记录本组**新出现**的伏笔线索，不重复前组已有的
   - `resolved_foreshadowing` 只记录本组**回收**了的伏笔（前组或更早埋下的）
   - `character_arcs` 只记录本组有**明显变化**的角色，没变化的不要列
   - `key_causality` 只记录本组内**最重要的** 1-3 条因果链
   - `tension_level`：1=平淡过渡 2=铺垫蓄力 3=稳步推进 4=高潮迭起 5=核心转折/大高潮
   - 所有文本用中文
   - 不要输出 JSON 以外的内容

### Prompt 结构

```
## 分组叙事摘要（第 {{group_index}} / {{total_groups}} 组）

你是一位资深网文编辑...（角色设定）

### 体裁
{{genre_hint}}

### 前情提要
{{previous_summary}}

### 本组章节数据
{{chapters_data}}

### 输出要求
严格输出 JSON...（格式说明 + 示例 + 注意事项）
```

## 文件 2：`prompts/book_synthesis.md`

### 用途
基于所有分组摘要，生成全书叙事综合分析。

### 模板变量

| 变量 | 说明 |
|------|------|
| `{{group_summaries}}` | 所有 GroupSummary 的 JSON 数组 |
| `{{genre}}` | 体裁分类结果 JSON |
| `{{total_chapters}}` | 总章节数 |
| `{{total_groups}}` | 总组数 |

### Prompt 内容要求

1. 角色设定：你是一位资深网文编辑，正在为一部长篇小说撰写深度叙事分析报告
2. 输入：所有分组摘要的完整数据
3. 输出要求（严格 JSON）：

```json
{
  "title": "推断的书名或'未知书名'",
  "main_plotline": "主线剧情完整概要（200-400字，从开篇到最新进展）",
  "subplot_summary": [
    {"thread": "支线名称", "summary": "支线概要", "status": "active|resolved|abandoned"}
  ],
  "foreshadowing_tracker": [
    {"setup": "伏笔描述", "setup_group": "grp_001", "resolved_group": "grp_003 或 null（未回收）"}
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

4. 注意事项：
   - `main_plotline` 要有完整的起承转合，不是简单拼接各组摘要
   - `foreshadowing_tracker` 要跨组追踪，标记哪些已回收、哪些仍悬而未决
   - `character_arcs` 只列出有**完整弧线**的重要角色（≤10个）
   - `tension_curve` 每组一条，反映全书节奏曲线
   - `quality_notes` 如果发现节奏失衡、支线断裂、伏笔遗忘等问题要指出
   - `subplot_summary` 中 `abandoned` 表示支线被作者遗忘/放弃
   - 所有文本用中文

## 文件 3：`schemas/narrative_summary.schema.json`

对应 `prompts/narrative_summary.md` 的输出格式：

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["plot_progress", "new_foreshadowing", "resolved_foreshadowing", "open_questions", "subplot_threads", "character_arcs", "key_causality", "tension_level"],
  "additionalProperties": false,
  "properties": {
    "plot_progress": {"type": "string", "description": "本组剧情推进概要"},
    "new_foreshadowing": {"type": "array", "items": {"type": "string"}, "description": "本组新埋的伏笔"},
    "resolved_foreshadowing": {"type": "array", "items": {"type": "string"}, "description": "本组回收的伏笔"},
    "open_questions": {"type": "array", "items": {"type": "string"}, "description": "本组遗留悬念"},
    "subplot_threads": {"type": "array", "items": {"type": "string"}, "description": "活跃支线"},
    "character_arcs": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "development"],
        "additionalProperties": false,
        "properties": {
          "name": {"type": "string"},
          "development": {"type": "string"}
        }
      }
    },
    "key_causality": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["cause", "effect"],
        "additionalProperties": false,
        "properties": {
          "cause": {"type": "string"},
          "effect": {"type": "string"}
        }
      }
    },
    "tension_level": {"type": "integer", "minimum": 1, "maximum": 5}
  }
}
```

## 文件 4：`schemas/book_synthesis.schema.json`

对应 `prompts/book_synthesis.md` 的输出格式：

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["title", "main_plotline", "subplot_summary", "foreshadowing_tracker", "character_arcs", "tension_curve", "themes", "open_questions", "quality_notes"],
  "additionalProperties": false,
  "properties": {
    "title": {"type": "string"},
    "main_plotline": {"type": "string"},
    "subplot_summary": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["thread", "summary", "status"],
        "additionalProperties": false,
        "properties": {
          "thread": {"type": "string"},
          "summary": {"type": "string"},
          "status": {"type": "string", "enum": ["active", "resolved", "abandoned"]}
        }
      }
    },
    "foreshadowing_tracker": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["setup", "setup_group"],
        "additionalProperties": false,
        "properties": {
          "setup": {"type": "string"},
          "setup_group": {"type": "string"},
          "resolved_group": {"type": ["string", "null"]}
        }
      }
    },
    "character_arcs": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "arc_summary", "key_moments"],
        "additionalProperties": false,
        "properties": {
          "name": {"type": "string"},
          "arc_summary": {"type": "string"},
          "key_moments": {"type": "array", "items": {"type": "string"}}
        }
      }
    },
    "tension_curve": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["group_id", "level", "reason"],
        "additionalProperties": false,
        "properties": {
          "group_id": {"type": "string"},
          "level": {"type": "integer", "minimum": 1, "maximum": 5},
          "reason": {"type": "string"}
        }
      }
    },
    "themes": {"type": "array", "items": {"type": "string"}},
    "open_questions": {"type": "array", "items": {"type": "string"}},
    "quality_notes": {"type": "array", "items": {"type": "string"}}
  }
}
```

## 验证方法

1. 每个 schema 文件可被 `python -c "import json; json.load(open('schemas/xxx.schema.json'))"` 正确解析
2. 每个 prompt 文件包含所有要求的 `{{变量}}` 占位符
3. Schema 的 required 字段与 prompt 中的输出示例一一对应

## 不要做的事

- ❌ 不要修改任何 .py 文件
- ❌ 不要修改任何 .ts / .tsx 文件
- ❌ 不要修改已有的 prompt 或 schema 文件
- ❌ 不要创建 Python 模块
