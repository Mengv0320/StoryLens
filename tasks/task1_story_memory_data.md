# Task 1: StoryMemory 数据模型层

## 目标

新建 `src/story_memory.py`，提供 StoryMemory 的全部数据结构、序列化、持久化、prompt 格式化、角色别名归一化工具。

**本任务不修改任何已有文件，只新增一个 Python 文件。**

## 涉及文件

| 操作 | 文件 | 说明 |
|------|------|------|
| **新建** | `src/story_memory.py` | 唯一产出物 |

## 禁止触碰的文件

- `src/standard_analysis.py`
- `src/api_server.py`
- `prompts/*`
- `schemas/*`
- `src/models.py`

---

## 数据结构设计

```python
@dataclass
class CharacterProfile:
    name: str                        # 主要名称（归一化后的唯一标识）
    aliases: list[str]               # 别名列表：绰号/称号/代称
    role: str                        # "protagonist" | "antagonist" | "supporting" | "minor"
    faction: str                     # 所属势力/门派，无则 ""
    status: str                      # "alive" | "dead" | "missing" | "unknown"
    power_level: str                 # 当前境界/实力描述，如 "金丹期" "S级猎人"，无体系则 ""
    personality_traits: list[str]    # 性格标签，≤5个
    summary: str                     # 角色一句话概要（≤80字）
    last_seen_chapter: str           # 最后出现的章节 ID

@dataclass
class Relationship:
    character_a: str                 # 归一化主名
    character_b: str                 # 归一化主名
    relation_type: str               # "hostile"|"suspicious"|"allied"|"subordinate"|"mentor"|"family"|"romantic"|"rival"|"unknown"
    description: str                 # 关系描述（≤50字）
    since_chapter: str               # 关系建立/变化的章节 ID

@dataclass
class FactionInfo:
    name: str                        # 势力名称
    description: str                 # 势力简介（≤80字）
    key_members: list[str]           # 核心成员（归一化主名），≤10
    status: str                      # "active"|"disbanded"|"destroyed"|"unknown"

@dataclass
class PlotState:
    current_arc: str                 # 当前主线弧名称（≤30字）
    arc_summary: str                 # 当前弧概要（≤150字）
    active_threads: list[str]        # 活跃支线名称，≤10
    unresolved_foreshadowing: list[str]  # 未回收伏笔，≤15
    recent_events_digest: str        # 最近剧情摘要（≤250字），用于给 LLM 快速回忆

@dataclass
class StoryMemory:
    characters: list[CharacterProfile]   # ≤30
    relationships: list[Relationship]    # ≤40
    factions: list[FactionInfo]          # ≤10
    plot_state: PlotState
    last_chapter_id: str                 # 最后处理的章节 ID
    last_chapter_title: str              # 最后处理的章节标题
    total_chapters_processed: int        # 已处理章节总数
```

## 必须实现的方法/函数

### 1. StoryMemory 序列化

```python
class StoryMemory:
    def to_dict(self) -> dict:
        """转为可 JSON 序列化的 dict，使用 snake_case key。"""

    @classmethod
    def from_dict(cls, data: dict) -> "StoryMemory":
        """从 dict 反序列化，缺失字段用默认值，不抛异常。"""

    def save(self, path: Path) -> None:
        """原子写入 JSON 文件（先写 .tmp 再 rename）。"""

    @classmethod
    def load(cls, path: Path) -> "StoryMemory":
        """从 JSON 文件加载，文件不存在返回 empty()。"""

    @classmethod
    def empty(cls) -> "StoryMemory":
        """返回空白记忆实例。"""
```

**序列化要求**：
- `to_dict()` 使用 `dataclasses.asdict`，但对空列表仍保留 key（不省略）
- `from_dict()` 对任何缺失/多余字段容错，不抛异常
- `save()` 使用 `ensure_ascii=False, indent=2` 写入，先写 `{path}.tmp` 再 `os.replace`
- `load()` 文件不存在或 JSON 损坏时返回 `empty()`

### 2. format_memory_for_prompt(memory: StoryMemory) -> str

将记忆转为可读 markdown 文本，用于注入 LLM prompt。

**输出格式**（示例）：

```markdown
## 已知角色档案

| 角色 | 别名 | 身份 | 势力 | 境界 | 状态 |
|------|------|------|------|------|------|
| 林动 | 动哥, 符祖 | 主角 | 道宗 | 涅槃境 | 存活 |
| 林琅天 | 琅天少主 | 反派 | 元门 | 生死境 | 存活 |

## 主要关系

- 林动 ↔ 绫清竹：romantic — 互有好感但未表白（自第25章）
- 林动 ↔ 林琅天：hostile — 宿敌，多次交手（自第5章）

## 势力格局

- **道宗**（活跃）：林动、青阳掌教 — 正道大派
- **元门**（活跃）：林琅天 — 反派势力

## 剧情状态

**当前主线**：百朝大战
> 各方势力齐聚异魔战场，林动代表道宗参战，正与元门展开决战...

**活跃支线**：祖符寻觅、上古秘辛
**未回收伏笔**：神秘黑影的身份、第三祖符的下落

**最近剧情**：
> 林动在异魔战场击败元门先锋，但遭遇神秘黑影偷袭，青阳掌教受伤...
```

**规则**：
- 空记忆（`total_chapters_processed == 0`）返回空串 `""`
- 角色表只列有 aliases 或 power_level 或 faction 的角色（跳过信息太少的 minor 角色）
- 关系只列 type 不为 "unknown" 的
- 总输出控制在 1500-2500 tokens 以内（约 2000-4000 中文字符）
- 使用 markdown 格式，方便 LLM 理解

### 3. normalize_character_names(events: list[dict], memory: StoryMemory) -> list[dict]

角色别名归一化后处理函数。

```python
def normalize_character_names(
    events: list[dict],
    memory: StoryMemory,
) -> list[dict]:
    """
    将事件列表中 characters 字段的别名统一为主名。

    逻辑：
    1. 从 memory.characters 构建 alias->主名 映射表
    2. 遍历每个 event 的 characters 列表
    3. 如果名字在映射表中，替换为主名
    4. 去重（同一事件中归一化后可能出现重复主名）
    5. 返回新列表（不修改原列表）

    无记忆或空角色列表时原样返回。
    """
```

### 4. memory_content_hash(memory: StoryMemory) -> str

```python
def memory_content_hash(memory: StoryMemory) -> str:
    """
    返回记忆内容的短 hash（sha256 前 16 位），用于缓存 key。
    空记忆返回空串 ""。
    """
```

## 单元测试验证点

实现完成后，用以下方式自测：

```python
# 1. 空记忆序列化往返
m = StoryMemory.empty()
assert m.total_chapters_processed == 0
assert StoryMemory.from_dict(m.to_dict()).total_chapters_processed == 0

# 2. format 空记忆返回空串
assert format_memory_for_prompt(StoryMemory.empty()) == ""

# 3. 别名归一化
m = StoryMemory.empty()
m.characters = [CharacterProfile(name="林动", aliases=["动哥", "符祖"], ...)]
events = [{"characters": ["动哥", "绫清竹"]}]
result = normalize_character_names(events, m)
assert result[0]["characters"] == ["林动", "绫清竹"]  # 动哥 → 林动

# 4. 保存/加载往返
m.save(Path("/tmp/test_mem.json"))
m2 = StoryMemory.load(Path("/tmp/test_mem.json"))
assert m2.to_dict() == m.to_dict()

# 5. content hash 一致性
h1 = memory_content_hash(m)
h2 = memory_content_hash(m)
assert h1 == h2 and len(h1) == 16
```

## 编码约束

- 仅依赖 Python 标准库（`dataclasses`, `json`, `hashlib`, `pathlib`, `os`, `logging`）
- 不引入 `src/` 内其他模块（零耦合）
- 文件头 `from __future__ import annotations`
- 遵循项目既有风格：snake_case、type hints、`_log = logging.getLogger(__name__)`
- 所有 docstring 用英文，注释可中文
