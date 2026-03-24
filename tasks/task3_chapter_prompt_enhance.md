# Task 3: 章节提取 Prompt 增强 + Schema 扩展

## 目标

增强章节关键事件提取的 prompt 和 schema，使其：
1. 支持注入 `{{story_memory}}` 上下文（向后兼容，空串时等价于当前版本）
2. 引导 LLM 利用已知角色记忆改善提取准确度（对话归因、别名识别、境界理解）
3. 扩展 schema 支持新的可选字段（注水检测、时间标记）
4. 同步更新 `src/models.py` 中的数据类

**本任务只修改 3 个文件，不涉及 story_memory.py（Task 1）、memory_update prompt（Task 2）或管线逻辑（Task 4）。**

## 涉及文件

| 操作 | 文件 | 说明 |
|------|------|------|
| **修改** | `prompts/chapter_key_events.md` | 添加 story_memory 占位符 + 提取增强指令 |
| **修改** | `schemas/chapter_key_events.schema.json` | 新增可选字段 |
| **修改** | `src/models.py` | ChapterKeyEvent 新增对应字段 |

## 禁止触碰的文件

- `src/standard_analysis.py`
- `src/api_server.py`
- `src/story_memory.py`（可能还不存在，不要创建）
- `prompts/memory_update.md`
- `schemas/memory_update.schema.json`
- `src/rule_scoring.py`

---

## 1. 修改 prompts/chapter_key_events.md

### 当前结构（关键部分）

```
... 提取要求 ...
... 布尔标记说明 ...
... anchor_text 说明 ...
... importance 评分 ...
... 输出格式 ...
... Few-Shot ...

{{genre_hint}}

章节文本：
{{text}}
```

### 修改方案

在 `{{genre_hint}}` 和 `章节文本：` 之间插入 `{{story_memory}}` 占位符，并在前面的指令区域增加**记忆利用指导**。

#### 修改 1：在 "### 要求" 之后增加记忆利用段

在 `### 布尔标记说明` **之前**，插入：

```markdown
### 角色记忆利用（如有提供）

如果下方提供了"已知角色档案"，请在提取时：
- **角色识别**：将事件中的角色名归一化到已知角色的主名。如果文中用了"动哥"而档案中主名是"林动"，characters 中填写"林动"
- **对话归因**：根据上下文和已知角色的性格/身份推断对话的说话人，将其列入 characters
- **境界参考**：如果角色有 power_level 记录，在判断"身份变化"类事件的 importance 时参考境界跨度（低阶突破 importance 偏低，高阶突破偏高）
- **关系语境**：根据已知关系判断互动的性质（如已知为敌对关系的两人相遇，更可能是冲突而非结盟）
- 如果没有提供角色档案，正常提取即可，不受影响
```

#### 修改 2：在 `{{genre_hint}}` 后插入 story_memory 区域

```markdown
{{genre_hint}}

{{story_memory}}

章节文本：
{{text}}
```

**向后兼容**：当 `story_memory` 为空串 `""` 时，render_prompt 输出只多一个空行，不影响提取效果。

#### 修改 3：在 JSON 输出格式示例中增加新字段

在现有 `"anchor_text"` 之后，增加：

```json
{
  "events": [
    {
      ... 现有字段 ...,
      "anchor_text": "事件发生位置的原文片段（10-30字）",
      "time_marker": "三天后|当晚|修炼半年后（可选，标记故事内时间节点）"
    }
  ],
  "chapter_summary": "本章一句话概要（30字以内）",
  "filler_ratio": 0.2,
  "filler_type": "none"
}
```

#### 修改 4：在 "### 注意" 区域增加新字段说明

```markdown
- `time_marker`（可选）：如果事件涉及明确的时间跳跃或时间节点（如"三天后"、"半年过去"、"大战当夜"），用原文或简短描述标记。无明确时间信息则省略此字段
- `filler_ratio`：本章注水比例估计（0.0-1.0），0.0=全是干货，1.0=纯注水。评估标准：重复描写、无意义对话、过度环境描写、回忆重述、灌水凑字数
- `filler_type`：注水类型。"none"=无注水（filler_ratio<0.2）, "padding"=凑字数灌水, "recap"=重复回顾旧内容, "worldbuilding"=大段世界观说明, "transition"=过渡章节
```

#### 修改 5：更新 Few-Shot 示例

在现有 Few-Shot 输出示例中加上新字段：

```json
{
  "events": [
    {
      ... 现有字段 ...,
      "time_marker": ""
    }
  ],
  "chapter_summary": "林动在家族测试中展露淬体七重修为，引发震动。",
  "filler_ratio": 0.1,
  "filler_type": "none"
}
```

---

## 2. 修改 schemas/chapter_key_events.schema.json

### 新增事件级字段（在 events.items.properties 中）

```json
"time_marker": {
  "type": "string",
  "description": "故事内时间节点标记（如'三天后'、'大战当夜'），无则空串",
  "default": ""
}
```

**注意**：`time_marker` 不加入 `required`（可选字段），保持向后兼容。

### 新增章节级字段（在顶层 properties 中）

```json
"filler_ratio": {
  "type": "number",
  "minimum": 0,
  "maximum": 1,
  "description": "本章注水比例估计（0.0-1.0）"
},
"filler_type": {
  "type": "string",
  "enum": ["none", "padding", "recap", "worldbuilding", "transition"],
  "description": "注水类型"
}
```

**注意**：`filler_ratio` 和 `filler_type` 加入 `required` 数组（新提取结果必须包含），但旧数据缺失时 Python 端用默认值容错。

更新 `required` 为：
```json
"required": ["events", "chapter_summary", "filler_ratio", "filler_type"]
```

---

## 3. 修改 src/models.py

### ChapterKeyEvent 新增字段

```python
@dataclass
class ChapterKeyEvent:
    """A key event extracted directly at chapter level."""
    event_id: str
    event_type: str
    title: str
    description: str
    characters: list[str] = field(default_factory=list)
    cause: str = ""
    consequence: str = ""
    involves_protagonist: bool = False
    involves_identity_reveal: bool = False
    involves_faction_change: bool = False
    involves_death_or_breakthrough: bool = False
    involves_relationship_change: bool = False
    importance: int = 3
    anchor_text: str = ""
    time_marker: str = ""  # ← 新增：故事内时间标记
```

### ChapterKeyEventSet 新增字段

```python
@dataclass
class ChapterKeyEventSet:
    """Set of key events extracted from a single chapter."""
    events: list[ChapterKeyEvent] = field(default_factory=list)
    chapter_summary: str = ""
    filler_ratio: float = 0.0   # ← 新增：注水比例
    filler_type: str = "none"   # ← 新增：注水类型
```

---

## 向后兼容验证清单

完成修改后，确认以下兼容性：

### ✅ Prompt 兼容

```python
# 当 story_memory="" 时，渲染结果与修改前等价（仅多一个空行）
from src.prompt_loader import load_prompt, render_prompt
template = load_prompt("prompts/chapter_key_events.md")
result = render_prompt(template, genre_hint="玄幻", story_memory="", text="测试文本")
# 检查 result 中不包含 "{{story_memory}}" 占位符残留
assert "{{story_memory}}" not in result
```

### ✅ Schema 兼容

```python
# 旧格式数据仍然能被解析（Python 端容错）
old_event = {"event_id": "evt_001", "event_type": "冲突", "title": "t", "description": "d", "characters": []}
# ChapterKeyEvent(**old_event) 不报错（time_marker 有默认值）
```

### ✅ 新格式数据通过 schema 验证

```python
# 新格式包含 filler_ratio + filler_type
new_result = {
    "events": [],
    "chapter_summary": "测试",
    "filler_ratio": 0.3,
    "filler_type": "padding"
}
validator.validate("chapter_key_events.schema.json", new_result)  # 通过
```

### ✅ 调用方不受影响

用 Grep 搜索以下调用方，确认它们不会因新增字段而报错：
- `src/standard_analysis.py` 中 `ChapterKeyEvent(**e)` — 新字段有默认值 ✅
- `src/standard_analysis.py` 中 `ChapterKeyEventSet(events=..., chapter_summary=...)` — 新字段有默认值 ✅
- `src/rule_scoring.py` 中 `score_chapter(events)` — 不访问新字段 ✅
- `src/api_server.py` 中 `asdict()`/`camelize()` — 新字段会自动带上 ✅

## 编码约束

- `prompts/chapter_key_events.md` 中新增的段落与现有风格一致（中文、markdown 格式）
- `schemas/chapter_key_events.schema.json` 使用 JSON Schema draft 2020-12
- `src/models.py` 新增字段放在末尾，保持有默认值（向后兼容旧数据反序列化）
- 不引入任何新的 import
