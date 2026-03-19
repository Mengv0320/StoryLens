# 任务 4：新增标准分析模式的 API 与前端页面

## 任务目标

把新的标准分析模式变成用户可用页面，但**不要改后端核心流水线，不要修旧系统的通用 bug**。

你的任务只负责：

1. API 层接入 `standard_analysis`
2. 前端任务入口支持新模式
3. 新增标准分析结果展示页面

---

## 你只可以修改这些文件

- [src/api_server.py](C:\Users\admin\Desktop\history\src\api_server.py)
- [gui/src/App.tsx](C:\Users\admin\Desktop\history\gui\src\App.tsx)
- [gui/src/lib/api.ts](C:\Users\admin\Desktop\history\gui\src\lib\api.ts)
- [gui/src/lib/types.ts](C:\Users\admin\Desktop\history\gui\src\lib\types.ts)
- [gui/src/lib/useRunMode.ts](C:\Users\admin\Desktop\history\gui\src\lib\useRunMode.ts)
- [gui/src/pages/TasksPage.tsx](C:\Users\admin\Desktop\history\gui\src\pages\TasksPage.tsx)

你可以新增前端文件，例如：

- `gui/src/pages/ChapterAnalysisPage.tsx`
- `gui/src/components/chapters/*`

---

## 你不可以修改这些文件

- [src/pipeline.py](C:\Users\admin\Desktop\history\src\pipeline.py)
- [src/main.py](C:\Users\admin\Desktop\history\src\main.py)
- [src/stages.py](C:\Users\admin\Desktop\history\src\stages.py)
- [src/models.py](C:\Users\admin\Desktop\history\src\models.py)
- [schemas/](C:\Users\admin\Desktop\history\schemas)
- [prompts/](C:\Users\admin\Desktop\history\prompts)

不要顺手改后端主链路。

---

## 具体要做什么

### 1. API 支持 `standard_analysis`

要求：

- 状态接口能识别新模式
- 结果接口能读取标准分析结果

建议新增清晰的标准分析结果读取逻辑，不要强行复用深度模式结果去拼。

### 2. 任务页支持标准分析

在 [gui/src/pages/TasksPage.tsx](C:\Users\admin\Desktop\history\gui\src\pages\TasksPage.tsx) 中：

- 增加 `standard_analysis` 选项
- 增加模式说明文案

### 3. 新增标准分析页面

建议新增页面展示每章卡片，至少包含：

- 标题
- 章节摘要
- 主线推进
- 重要性分数
- 重要性原因
- 是否可深挖

要求：

- 页面能直接给用户看
- 不需要用户先理解内部 stage

---

## 绝对禁止

- 不要改后端主流水线
- 不要顺手修乱码
- 不要顺手重构整个 API 服务
- 不要改评分规则和 schema

---

## 验收标准

你交付时必须满足：

1. 前端任务入口能选 `standard_analysis`
2. API 能返回标准分析结果
3. 前端有单独的标准分析展示页
4. 页面字段清晰，用户能看懂
5. 没有改动后端核心流水线逻辑

---

## 交付说明

提交时请附一句话说明：

- 新增了哪些页面和组件
- 新增了哪些 API 读取逻辑
- 用户在前端如何进入标准分析结果页
