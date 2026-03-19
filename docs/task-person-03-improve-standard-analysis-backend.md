# 任务 3：新增标准分析模式的后端能力

## 任务目标

新增一个适合商业使用的默认模式，但**不要改 GUI，不要重构旧 API 的展示层**。

你的任务只负责后端新能力：

1. 新增 `standard_analysis` 模式
2. 新增章节级关键事件提取
3. 新增规则打分
4. 让标准模式默认比深度模式更轻

---

## 你只可以修改这些文件

- [src/main.py](C:\Users\admin\Desktop\history\src\main.py)
- [src/models.py](C:\Users\admin\Desktop\history\src\models.py)
- [src/pipeline.py](C:\Users\admin\Desktop\history\src\pipeline.py)
- [src/runtime.py](C:\Users\admin\Desktop\history\src\runtime.py)
- [schemas/](C:\Users\admin\Desktop\history\schemas)
- [prompts/](C:\Users\admin\Desktop\history\prompts)

你可以新增后端文件，例如：

- `src/standard_analysis.py`
- `src/rule_scoring.py`
- `src/standard_analysis_types.py`

---

## 你不可以修改这些文件

- [src/api_server.py](C:\Users\admin\Desktop\history\src\api_server.py)
- [gui/](C:\Users\admin\Desktop\history\gui)
- [README.md](C:\Users\admin\Desktop\history\README.md)
- [docs/deep-analysis-simplification-plan.md](C:\Users\admin\Desktop\history\docs\deep-analysis-simplification-plan.md)

不要做前端，不要改旧页面，不要顺手修旧 API。

---

## 具体要做什么

### 1. 新增 `standard_analysis` 模式

要求：

- CLI 能识别 `standard_analysis`
- 运行时能进入新的后端流程

### 2. 新增章节级关键事件提取

利用已有模型基础：

- [src/models.py](C:\Users\admin\Desktop\history\src\models.py) 中已有 `ChapterKeyEvent`
- [src/models.py](C:\Users\admin\Desktop\history\src\models.py) 中已有 `ChapterKeyEventSet`

你需要把它真正接入流程。

### 3. 新增规则打分

至少能给每章产出：

- `importance_score`
- `importance_reason`

打分优先用规则，不要继续默认走全量 LLM 评分。

### 4. 让标准模式默认更轻

标准模式下不应该默认全量跑：

- `scene_split`
- 全量 `scene_extraction`
- 全量 `causal_analysis`
- 章节级 `episode`

要求：

- 深度模式保留
- 标准模式走更轻的链路

---

## 绝对禁止

- 不要改 GUI
- 不要改旧 API 返回格式
- 不要删除 `deep_analysis`
- 不要重写所有旧逻辑

---

## 验收标准

你交付时必须满足：

1. 后端存在 `standard_analysis` 模式
2. 章节结果能产出关键事件和重要性
3. 标准模式默认调用链明显轻于深度模式
4. 深度模式仍能继续使用
5. 没有改动 GUI 和旧 API 展示逻辑

---

## 交付说明

提交时请附一句话说明：

- 新增了哪些文件
- 标准模式的主要链路是什么
- 相比深度模式减少了哪些默认阶段
