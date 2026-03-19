# 任务 1：修复编码、文档可读性、评分口径

## 任务目标

把当前项目里最明显的“看起来就不可靠”的问题修掉，但**不要改变产品模式，不要新增功能**。

你的任务只负责三类内容：

1. 中文乱码和文档可读性
2. 评分范围与质量检查口径一致
3. 相关说明文档同步

---

## 你只可以修改这些文件

- [README.md](C:\Users\admin\Desktop\history\README.md)
- [docs/deep-analysis-simplification-plan.md](C:\Users\admin\Desktop\history\docs\deep-analysis-simplification-plan.md)
- [src/quality.py](C:\Users\admin\Desktop\history\src\quality.py)
- [src/stages.py](C:\Users\admin\Desktop\history\src\stages.py)

如果必须补充说明文档，只能新增：

- `docs/fix-notes-*`

---

## 你不可以修改这些文件

- [src/pipeline.py](C:\Users\admin\Desktop\history\src\pipeline.py)
- [src/main.py](C:\Users\admin\Desktop\history\src\main.py)
- [src/api_server.py](C:\Users\admin\Desktop\history\src\api_server.py)
- [gui/](C:\Users\admin\Desktop\history\gui)
- [src/models.py](C:\Users\admin\Desktop\history\src\models.py)

不要新增模式，不要新增接口，不要改前端。

---

## 具体要做什么

### 1. 修复乱码和可读性问题

检查并修复：

- README 中的中文乱码
- 现有 `docs` 中文档中的乱码
- 关键说明文本是否能让普通人看懂

注意：

- 只做可读性修复
- 不要借机改产品定义

### 2. 统一评分口径

重点检查：

- [src/stages.py](C:\Users\admin\Desktop\history\src\stages.py) 中评分范围定义
- [src/quality.py](C:\Users\admin\Desktop\history\src\quality.py) 中质量阈值判断

必须确认：

- 所有评分字段的取值范围一致
- 质量检查使用的阈值和评分体系匹配

### 3. 修正文档说明

如果评分从 `1-5`，那所有文档、提示、校验都要一致。

---

## 绝对禁止

- 不要新增 `standard_analysis`
- 不要重写流水线
- 不要改 API
- 不要碰 GUI
- 不要顺手改缓存逻辑

---

## 验收标准

你交付时必须满足：

1. 关键中文文档能正常阅读
2. README 不再有明显乱码
3. 评分体系说明清晰一致
4. `quality.py` 与 `stages.py` 口径一致
5. 没有引入新模式或新业务字段

---

## 交付说明

提交时请附一句话说明：

- 修了哪些乱码文件
- 评分范围最终是多少
- 质量检查按什么阈值判断
