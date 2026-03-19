# 任务 2：修复旧流水线重复逻辑、API 稳定性、仓库卫生

## 任务目标

把当前系统里影响维护和稳定性的旧问题修掉，但**不要改产品方向，不要新增新模式**。

你的任务只负责三类内容：

1. `pipeline.py` 中重复逻辑清理
2. `api_server.py` 中旧结果读取与稳定性修复
3. 仓库卫生与忽略规则

---

## 你只可以修改这些文件

- [src/pipeline.py](C:\Users\admin\Desktop\history\src\pipeline.py)
- [src/api_server.py](C:\Users\admin\Desktop\history\src\api_server.py)
- [src/runtime.py](C:\Users\admin\Desktop\history\src\runtime.py)
- [.gitignore](C:\Users\admin\Desktop\history\.gitignore)

如有必要，可新增：

- `docs/fix-notes-*`

---

## 你不可以修改这些文件

- [src/main.py](C:\Users\admin\Desktop\history\src\main.py)
- [src/stages.py](C:\Users\admin\Desktop\history\src\stages.py)
- [src/models.py](C:\Users\admin\Desktop\history\src\models.py)
- [gui/](C:\Users\admin\Desktop\history\gui)

不要新增模式，不要改结果协议。

---

## 具体要做什么

### 1. 清理 `pipeline.py` 重复逻辑

重点关注：

- `run_book`
- `run_book_continue`
- `run_book_resume`

目标不是重写，而是：

- 提炼公共处理函数
- 减少重复的失败处理
- 减少重复的章节结果写盘逻辑
- 减少重复的知识层更新逻辑

要求：

- 不改变现有业务输出含义
- 不新增新模式

### 2. 修复 `api_server.py` 旧接口稳定性

重点处理：

- 结果读取容错
- 空文件或坏文件时的返回行为
- 旧接口中明显不稳定的逻辑

要求：

- 只做稳定性修正
- 不新增新的业务接口

### 3. 仓库卫生治理

处理方向：

- `__pycache__`
- 运行产物
- 不应纳入版本控制的临时文件

目标：

- 让仓库更干净
- 减少误提交

---

## 绝对禁止

- 不要新增 `standard_analysis`
- 不要改 CLI 模式枚举
- 不要改前端
- 不要改章节输出字段结构
- 不要重写整个 `api_server.py`

---

## 验收标准

你交付时必须满足：

1. `pipeline.py` 重复逻辑减少
2. 旧流程输出不发生业务意义变化
3. 旧 API 在异常情况下更稳
4. 仓库忽略规则更合理
5. 没有引入新模式、新接口、新字段

---

## 交付说明

提交时请附一句话说明：

- 提炼了哪些公共逻辑
- 修了哪些 API 稳定性问题
- `.gitignore` 增补了什么
