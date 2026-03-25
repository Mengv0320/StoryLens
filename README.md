# 📖 StoryLens — 网文智能分析管线

<p align="center">
  <a href="./README.en.md">English</a> | <b>中文</b>
</p>

> 从中文网络小说中自动提取结构化故事数据：章节摘要、关键事件、角色关系、叙事脉络——一键完成。

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![React](https://img.shields.io/badge/React-19-61dafb?logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-5.9-blue?logo=typescript)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 🎯 这是什么？

**StoryLens** 是一个面向中文网络小说的 AI 智能分析工具。

网文动辄几百上千章，读者很难快速把握故事全貌。StoryLens 利用大语言模型（LLM）对小说进行**自动化结构化分析**——从体裁识别、章节切分，到关键事件提取、角色追踪、叙事脉络生成，帮助你在几分钟内理解一本书的核心内容。

无论你是：
- 📖 **网文读者** — 想快速了解一本书值不值得追，或者回顾遗忘的剧情
- 🎬 **内容改编者** — 在做动画/漫画/影视改编前，需要梳理故事结构和角色关系
- 📊 **研究者** — 想对网文的叙事模式、角色关系进行数据化分析
- 🛠️ **开发者** — 想基于结构化的小说数据做二次开发

StoryLens 都能帮到你。

## 💡 为什么选择 StoryLens？

| 优势 | 说明 |
|------|------|
| **一键启动** | 双击 `start.bat` 即可使用，无需复杂配置 |
| **全流程可视化** | 现代 Web GUI，书架→分析→阅读→搜索，所见即所得 |
| **极简依赖** | 后端仅需 `openai` + `requests` 两个包，无重型框架 |
| **模型自由** | 兼容 OpenAI / DeepSeek / Anthropic 等任意 OpenAI 兼容接口，用你最划算的模型 |
| **智能缓存** | 相同章节不重复调用 LLM，省钱省时间 |
| **增量分析** | 小说更新了？只需分析新章节，自动与已有结果合并 |
| **故事记忆** | 跨章节追踪角色、关系和情节线索，分析结果更连贯 |
| **完全本地** | 数据全部存储在本地，不上传任何内容到第三方（除 LLM API 调用） |

## ✨ 功能特性

- **📝 标准分析** — 体裁分类 → 章节切分 → 关键事件提取 → 重要性评分，全流程自动化
- **📊 叙事分析** — 两层叙事分析：分组摘要 + 全书综合，生成完整的故事脉络
- **🧠 故事记忆** — 跨章节角色/关系/情节状态追踪，支持别名归一化
- **🕷️ 网页爬取** — 直接从小说目录页抓取内容，支持章节范围选择、编码设置
- **📚 书架管理** — 多书管理，独立分析，支持增量分析（续接之前的分析）
- **🖥️ Web GUI** — 现代化 React 前端，包含书架、阅读器、角色图谱、时间线等
- **⚡ 智能缓存** — 基于书指纹+模型+管线版本的缓存系统，避免重复 LLM 调用
- **🔌 多 LLM 支持** — 兼容 OpenAI / Anthropic / DeepSeek 等 OpenAI 兼容接口
- **🛑 优雅停止** — 分析过程中随时可停止，已完成的章节结果保留
- **🔄 双提供商容灾** — 支持配置主/备两个 LLM 提供商，自动容灾切换

## 🏗️ 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                     React GUI (Vite + TS)                    │
│  书架 │ 任务中心 │ 分析总览 │ 阅读器 │ 角色 │ 时间线 │ 搜索  │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP API
┌────────────────────────▼────────────────────────────────────┐
│              Python API Server (stdlib HTTP)                 │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌───────────────┐ │
│  │ 书架管理 │ │ 管线调度  │ │ 爬虫引擎 │ │ 静态文件服务  │ │
│  └──────────┘ └─────┬─────┘ └──────────┘ └───────────────┘ │
│                     │                                       │
│  ┌──────────────────▼──────────────────────────────────────┐│
│  │            standard_analysis 管线                        ││
│  │  体裁分类 → 章节切分 → 并行事件提取 → 规则评分          ││
│  │                    ↓                                     ││
│  │           narrative_analyzer                             ││
│  │  分组叙事摘要 → 全书综合分析                              ││
│  └─────────────────────────────────────────────────────────┘│
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────┐ │
│  │ LLM客户端│ │ 缓存系统 │ │ 故事记忆 │ │ Schema校验     │ │
│  └─────────┘ └──────────┘ └──────────┘ └─────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+（仅前端开发需要）
- OpenAI 兼容的 API Key

### 安装

```bash
git clone https://github.com/Mengv0320/StoryLens.git
cd StoryLens

# Python 依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 API Key
```

### 一键启动

```bash
# Windows
start.bat

# Linux/macOS
bash start.sh
```

启动后访问 `http://localhost:8765` 即可使用完整 GUI。

### 开发模式

```bash
# 后端
python -m src.api_server

# 前端（另一个终端）
cd gui && npm install && npm run dev
```

前端开发服务器运行在 `http://localhost:5173`，自动代理 API 请求到后端。

## � 界面预览

| 书架管理 | 阅读器（原文+分析对照） |
|:---:|:---:|
| ![书架](image/1.png) | ![阅读器](image/2.png) |

| 分析总览 | 叙事分析 |
|:---:|:---:|
| ![分析总览](image/3.png) | ![叙事分析](image/4.png) |

| 角色图谱 | 时间线 |
|:---:|:---:|
| ![角色](image/5.png) | ![时间线](image/6.png) |

| 任务中心（爬取+分析） |
|:---:|
| ![任务中心](image/7.png) |

## �📖 使用方式

### CLI — 标准分析

```bash
python -m src.main input.txt --output result.json
python -m src.main input.txt --output result.json --model deepseek-chat --use-cache
```

### CLI — 网页爬取

```bash
# 爬取小说并保存为文本
python -m src.main --crawl-url https://example.com/novel/ --output novel.txt

# 仅爬取前 50 章
python -m src.main --crawl-url https://example.com/novel/ --chapter-start 1 --chapter-end 50

# 查看章节列表
python -m src.main --crawl-url https://example.com/novel/ --list-chapters
```

### GUI 功能

| 页面 | 功能 |
|------|------|
| 📚 书架 | 多书管理，一键分析，删除/清洗 |
| 📋 任务中心 | 启动/停止分析管线，实时进度 |
| 📊 分析总览 | 章节统计、关键角色、故事阶段 |
| 📖 阅读器 | 原文/分析对照阅读 |
| 👥 角色 | 角色列表、详情、事件参与 |
| 🕐 时间线 | 故事事件时间线可视化 |
| 📈 叙事分析 | 分组摘要 + 全书综合叙事 |
| 🔍 搜索 | 全文搜索章节和事件 |
| ⚙️ 设置 | API 配置、模型选择、参数调整 |

## ⚙️ 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `OPENAI_API_KEY` | ✅ | LLM API 密钥 |
| `OPENAI_MODEL` | | 模型名称（默认 `gpt-4o`） |
| `OPENAI_BASE_URL` | | API 地址（支持代理/自部署） |
| `OPENAI_TYPE` | | 提供商类型：`openai`（默认）或 `anthropic` |
| `OPENAI_API_KEY_2` | | 备用提供商密钥 |
| `OPENAI_BASE_URL_2` | | 备用提供商地址 |
| `API_TOKEN` | | API 访问令牌（未设置则免认证） |

## 📂 项目结构

```
src/
  api_server.py          HTTP API 服务器
  standard_analysis.py   标准分析管线
  narrative_analyzer.py  叙事分析模块
  stages.py              LLM 客户端（OpenAI/Anthropic/多提供商）
  story_memory.py        故事记忆系统
  web_crawler.py         网页爬虫
  book_index.py          书架索引管理
  rule_scoring.py        规则化重要性评分
  chaptering.py          章节切分
  main.py                CLI 入口
gui/
  src/pages/             13 个功能页面
  src/components/        UI 组件库
  src/lib/               API 客户端、类型定义、自定义 Hooks
prompts/                 LLM 提示词模板（5 个）
schemas/                 JSON Schema 定义（5 个）
```

## 🔧 技术栈

**后端：** Python 3.10+ · stdlib `http.server` · OpenAI SDK · 多线程并行

**前端：** React 19 · TypeScript 5.9 · Vite 8 · TailwindCSS 3 · Lucide Icons · React Router 7

**依赖极简：** 后端仅依赖 `openai` 和 `requests` 两个包

## 📄 License

[MIT](./LICENSE)
