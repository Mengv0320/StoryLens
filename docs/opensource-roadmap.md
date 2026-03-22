# 开源发布路线图

> 本文档规划了将 Story Analysis Pipeline 从个人工具转型为可开源发布项目的完整路径。
>
> 最后更新：2026-03-22

---

## 目录

- [项目现状评估](#项目现状评估)
- [开源项目核心目标](#开源项目核心目标)
- [Tier 1：必须做（发布前置条件）](#tier-1必须做发布前置条件)
- [Tier 2：应该做（提升用户与贡献者体验）](#tier-2应该做提升用户与贡献者体验)
- [Tier 3：锦上添花（社区增长加速器）](#tier-3锦上添花社区增长加速器)
- [不需要做的事情](#不需要做的事情)
- [工作量估算与排期](#工作量估算与排期)
- [代码审计修复记录](#代码审计修复记录)

---

## 项目现状评估

### 架构概览

| 组件 | 技术栈 | 说明 |
|------|--------|------|
| 后端 | Python 3.10+ / stdlib `http.server` | 手动路由、ThreadingHTTPServer |
| 前端 | React 19 + TypeScript 5.9 + Vite 8 + Tailwind | SPA，Vite proxy → 后端 |
| LLM | OpenAI + Anthropic 双 Provider | MultiProviderClient 自动 fallback |
| 数据存储 | 文件系统 JSON | `data/` 目录，SHA-256 指纹 |
| 缓存 | 文件缓存 | `data/cache/books/{hash}/` |
| 导出 | EPUB + JSON | `data/exports/` |

### 适配度评估

| 维度 | 现状 | 开源需要 | 差距 |
|------|------|----------|------|
| 一键启动 | 手动 pip + 手动启 server + 手动启前端 | 一条命令跑起来 | 🔴 关键 |
| 文档 | README 有 API 表格 | 安装/配置/使用/贡献指南 | 🟠 重要 |
| 测试覆盖 | **零测试** | 核心逻辑覆盖，PR 能跑 CI | 🔴 关键 |
| CI/CD | **不存在** | GitHub Actions lint + test | 🔴 关键 |
| LICENSE | **不存在** | 开源许可证 | 🔴 关键 |
| 稳定性 | 已完成 62 项 bug 修复 | 基本稳定 | ✅ 已达标 |
| 错误提示 | 部分友好 | 用户能自行排查 | 🟡 中等 |
| 跨平台 | Windows 开发 | Win/Mac/Linux | 🟡 中等 |
| 配置复杂度 | .env 12+ 变量 | 最少配置即可用 | 🟡 中等 |
| Web 框架 | stdlib http.server | 能用但扩展性差 | 🟠 建议升级 |
| 数据存储 | 文件系统 JSON | 开源自用完全 OK | ✅ 无需改 |
| 认证 | 单 Token（可选） | 本地使用足够 | ✅ 无需改 |
| 单线程 pipeline | 一次一本书 | 个人使用可接受 | ✅ 可接受 |
| 前端 polling | 自定义 usePolling | 够用 | ✅ 可接受 |

### 可直接复用的优势

- **业务逻辑成熟**：章节分割、LLM 分析、规则评分、叙事分析管线完整
- **LLM 容错**：指数退避重试、JSON 修复管线、多 Provider 自动 fallback
- **数据安全**：原子写入（tempfile + os.replace）、路径遍历防护、SSRF 防护
- **缓存机制**：SHA-256 指纹 + 模型 + 版本号 → 避免重复 LLM 调用
- **Schema 验证**：自定义 validator 支持 anyOf/oneOf/allOf

---

## 开源项目核心目标

1. **用户能 3 步跑起来** — clone → 配 API key → 启动
2. **贡献者敢改代码** — 有测试保护，CI 自动验证
3. **出错能自己排查** — 错误信息明确，文档覆盖常见场景
4. **代码结构清晰** — 新人能快速理解架构

---

## Tier 1：必须做（发布前置条件）

> 预计工时：**5 天**
>
> 不完成这些，不建议公开发布。

### 1.1 Docker 一键启动

**目标**：用户只需 `docker compose up` 即可启动完整服务。

**文件清单**：

```
Dockerfile              # 后端 Python
gui/Dockerfile          # 前端 build → nginx
docker-compose.yml      # 编排
.dockerignore           # 排除 node_modules、__pycache__ 等
```

**Dockerfile（后端）参考结构**：

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ src/
COPY prompts/ prompts/
COPY schemas/ schemas/
COPY .env.example .env.example
EXPOSE 8765
CMD ["python", "-m", "src.api_server"]
```

**Dockerfile（前端）参考结构**：

```dockerfile
# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY gui/package*.json ./
RUN npm ci
COPY gui/ .
RUN npm run build

# Serve stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

**docker-compose.yml**：

```yaml
services:
  backend:
    build: .
    ports:
      - "8765:8765"
    volumes:
      - ./data:/app/data
    env_file: .env
    restart: unless-stopped

  frontend:
    build:
      context: .
      dockerfile: gui/Dockerfile
    ports:
      - "3000:80"
    depends_on:
      - backend
    restart: unless-stopped
```

**验收标准**：
- [ ] 全新环境 `docker compose up --build` 能启动
- [ ] 前端页面可访问，API 可调通
- [ ] `data/` 目录持久化到宿主机

---

### 1.2 README 完善

**目标**：新用户 5 分钟内理解项目 + 跑起来。

**结构**：

```markdown
# 📖 Story Analysis Pipeline

一句话介绍 + 项目亮点

## ✨ 功能特性
- 功能列表（附截图或 GIF）

## 🚀 快速开始

### 方式一：Docker（推荐）
1. `cp .env.example .env`
2. 编辑 `.env`，填入 `OPENAI_API_KEY=sk-...`
3. `docker compose up`
4. 打开 http://localhost:3000

### 方式二：本地开发
1. Python 3.10+ / Node 20+
2. `pip install -r requirements.txt`
3. `cd gui && npm install && npm run dev`
4. `python -m src.api_server`

## ⚙️ 配置说明
| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| OPENAI_API_KEY | ✅ | - | OpenAI API 密钥 |
| ... | | | |

## 📖 使用指南
- 基本流程截图

## 🤝 贡献指南
- 见 CONTRIBUTING.md

## 📄 License
- MIT / Apache 2.0
```

**验收标准**：
- [ ] 新用户按 README 能跑起来（找人测试）
- [ ] 配置表格覆盖所有环境变量
- [ ] 有至少 1 张截图或 GIF

---

### 1.3 LICENSE 文件

**推荐选择**：

| 许可证 | 特点 | 适合场景 |
|--------|------|----------|
| **MIT** | 最宽松，允许商用、修改、闭源分发 | 想最大化传播 |
| **Apache 2.0** | 宽松 + 专利授权保护 | 企业友好 |
| **GPL 3.0** | 强 copyleft，衍生作品必须开源 | 保护开源 |
| **AGPL 3.0** | 最强 copyleft，SaaS 也必须开源 | 防止别人拿去做闭源 SaaS |

**建议**：如果希望社区活跃、被广泛使用 → **MIT**。如果担心别人拿去闭源商业化 → **AGPL 3.0**。

---

### 1.4 基础测试

**目标**：核心逻辑有测试保护，贡献者提 PR 时 CI 能自动验证。

**测试范围**（只测纯逻辑，不测 LLM 调用）：

```
tests/
├── test_chaptering.py          # 章节分割
│   - 正常分割（有明确章节标题）
│   - 无章节标题（全文作为一章）
│   - 空文本
│   - 超长文本
│
├── test_rule_scoring.py        # 规则评分
│   - 各类事件的评分计算
│   - 边界值（空事件、极端分数）
│
├── test_schema_validator.py    # Schema 验证
│   - 基本类型验证
│   - required 字段检查
│   - anyOf / oneOf / allOf
│   - 嵌套对象
│
├── test_serialization.py       # JSON 修复
│   - 正常 JSON 直接通过
│   - 缺少引号
│   - 多余逗号
│   - 未闭合括号
│   - 提前退出机制
│
├── test_runtime.py             # 运行时工具
│   - 原子写入（正常 + 并发）
│   - compute_book_fingerprint
│   - fingerprint 向后兼容
│
├── test_prompt_loader.py       # Prompt 模板
│   - 正常替换
│   - 未替换占位符检测
│
├── test_api_smoke.py           # API 冒烟测试
│   - GET /api/health → 200
│   - GET /api/books → 200
│   - 认证 Token 验证（有 token vs 无 token）
│   - 路径遍历防护
│
└── fixtures/
    ├── sample_novel.txt        # 测试用小说文本
    ├── sample_schema.json      # 测试用 schema
    └── broken_json_samples.py  # 各种损坏的 JSON 样本
```

**测试工具**：

```
# requirements-dev.txt
pytest>=8.0
pytest-cov>=5.0
httpx>=0.27          # FastAPI/HTTP 测试客户端
```

**不测什么**：
- ❌ LLM 实际调用（成本高、不可复现）
- ❌ 爬虫实际网络请求（外部依赖不可控）
- ❌ 前端 E2E（Tier 2 再考虑）

---

### 1.5 CI/CD（GitHub Actions）

**文件**：`.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: ruff check src/            # lint
      - run: ruff format --check src/   # format check
      - run: python -m pytest tests/ --cov=src --cov-report=term-missing

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: cd gui && npm ci
      - run: cd gui && npm run lint
      - run: cd gui && npx tsc --noEmit
```

**验收标准**：
- [ ] PR 提交后自动跑 CI
- [ ] lint 错误阻断合并
- [ ] 测试失败阻断合并

---

## Tier 2：应该做（提升用户与贡献者体验）

> 预计工时：**5-8 天**
>
> v1.0 发布后逐步完善。

### 2.1 启动脚本 + 前端嵌入

**问题**：当前用户需要分别启动后端和前端，且前端需要 Node.js 环境。

**方案**：后端直接 serve 前端构建产物。

```python
# api_server.py 中添加静态文件服务
# 检测 gui/dist/ 是否存在，存在则 serve
GUI_DIST = Path(__file__).parent.parent / "gui" / "dist"
if GUI_DIST.is_dir():
    # serve 静态文件
    # 所有非 /api/ 路径回退到 index.html（SPA routing）
```

**启动脚本**：

```bash
#!/bin/bash
# start.sh
set -e

# 检查 Python
python3 --version || { echo "需要 Python 3.10+"; exit 1; }

# 安装依赖
pip install -r requirements.txt

# 构建前端（如果 dist 不存在）
if [ ! -d "gui/dist" ]; then
    echo "首次运行，构建前端..."
    cd gui && npm install && npm run build && cd ..
fi

# 启动
echo "启动服务: http://localhost:8765"
python -m src.api_server
```

**收益**：
- 非 Docker 用户也能一键启动
- 不需要 Node.js 运行时（只在构建时需要）
- Release 中附带 pre-built `gui/dist/`，连 npm 都不需要

---

### 2.2 Web 框架升级 → FastAPI（推荐但可选）

**为什么升级**：

| 维度 | http.server | FastAPI |
|------|-------------|---------|
| 自动 API 文档 | ❌ | ✅ `/docs` Swagger UI |
| async 支持 | ❌ | ✅ LLM 调用不阻塞 |
| 请求验证 | 手动 | Pydantic 自动 |
| 中间件 | 手动 | 标准中间件管线 |
| 社区认知 | 无人用 | Python Web 框架 Top 3 |
| 安全性 | 文档明确警告生产不可用 | 生产就绪 |

**迁移策略**：

```python
# 当前 (http.server)
class StoryHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/books":
            books = _book_index.list_books()
            self._send_json(200, books)

# 迁移后 (FastAPI)
from fastapi import FastAPI
app = FastAPI(title="Story Analysis Pipeline")

@app.get("/api/books")
async def list_books():
    return _book_index.list_books()
```

**迁移工作量**：
- 路由结构基本 1:1 映射，约 30 个 endpoint
- CORS、认证改为 FastAPI 中间件
- 预计 3-5 天

**如果不升级**：http.server 在本地单用户场景下也能工作，只是：
- 无自动 API 文档（对开发者 / 贡献者不友好）
- 无 async（LLM 调用时整个 server 阻塞）
- 社区认知度低（贡献者需要学习自定义路由逻辑）

---

### 2.3 配置零门槛化

**目标**：只填一个 API Key 就能用。

**改进方案**：

```
# .env.example 简化

# ====== 必填 ======
OPENAI_API_KEY=sk-your-key-here

# ====== 可选（有合理默认值，无需修改）======
# MODEL=gpt-4o-mini              # 默认模型
# OUTPUT_DIR=data                 # 数据目录
# PORT=8765                       # 服务端口
# API_TOKEN=                      # 留空 = 不启用认证（本地使用推荐）
# USE_ANTHROPIC=false             # 是否使用 Anthropic
# ANTHROPIC_API_KEY=              # Anthropic API Key
# ANTHROPIC_BASE_URL=             # Anthropic 自定义端点
```

**首次启动引导**：

```python
# 如果 .env 不存在且 OPENAI_API_KEY 未设置
if not os.getenv("OPENAI_API_KEY") and not Path(".env").exists():
    print("⚠️  未检测到 API Key 配置")
    print("请执行以下步骤：")
    print("  1. cp .env.example .env")
    print("  2. 编辑 .env，填入 OPENAI_API_KEY")
    print("  3. 重新启动")
    sys.exit(1)
```

---

### 2.4 错误信息友好化

**常见错误场景与期望信息**：

| 场景 | 当前表现 | 期望表现 |
|------|----------|----------|
| API Key 无效 | `openai.AuthenticationError` 堆栈 | `❌ OpenAI API Key 无效。请检查 .env 中的 OPENAI_API_KEY` |
| API Key 未配置 | 启动后调用时才报错 | 启动时立即检测并提示 |
| 网络超时 | `TimeoutError` | `⏱ 连接 OpenAI 超时。请检查网络或设置 OPENAI_BASE_URL 使用代理` |
| Rate Limit | `429 Too Many Requests` | `⚠️ 请求频率超限，自动等待 {N} 秒后重试 ({retry}/{max})` |
| 爬虫被封 | `HTTPError 403` | `🚫 目标网站拒绝访问。建议：等待几分钟后重试，或更换小说源` |
| 端口占用 | `OSError: Address already in use` | `❌ 端口 8765 已被占用。使用 PORT=8766 指定其他端口` |
| 磁盘空间不足 | `OSError: No space left` | `❌ 磁盘空间不足。data/ 目录当前占用 {size}，请清理后重试` |

---

### 2.5 CONTRIBUTING.md

```markdown
# 贡献指南

## 开发环境搭建

1. Fork 并 clone 仓库
2. 安装依赖：
   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   cd gui && npm install
   ```
3. 启动开发环境：
   ```bash
   python -m src.api_server  # 后端
   cd gui && npm run dev     # 前端（另一个终端）
   ```
4. 跑测试：`pytest tests/`

## 代码规范

- Python：ruff 格式化 + 类型注解
- TypeScript：ESLint + Prettier
- 提交信息：`type: description`（如 `fix: 修复章节分割空行问题`）

## PR 流程

1. 从 main 创建 feature 分支
2. 确保 CI 通过（lint + test）
3. 描述清楚改了什么、为什么改
4. 等待 review

## 项目结构

src/
├── api_server.py      # HTTP API 服务
├── main.py            # CLI 入口
├── web_crawler.py     # 网络爬虫
├── chaptering.py      # 章节分割
├── stages.py          # LLM 客户端
├── standard_analysis.py # 标准分析编排
├── narrative_analyzer.py # 叙事分析
├── rule_scoring.py    # 规则评分
├── runtime.py         # 运行时工具（路径、日志、缓存）
├── config.py          # 配置
├── models.py          # 数据模型
└── ...

gui/src/
├── lib/               # 工具函数、API 客户端、类型
├── components/        # UI 组件
├── pages/             # 页面
└── hooks/             # 自定义 hooks
```

---

### 2.6 .gitignore 完善

确保以下内容不被提交：

```gitignore
# 数据与缓存
data/
*.log

# 环境
.env
.env.local
!.env.example

# Python
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/

# Node
node_modules/
gui/dist/

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# Docker
docker-compose.override.yml
```

---

## Tier 3：锦上添花（社区增长加速器）

> 预计工时：**5-10 天**（可按需选做）

### 3.1 Ollama 本地模型支持 ⭐

**为什么重要**：这可能是用户最想要的功能 — 不花钱、不注册、完全本地。

**实现方案**：Ollama 兼容 OpenAI API 格式。

```python
# .env
USE_OLLAMA=true
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5:14b   # 或其他支持中文的模型
```

```python
# stages.py — 复用 OpenAILLMClient，只改 base_url
if os.getenv("USE_OLLAMA"):
    client = OpenAILLMClient(
        api_key="ollama",           # Ollama 不校验 key
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        model=os.getenv("OLLAMA_MODEL", "qwen2.5:14b"),
    )
```

**注意事项**：
- 本地模型 JSON 输出不如 GPT-4 稳定，`repair_json` 会更频繁触发
- 需要在 README 中标注推荐模型和最低配置（如 16GB RAM）

---

### 3.2 更多 LLM Provider 支持

| Provider | 接入难度 | 说明 |
|----------|----------|------|
| Ollama | 低 | OpenAI 兼容 API |
| DeepSeek | 低 | OpenAI 兼容 API |
| 通义千问 | 低 | OpenAI 兼容 API |
| Gemini | 中 | 需要适配器 |
| 本地 llama.cpp | 低 | OpenAI 兼容 server |

**统一接口**：大多数国内模型都兼容 OpenAI API 格式，只需改 `base_url` 和 `model`。

---

### 3.3 GitHub 社区配置

```
.github/
├── ISSUE_TEMPLATE/
│   ├── bug_report.yml          # 结构化 bug 报告
│   └── feature_request.yml     # 功能建议
├── PULL_REQUEST_TEMPLATE.md    # PR 模板
├── FUNDING.yml                 # 赞助链接（可选）
├── CODEOWNERS                  # 代码审查责任人
└── workflows/
    ├── ci.yml                  # 主 CI
    └── release.yml             # 自动发布
```

**Bug 报告模板**（`bug_report.yml`）：

```yaml
name: Bug 报告
description: 提交一个 bug
body:
  - type: textarea
    id: description
    attributes:
      label: 问题描述
      placeholder: 清晰描述遇到的问题
    validations:
      required: true
  - type: textarea
    id: reproduce
    attributes:
      label: 复现步骤
      placeholder: |
        1. 打开 ...
        2. 点击 ...
        3. 出现 ...
  - type: dropdown
    id: deployment
    attributes:
      label: 部署方式
      options:
        - Docker
        - 本地开发
    validations:
      required: true
  - type: textarea
    id: logs
    attributes:
      label: 错误日志
      render: shell
```

---

### 3.4 Release 自动化

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags: ["v*"]

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # 构建前端
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: cd gui && npm ci && npm run build

      # 打包
      - run: tar czf story-pipeline-${{ github.ref_name }}.tar.gz
              src/ prompts/ schemas/ gui/dist/
              requirements.txt .env.example README.md

      # Docker image
      - uses: docker/build-push-action@v5
        with:
          push: true
          tags: ghcr.io/${{ github.repository }}:${{ github.ref_name }}

      # GitHub Release
      - uses: softprops/action-gh-release@v2
        with:
          files: story-pipeline-*.tar.gz
          generate_release_notes: true
```

**用户获取方式**：
- `docker pull ghcr.io/xxx/story-pipeline:v1.0`
- 或下载 Release tar.gz（含 pre-built 前端）

---

### 3.5 国际化（i18n）

**优先级**：如果主要面向中文用户，可暂缓。如果希望国际化传播，需要：

- 前端：`react-i18next`，中/英双语
- 后端 API 错误信息：`Accept-Language` header 切换语言
- README：中英双语或分开两个文件
- Prompt 模板：不同语言的 prompt 变体（影响分析质量）

---

### 3.6 插件 / 扩展机制（远期）

```
~/.story-pipeline/
├── prompts/          # 用户自定义 prompt 覆盖默认
├── rules/            # 自定义评分规则
└── crawlers/         # 自定义爬虫源
```

- 项目内置 prompt 为默认值，用户目录下的同名文件覆盖
- 评分规则支持 YAML 配置
- 爬虫源支持注册机制

---

## 不需要做的事情

以下是**商业 SaaS 需要但开源项目不需要**的：

| 不需要 | 原因 |
|--------|------|
| ❌ PostgreSQL / 数据库 | 文件系统对单用户完全够用，用户不需要装数据库 |
| ❌ Celery / Redis / 任务队列 | 单用户一次跑一本书，daemon thread 够用 |
| ❌ 用户注册 / 多租户 | 本地部署，不需要用户系统 |
| ❌ RBAC 权限模型 | 单用户，不需要角色权限 |
| ❌ 计费 / 支付 | 开源免费 |
| ❌ Kubernetes | Docker Compose 足矣 |
| ❌ Prometheus / Grafana | 文件日志对单用户够用 |
| ❌ 分布式追踪 | 单进程，不需要 |
| ❌ API 网关 | 本地直连 |
| ❌ CDN | 本地 serve 静态文件 |

---

## 工作量估算与排期

### Tier 1（发布前必须完成）

| 任务 | 工时 | 依赖 |
|------|------|------|
| 1.1 Dockerfile + compose | 1 天 | 无 |
| 1.2 README 完善 | 1 天 | 无 |
| 1.3 LICENSE 选择 | 0.5 天 | 无 |
| 1.4 基础测试 | 2 天 | 无 |
| 1.5 CI/CD（GitHub Actions） | 0.5 天 | 1.4 |
| **Tier 1 合计** | **~5 天** | |

### Tier 2（v1.1 ~ v1.2）

| 任务 | 工时 | 依赖 |
|------|------|------|
| 2.1 启动脚本 + 前端嵌入 | 1 天 | 无 |
| 2.2 FastAPI 迁移 | 3-5 天 | 无 |
| 2.3 配置零门槛化 | 0.5 天 | 无 |
| 2.4 错误信息友好化 | 1 天 | 无 |
| 2.5 CONTRIBUTING.md | 0.5 天 | 无 |
| 2.6 .gitignore 完善 | 0.5 天 | 无 |
| **Tier 2 合计** | **~7-9 天** | |

### Tier 3（v1.x ~ v2.0）

| 任务 | 工时 | 依赖 |
|------|------|------|
| 3.1 Ollama 支持 | 1-2 天 | 无 |
| 3.2 更多 LLM Provider | 1-2 天 | 无 |
| 3.3 GitHub 社区配置 | 0.5 天 | 无 |
| 3.4 Release 自动化 | 0.5 天 | 1.5 |
| 3.5 国际化 | 3-5 天 | 无 |
| 3.6 插件机制 | 3-5 天 | 无 |
| **Tier 3 合计** | **~10-15 天** | |

### 建议发布节奏

```
v0.9  — Tier 1 完成，内部测试
v1.0  — 正式开源发布
v1.1  — Tier 2 完成（FastAPI + 启动简化）
v1.2  — Ollama 支持
v1.3  — 更多 LLM Provider + 社区反馈修复
v2.0  — 插件系统 + 国际化（如果社区有需求）
```

---

## 代码审计修复记录

> 2026-03-22 完成的全量审计与修复，已合并到代码中。

### P0 安全修复（8 项）

| 文件 | 修复内容 |
|------|----------|
| `src/api_server.py` | `_check_auth()` 实现 Bearer Token 验证 |
| `src/api_server.py` | `/api/crawl/export` 添加 `output_dir` 路径校验 |
| `src/api_server.py` | `shutil.rmtree` 前添加路径验证 |
| `src/api_server.py` | `except Exception:` → `except Exception as e:` |
| `src/api_server.py` | API Token 日志掩码化 |
| `src/api_server.py` | CORS 添加 DELETE 方法 |
| `src/main.py` | 修复 3 处致命错误（base_url / from_output / logs_dir） |
| `src/web_crawler.py` | SSRF DNS Pinning + response 大小限制 + validate_url 全覆盖 + 速率限制 |

### P1 核心修复（12 项）

| 文件 | 修复内容 |
|------|----------|
| `src/stages.py` | API Key 不存实例属性 / fallback 异常日志 / JSON 管道文档化 |
| `src/runtime.py` | 原子写入 / SHA-256[:32] 128bit / RunLogger 线程锁 |
| `src/standard_analysis.py` | SHA-256 缓存键 / 独立 dict 推导 / duration 计时 |
| `src/narrative_analyzer.py` | client.last_usage token 统计 / schema 失败处理 / _safe_int |
| `src/serialization.py` | repair_json 循环 200→20 / 针对性策略 / 提前退出 |
| `src/schema_validator.py` | anyOf / oneOf / allOf 支持 |
| `gui/src/lib/api.ts` | Authorization header / getJson export / 30s 超时 |
| `gui/src/lib/usePolling.ts` | 递归 setTimeout / AbortController / 保留数据 |

### P2 质量修复（20 项）

| 文件 | 修复内容 |
|------|----------|
| `src/book_index.py` | 子目录 mtime 刷新 / 快速章节计数 |
| `src/book_types.py` | to_dict() 移除 latestRunDir 泄露 |
| `src/stats.py` | 移除不必要的 __new__ 模式 |
| `src/prompt_loader.py` | 未替换占位符检测 |
| `src/chaptering.py` | 章节文本剥离标题行 |
| `gui/src/lib/types.ts` | 9 处前后端类型对齐 |
| `gui/src/lib/useActiveBook.ts` | globalThis HMR 安全 |
| `gui/src/lib/useSessionState.ts` | JSON.parse try-catch + validate |
| `gui/src/hooks/useSearchState.ts` | AbortSignal 正确传递 |
| `gui/src/components/shell/TopBar.tsx` | length>0 / EPUB 认证下载 |
| `gui/src/components/tasks/CrawlWorkflow.tsx` | URL 校验 / 章节范围校验 |
| `gui/src/pages/NarrativePage.tsx` | 11 处 key={index} 替换 |
| `gui/src/pages/BookDetailPage.tsx` | 章节列表 max-h-600px 滚动 |
| `gui/src/pages/ReaderComparePage.tsx` | 3 处空 catch 补错误处理 |
| `gui/src/components/feedback/FeedbackButton.tsx` | Esc / focus / setTimeout 清理 |
| `gui/src/components/ErrorBoundary.tsx` | PageErrorBoundary 可复用组件 |

### P3 清理修复（9 项）

| 操作 | 内容 |
|------|------|
| 删除 | `src/feedback_store.py`（死代码） |
| 删除 | `src/search_index.py`（死代码） |
| 删除 | `gui/src/components/shell/RightInfoPanel.tsx`（死代码） |
| 删除 | `schemas/episode_summary.schema.json`（死代码） |
| 删除 | `schemas/event_scores.schema.json`（死代码） |
| 删除 | `prompts/event_type_taxonomy.md`（死代码） |
| 修复 | `schemas/chapter_key_events.schema.json` 补 required |
| 修复 | `requirements.txt` 版本约束 |
| 修复 | `.env.example` 补全缺失变量 |
