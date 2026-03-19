# 任务 A：分层叙事分析引擎（后端核心）

## 目标

新建 `src/narrative_analyzer.py`，实现分层叙事摘要引擎。输入为 standard_analysis 已产出的逐章数据，输出为多层叙事结构（分组摘要 + 全书综合）。

## 约束

- **只新建/修改以下文件**，不碰其他文件：
  - 新建：`src/narrative_analyzer.py`
  - 新建：`src/narrative_types.py`（数据类型定义）
- **不修改** `standard_analysis.py`、`api_server.py`、任何前端文件
- 依赖的外部接口只有 `LLMClient.complete_json(prompt, max_tokens)` 和 `StageCache`（可选）
- Prompt 模板路径硬编码为 `prompts/narrative_summary.md` 和 `prompts/book_synthesis.md`，但**不需要创建这些文件**（任务 B 负责）
- Schema 路径硬编码为 `schemas/narrative_summary.schema.json` 和 `schemas/book_synthesis.schema.json`，但**不需要创建这些文件**（任务 B 负责）

## 输入格式

函数签名：

```python
def run_narrative_analysis(
    chapter_results: list[dict],   # standard_analysis 输出的 chapters 列表
    genre: dict,                   # standard_analysis 输出的 genre 字典
    client: LLMClient,
    paths: Paths,
    validator: SchemaValidator,
    cache: StageCache | None = None,
    logger: RunLogger | None = None,
    stats: PipelineStats | None = None,
    group_size: int = 5,           # 每组章节数
) -> NarrativeResult:
```

每个 `chapter_results[i]` 的结构（已有字段，只读）：

```json
{
  "chapter_id": "ch_001",
  "title": "第一章 标题",
  "chapter_summary": "一句话概要",
  "key_events": [
    {
      "event_id": "evt_001",
      "event_type": "conflict|turning_point|relationship_change|status_change|foreshadowing|payoff",
      "title": "事件标题",
      "description": "事件描述",
      "characters": ["角色A"],
      "cause": "起因",
      "consequence": "结果",
      "importance": 4
    }
  ],
  "importance_score": 4,
  "importance_reason": "含转折点事件",
  "status": "ok"
}
```

## 输出格式

### `NarrativeResult`（定义在 `narrative_types.py`）

```python
@dataclass
class GroupSummary:
    group_id: str                    # "grp_001"
    chapter_range: str               # "第1章 ~ 第5章"
    chapter_ids: list[str]           # ["ch_001", ..., "ch_005"]
    plot_progress: str               # 本组剧情推进概要（100-200字）
    new_foreshadowing: list[str]     # 本组新埋的伏笔
    resolved_foreshadowing: list[str]# 本组回收的伏笔
    open_questions: list[str]        # 本组遗留的悬念
    subplot_threads: list[str]       # 活跃的支线
    character_arcs: list[dict]       # [{"name": "角色", "development": "变化描述"}]
    key_causality: list[dict]        # [{"cause": "因", "effect": "果"}]
    tension_level: int               # 1-5 紧张度

@dataclass
class BookSynthesis:
    title: str                       # 书名/推断书名
    main_plotline: str               # 主线剧情概要（200-400字）
    subplot_summary: list[dict]      # [{"thread": "支线名", "summary": "概要", "status": "active|resolved"}]
    foreshadowing_tracker: list[dict]# [{"setup": "伏笔描述", "setup_group": "grp_001", "resolved_group": "grp_003"|null}]
    character_arcs: list[dict]       # [{"name": "角色", "arc_summary": "完整弧线", "key_moments": ["grp_001:事件"]}]
    tension_curve: list[dict]        # [{"group_id": "grp_001", "level": 3, "reason": "原因"}]
    themes: list[str]                # 核心主题
    open_questions: list[str]        # 全书未解悬念
    quality_notes: list[str]         # 叙事质量备注（节奏问题、断裂等）

@dataclass
class NarrativeResult:
    group_summaries: list[GroupSummary]
    book_synthesis: BookSynthesis
```

## 实现要求

### 第一层：分组摘要（GroupSummary）

1. 将 `chapter_results` 按 `group_size` 分组（最后一组可以不足）
2. 对每组调用 LLM，prompt 使用 `prompts/narrative_summary.md`
3. **滚动上下文**：第 N 组的 prompt 包含第 N-1 组的摘要输出作为"前情提要"（第 1 组无前情）
4. prompt 变量：`{{previous_summary}}`、`{{chapters_data}}`、`{{genre_hint}}`、`{{group_index}}`、`{{total_groups}}`
5. LLM 返回 JSON，用 `schemas/narrative_summary.schema.json` 校验
6. 支持 `StageCache` 缓存（cache key = 组内章节 ID 排序拼接的 hash）
7. 失败的组记录错误但不中断，继续处理下一组

### 第二层：全书综合（BookSynthesis）

1. 收集所有 GroupSummary，拼接为全书上下文
2. 调用 LLM，prompt 使用 `prompts/book_synthesis.md`
3. prompt 变量：`{{group_summaries}}`、`{{genre}}`、`{{total_chapters}}`、`{{total_groups}}`
4. LLM 返回 JSON，用 `schemas/book_synthesis.schema.json` 校验
5. 支持 `StageCache` 缓存

### 并发

- 分组摘要**不能并发**（因为滚动上下文依赖前一组输出）
- 全书综合在所有分组完成后执行

### 错误处理

- 单组失败：记录到 logger，该组 GroupSummary 填充默认值（plot_progress="分析失败"），继续
- 全书综合失败：BookSynthesis 填充默认值，不抛异常
- 所有 LLM 调用通过 `stats.record_call()` 记录

### 可导入接口

```python
# 其他模块只需要这两个
from .narrative_analyzer import run_narrative_analysis
from .narrative_types import NarrativeResult, GroupSummary, BookSynthesis
```

## 已有可用依赖（只读，不修改）

| 模块 | 用途 |
|------|------|
| `src/stages.py` → `LLMClient` | LLM 调用协议 |
| `src/config.py` → `Paths` | 路径发现（prompts_dir, schemas_dir） |
| `src/schema_validator.py` → `SchemaValidator` | JSON Schema 校验 |
| `src/runtime.py` → `StageCache`, `RunLogger` | 缓存 + 日志 |
| `src/stats.py` → `PipelineStats` | 调用统计 |
| `src/prompt_loader.py` → `load_prompt`, `render_prompt` | 模板加载渲染 |

## 验证方法

```python
# 单元测试思路（不需要写测试文件，但实现时确保可测试）
from src.narrative_types import NarrativeResult, GroupSummary, BookSynthesis

# 1. NarrativeResult 可以 dataclasses.asdict() 序列化为 JSON
# 2. run_narrative_analysis() 传入空 chapter_results 返回空 group_summaries + 默认 BookSynthesis
# 3. run_narrative_analysis() 传入 3 章 group_size=5 只产生 1 个 group
# 4. 缓存命中时不调用 LLM
```

## 不要做的事

- ❌ 不要修改 `standard_analysis.py`
- ❌ 不要修改 `api_server.py`
- ❌ 不要创建 prompt 或 schema 文件
- ❌ 不要修改任何前端文件
- ❌ 不要修改 `models.py`（新类型放 `narrative_types.py`）
