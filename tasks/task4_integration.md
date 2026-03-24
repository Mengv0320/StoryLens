# Task 4: 集成收口 — 串行记忆管线 + API 对接

## 目标

将 Task 1（数据层）、Task 2（记忆更新 prompt）、Task 3（章节 prompt 增强）的产出物接入主管线，实现：

1. `standard_analysis.py` 新增记忆模式串行分支
2. `api_server.py` 跨 run 记忆加载 + 角色/关系数据充实
3. 全链路验证闭环

**本任务是最后执行的收口任务，依赖 Task 1/2/3 全部完成。**

## 前置依赖

| 依赖 | 产出物 | 本任务使用 |
|------|--------|-----------|
| Task 1 | `src/story_memory.py` | `StoryMemory`, `format_memory_for_prompt`, `normalize_character_names`, `memory_content_hash` |
| Task 2 | `prompts/memory_update.md` + `schemas/memory_update.schema.json` | prompt 模板 + schema 验证 |
| Task 3 | 修改后的 `prompts/chapter_key_events.md` + `schemas/chapter_key_events.schema.json` + `src/models.py` | `{{story_memory}}` 占位符 + `filler_ratio`/`filler_type` 字段 |

## 涉及文件

| 操作 | 文件 | 说明 |
|------|------|------|
| **修改** | `src/standard_analysis.py` | 核心：串行分支 + 记忆注入/更新循环 |
| **修改** | `src/api_server.py` | 跨 run 记忆加载 + 角色 API 充实 |

## 禁止触碰的文件

- `src/story_memory.py`（Task 1 产出，只 import 使用）
- `prompts/*`（Task 2/3 产出，只读取使用）
- `schemas/*`（Task 2/3 产出，只读取使用）
- `src/models.py`（Task 3 产出，只 import 使用）

---

## Part A: 修改 src/standard_analysis.py

### A-1. 新增 import

```python
from .story_memory import (
    StoryMemory,
    format_memory_for_prompt,
    normalize_character_names,
    memory_content_hash,
)
```

### A-2. ChapterKeyEventExtractor._build_prompt 增加 story_memory_text 参数

**当前签名**：
```python
def _build_prompt(self, chapter_text: str, genre_hint: str) -> str:
```

**改为**：
```python
def _build_prompt(self, chapter_text: str, genre_hint: str, story_memory_text: str = "") -> str:
```

**实现变更**：
```python
def _build_prompt(self, chapter_text: str, genre_hint: str, story_memory_text: str = "") -> str:
    template = load_prompt(self.paths.prompts_dir / "chapter_key_events.md")
    hint_block = f"流派提示：{genre_hint}\n" if genre_hint else ""
    refinement_block = self._REFINEMENT_INSTRUCTIONS.get(self.refinement_intensity, "")
    return render_prompt(
        template,
        genre_hint=hint_block + refinement_block,
        story_memory=story_memory_text,  # ← 新增
        text=chapter_text,
    )
```

### A-3. ChapterKeyEventExtractor.run 增加 story_memory_text 参数

```python
def run(self, chapter_text: str, genre_hint: str = "", story_memory_text: str = "") -> ChapterKeyEventSet:
    prompt = self._build_prompt(chapter_text, genre_hint, story_memory_text)
    result = self._complete_validated(prompt, "chapter_key_events.schema.json")
    events = [ChapterKeyEvent(**e) for e in result.get("events", [])]
    return ChapterKeyEventSet(
        events=events,
        chapter_summary=result.get("chapter_summary", ""),
        filler_ratio=result.get("filler_ratio", 0.0),   # ← 新增
        filler_type=result.get("filler_type", "none"),   # ← 新增
    )
```

### A-4. _process_chapter 增加 memory 相关参数

```python
def _process_chapter(
    chapter_id: str,
    chapter_title: str,
    chapter_text: str,
    extractor: ChapterKeyEventExtractor,
    genre_hint: str,
    cache: StageCache | None,
    stats: PipelineStats | None,
    story_memory_text: str = "",      # ← 新增
    memory_hash: str = "",            # ← 新增
) -> dict[str, Any]:
```

**缓存 key 变更**：
```python
cache_payload = {
    "chapter_text_hash": text_hash,
    "genre": genre_hint,
    "memory_hash": memory_hash,  # ← 新增，空串与旧缓存兼容
}
```

**LLM 调用变更**：
```python
event_set = extractor.run(chapter_text, genre_hint=genre_hint, story_memory_text=story_memory_text)
```

**结果增加新字段**：
```python
result = {
    ...,
    "filler_ratio": event_set.filler_ratio,    # ← 新增
    "filler_type": event_set.filler_type,      # ← 新增
}
```

### A-5. 新增 StoryMemoryUpdater 调用封装

在 `standard_analysis.py` 中新增函数：

```python
def _update_memory(
    memory: StoryMemory,
    chapter_result: dict[str, Any],
    client: LLMClient,
    paths: Paths,
    validator: SchemaValidator,
    stats: PipelineStats | None,
) -> StoryMemory:
    """Call LLM to incrementally update story memory after a chapter extraction."""
    import json as _json
    import time as _time

    template = load_prompt(paths.prompts_dir / "memory_update.md")
    prompt = render_prompt(
        template,
        current_memory=_json.dumps(memory.to_dict(), ensure_ascii=False),
        chapter_id=chapter_result.get("chapter_id", ""),
        chapter_title=chapter_result.get("title", ""),
        chapter_summary=chapter_result.get("chapter_summary", ""),
        chapter_events=_json.dumps(chapter_result.get("key_events", []), ensure_ascii=False),
        genre_hint="",  # genre_hint 已在记忆中体现
    )

    t0 = _time.time()
    raw = client.complete_json(prompt, max_tokens=4096)
    elapsed = _time.time() - t0

    # 验证（宽容模式：验证失败时返回原记忆）
    try:
        validator.validate("memory_update.schema.json", raw)
    except Exception as exc:
        _log.warning("Memory update validation failed for %s: %s",
                     chapter_result.get("chapter_id"), exc)
        # 只更新 meta 字段，保留原记忆内容
        memory.last_chapter_id = chapter_result.get("chapter_id", "")
        memory.last_chapter_title = chapter_result.get("title", "")
        memory.total_chapters_processed += 1
        return memory

    # 统计
    if stats:
        usage = getattr(client, "last_usage", None) or {}
        stats.record_call(
            stage="memory_update",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            duration_seconds=elapsed,
            chapter_id=chapter_result.get("chapter_id", ""),
        )

    return StoryMemory.from_dict(raw)
```

### A-6. run_standard_analysis 新增参数和串行分支

**新签名**：
```python
def run_standard_analysis(
    text: str,
    client: LLMClient,
    cache: StageCache | None = None,
    logger: RunLogger | None = None,
    artifacts_dir: Path | None = None,
    stats: PipelineStats | None = None,
    max_workers: int = 4,
    refinement_intensity: str = "standard",
    # ↓ 新增参数
    enable_story_memory: bool = False,
    initial_memory: StoryMemory | None = None,
) -> dict[str, Any]:
```

**核心逻辑**：在步骤 3（当前的并行提取区域），根据 `enable_story_memory` 选择分支：

```python
if enable_story_memory:
    # ========== 串行记忆分支 ==========
    memory = initial_memory or StoryMemory.empty()

    # 创建 memory snapshots 目录
    if artifacts_dir is not None:
        snapshots_dir = artifacts_dir / "memory_snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)

    for i, ch in enumerate(chapters):
        # 1. 格式化记忆为 prompt 文本
        memory_text = format_memory_for_prompt(memory)
        mem_hash = memory_content_hash(memory)

        # 2. 提取关键事件（注入记忆）
        try:
            ch_result = _process_chapter(
                ch.chapter_id, ch.title, ch.text,
                extractor, genre_hint, cache, stats,
                story_memory_text=memory_text,
                memory_hash=mem_hash,
            )
        except Exception as exc:
            _log.warning("Chapter %s failed: %s", ch.chapter_id, exc)
            ch_result = {
                "chapter_id": ch.chapter_id, "title": ch.title,
                "chapter_summary": "", "key_events": [], "status": "error",
                "importance_score": 0, "importance_reason": "",
                "filler_ratio": 0.0, "filler_type": "none",
            }
            failures.append({"chapter_id": ch.chapter_id, "title": ch.title, "error": str(exc)})
            chapter_results[i] = ch_result
            if chapters_dir is not None:
                write_artifact(chapters_dir / f"{ch.chapter_id}.json", ch_result)
            continue

        # 3. 别名归一化
        if memory.characters:
            ch_result["key_events"] = normalize_character_names(
                ch_result.get("key_events", []), memory,
            )

        # 4. 规则评分
        if ch_result.get("status") == "ok":
            event_objs = [ChapterKeyEvent(**e) for e in ch_result.get("key_events", [])]
            event_set = ChapterKeyEventSet(events=event_objs, chapter_summary=ch_result.get("chapter_summary", ""))
            score_out = score_chapter(event_set)
            ch_result["importance_score"] = score_out["importance_score"]
            ch_result["importance_reason"] = score_out["importance_reason"]
        else:
            ch_result["importance_score"] = 0
            ch_result["importance_reason"] = ""

        chapter_results[i] = ch_result
        if chapters_dir is not None:
            write_artifact(chapters_dir / f"{ch.chapter_id}.json", ch_result)

        # 5. 更新记忆
        if ch_result.get("status") == "ok":
            try:
                memory = _update_memory(memory, ch_result, client, paths, validator, stats)
            except Exception as exc:
                _log.warning("Memory update failed for %s: %s", ch.chapter_id, exc)
                # 记忆更新失败不阻塞管线，继续用旧记忆

        # 6. 保存记忆快照
        if artifacts_dir is not None:
            memory.save(snapshots_dir / f"{ch.chapter_id}_memory.json")

        if logger:
            logger.log("standard_chapter_done_with_memory",
                       chapter_id=ch.chapter_id, chapter_index=i+1,
                       total=len(chapters), memory_chars=len(memory.characters))
else:
    # ========== 原有并行分支（完全不变）==========
    # ... 保持现有 ThreadPoolExecutor 代码 ...
```

**输出 dict 新增 memory 字段**（串行分支时）：
```python
output = {
    "mode": "standard_analysis",
    "genre": asdict(genre_result),
    "chapters": chapter_results,
    "failures": failures,
    "stats": stats.to_dict() if stats else {},
}
if enable_story_memory and memory is not None:
    output["story_memory"] = memory.to_dict()
```

### A-7. 记忆持久化

在函数末尾（return 前），如果启用了记忆：

```python
# 保存最终记忆到 knowledge 目录
if enable_story_memory and artifacts_dir is not None:
    knowledge_dir = artifacts_dir.parent / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    memory.save(knowledge_dir / "story_memory.json")
    if logger:
        logger.log("story_memory_saved",
                   path=str(knowledge_dir / "story_memory.json"),
                   characters=len(memory.characters),
                   relationships=len(memory.relationships))
```

---

## Part B: 修改 src/api_server.py

### B-1. 在 _run_pipeline 方法中加载历史记忆

找到 `_run_pipeline` 方法中调用 `run_standard_analysis` 的位置。在调用之前，增加历史记忆加载逻辑：

```python
# --- 加载历史记忆（跨 run 继承）---
from .story_memory import StoryMemory

prior_memory: StoryMemory | None = None
enable_story_memory = True  # 默认开启记忆模式

# 扫描同项目名的历史 run，找到最新的 story_memory.json
if run_dir is not None:
    project_dir = run_dir.parent  # data/runs/ 或类似
    try:
        existing_runs = sorted(
            [d for d in project_dir.iterdir() if d.is_dir() and d != run_dir],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
        for prev_run in existing_runs:
            mem_path = prev_run / "knowledge" / "story_memory.json"
            if mem_path.exists():
                prior_memory = StoryMemory.load(mem_path)
                if prior_memory.total_chapters_processed > 0:
                    logger.log("loaded_prior_memory",
                               source=str(mem_path),
                               chapters=prior_memory.total_chapters_processed,
                               characters=len(prior_memory.characters))
                    break
                else:
                    prior_memory = None
    except Exception as exc:
        logger.log("prior_memory_load_failed", error=str(exc))
        prior_memory = None
```

**修改 `run_standard_analysis` 调用**：

找到现有调用，增加两个参数：
```python
result = run_standard_analysis(
    text=full_text,
    client=client,
    cache=cache,
    logger=logger,
    artifacts_dir=artifacts_dir,
    stats=stats,
    max_workers=max_workers,
    refinement_intensity=refinement_intensity,
    enable_story_memory=enable_story_memory,       # ← 新增
    initial_memory=prior_memory,                    # ← 新增
)
```

### B-2. 充实角色列表 API（_send_standard_characters）

在 `_send_standard_characters` 方法中，加载 story_memory 来充实角色数据：

```python
def _send_standard_characters(self, mgr: RunManager) -> list[dict]:
    """Synthesize character list from standard_output key_events + story_memory."""
    data = self._load_standard_result(mgr)
    if not data:
        self._send_json([])
        return []

    # 从事件统计角色出现次数（现有逻辑）
    char_events: dict[str, int] = {}
    char_latest: dict[str, str] = {}
    for ch in data.get("chapters", []):
        ch_title = ch.get("title", "")
        for ev in ch.get("key_events", []):
            for c in ev.get("characters", []):
                char_events[c] = char_events.get(c, 0) + 1
                char_latest[c] = ch_title

    # ← 新增：尝试加载 story_memory 充实角色信息
    memory_chars: dict[str, dict] = {}
    mem_path = mgr.run_dir / "knowledge" / "story_memory.json"  # 根据实际路径调整
    if mem_path.exists():
        try:
            from .story_memory import StoryMemory
            memory = StoryMemory.load(mem_path)
            for cp in memory.characters:
                memory_chars[cp.name] = {
                    "faction": cp.faction or None,
                    "aliasCount": len(cp.aliases),
                    "role": cp.role,
                    "power_level": cp.power_level,
                }
        except Exception:
            pass  # 记忆加载失败不影响现有逻辑

    items = []
    for name, count in sorted(char_events.items(), key=lambda x: x[1], reverse=True):
        mc = memory_chars.get(name, {})
        items.append({
            "id": name,
            "name": name,
            "faction": mc.get("faction"),               # ← 从 None 变为实际值
            "aliasCount": mc.get("aliasCount", 0),      # ← 从 0 变为实际值
            "eventCount": count,
            "latestChapterLabel": char_latest.get(name, ""),
        })
    self._send_json(items)
    return items
```

### B-3. 充实角色详情 API（_send_standard_character_detail）

类似地，用 story_memory 填充 identity/faction/currentGoal/relationships：

```python
def _send_standard_character_detail(self, mgr: RunManager, char_id: str) -> None:
    data = self._load_standard_result(mgr)
    if not data:
        self._send_json({"error": "Character not found"}, status=HTTPStatus.NOT_FOUND)
        return

    events: list[str] = []
    related: set[str] = set()
    found = False
    for ch in data.get("chapters", []):
        for ev in ch.get("key_events", []):
            chars = ev.get("characters", [])
            if char_id in chars:
                found = True
                events.append(ev.get("title", ev.get("description", "")))
                for c in chars:
                    if c != char_id:
                        related.add(c)
    if not found:
        self._send_json({"error": "Character not found"}, status=HTTPStatus.NOT_FOUND)
        return

    # ← 新增：从 story_memory 读取角色档案和关系
    aliases = []
    identity = ""
    faction = ""
    current_goal = ""
    description = ""
    rels_from_memory: list[dict] = []

    mem_path = mgr.run_dir / "knowledge" / "story_memory.json"
    if mem_path.exists():
        try:
            from .story_memory import StoryMemory
            memory = StoryMemory.load(mem_path)
            # 查找角色档案
            for cp in memory.characters:
                if cp.name == char_id:
                    aliases = cp.aliases
                    identity = cp.role
                    faction = cp.faction
                    description = cp.summary
                    # current_goal 可从 plot_state 推断，或留空
                    break

            # 查找关系
            for rel in memory.relationships:
                if rel.character_a == char_id:
                    rels_from_memory.append({
                        "targetName": rel.character_b,
                        "relationType": rel.relation_type,
                        "note": rel.description,
                    })
                elif rel.character_b == char_id:
                    rels_from_memory.append({
                        "targetName": rel.character_a,
                        "relationType": rel.relation_type,
                        "note": rel.description,
                    })
        except Exception:
            pass

    # 合并关系：memory 优先，补充 co-occurrence 中未覆盖的
    memory_rel_names = {r["targetName"] for r in rels_from_memory}
    for r_name in list(related)[:10]:
        if r_name not in memory_rel_names:
            rels_from_memory.append({"targetName": r_name, "relationType": "unknown", "note": ""})

    self._send_json({
        "id": char_id,
        "name": char_id,
        "aliases": aliases,                        # ← 从 [] 变为实际值
        "identity": identity,                      # ← 从 "" 变为实际值
        "faction": faction,                        # ← 从 "" 变为实际值
        "currentGoal": current_goal,
        "description": description,                # ← 新增字段
        "recentEvents": events[-20:],
        "relationships": rels_from_memory[:15],    # ← 从 unknown 变为实际类型
    })
```

### B-4. book 级别的角色 API 同样充实

检查 `_send_book_characters` 和 `_send_book_character_detail`（如果存在），应用相同的 memory 充实逻辑。查找 memory 路径时使用 book 对应的最新 run 的 `knowledge/story_memory.json`。

---

## 验证闭环

完成所有修改后，执行以下验证：

### V-1. 导入链完整

```bash
cd /path/to/story
python -c "from src.standard_analysis import run_standard_analysis; print('OK')"
```

### V-2. 默认模式不受影响

```python
# enable_story_memory=False（默认值），走并行分支，与修改前行为一致
result = run_standard_analysis(text=sample, client=client)
assert "story_memory" not in result  # 默认不输出 memory
```

### V-3. 记忆模式 E2E

```python
# 用一段短文本测试完整流程
from src.story_memory import StoryMemory
result = run_standard_analysis(
    text=sample_5_chapters,
    client=client,
    enable_story_memory=True,
    artifacts_dir=Path("test_artifacts"),
)
# 检查输出
assert "story_memory" in result
mem = StoryMemory.from_dict(result["story_memory"])
assert mem.total_chapters_processed > 0
assert len(mem.characters) > 0
# 检查快照文件存在
assert (Path("test_artifacts/memory_snapshots")).exists()
# 检查 knowledge 目录
assert (Path("test_artifacts").parent / "knowledge" / "story_memory.json").exists()
```

### V-4. 跨 Run 继承

```python
# 第二次 run，应该加载第一次的 memory
result2 = run_standard_analysis(
    text=sample_next_5_chapters,
    client=client,
    enable_story_memory=True,
    initial_memory=mem,  # 传入上次的记忆
)
mem2 = StoryMemory.from_dict(result2["story_memory"])
assert mem2.total_chapters_processed > mem.total_chapters_processed
```

### V-5. API 角色数据充实

```bash
# 启动服务后
curl http://localhost:PORT/api/runs/RUNID/characters | python -m json.tool
# 检查 faction 不为 null、aliasCount > 0
curl http://localhost:PORT/api/runs/RUNID/characters/角色名 | python -m json.tool
# 检查 aliases、identity、faction、relationships[].relationType 不全是 unknown
```

### V-6. Grep 确认无遗漏

```bash
# 确认所有 _process_chapter 调用都传入了新参数
grep -n "_process_chapter(" src/standard_analysis.py

# 确认所有 extractor.run 调用都传入了 story_memory_text
grep -n "extractor.run(" src/standard_analysis.py

# 确认 story_memory import 在正确位置
grep -n "story_memory" src/standard_analysis.py src/api_server.py
```

## 编码约束

- 并行分支代码**一行不改**，用 `if enable_story_memory: ... else: ...` 隔离
- 新增参数全部有默认值，不破坏现有调用
- `_update_memory` 失败不阻塞管线（catch + log + 继续用旧记忆）
- API 端的 memory 加载失败不影响现有返回（catch + 空值 fallback）
- 不新增任何 REST endpoint，只充实现有 endpoint 的返回数据
