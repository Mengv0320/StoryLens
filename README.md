# Web Novel Extraction Pipeline

Extract structured story data from Chinese web novels. Python 3.10+, sole external dependency is the `openai` SDK.

Supports OpenAI-compatible and Anthropic-compatible API endpoints. Includes a React/TypeScript GUI frontend and a built-in API server.

## How It Works

The pipeline runs in `standard_analysis` mode:

1. Genre classification (LLM)
2. Chapter splitting (rule-based)
3. Per-chapter key event extraction (LLM)
4. Rule-based importance scoring (weighted event importance + boolean bonuses)

Output per chapter: `chapter_summary`, `key_events[]`, `importance_score` (1-5), `importance_reason`.

## Crawl Mode

Fetch web novels directly from index pages. Supports chapter range selection, encoding override, and JSON export.

## Cache System

- Book-level cache at `data/cache/books/<book_hash>/`
- Cache key: `{book_fingerprint}:{model}:v{pipeline_version}`
- Same book + same model = cache hit across runs
- Prompt/schema/version changes auto-invalidate

## Project Structure

```
src/
  main.py               CLI entry point
  api_server.py          HTTP API server (stdlib ThreadingHTTPServer)
  standard_analysis.py   Standard analysis orchestrator
  stages.py              LLM stage clients (OpenAI / Anthropic / MultiProvider)
  models.py              Dataclasses for pipeline data
  rule_scoring.py        Rule-based importance scoring
  narrative_analyzer.py  Narrative analysis module
  narrative_types.py     Narrative analysis types
  chaptering.py          Chapter splitting from raw text
  config.py              Paths, ModelConfig
  runtime.py             RunPaths, StageCache, RunLogger
  schema_validator.py    JSON Schema validation
  prompt_loader.py       Template loading + rendering
  stats.py               Token usage and cost tracking
  web_crawler.py         Web novel crawling
  book_index.py          Book index management
gui/                     React frontend (TypeScript, Vite)
prompts/                 LLM prompt templates (5 templates)
schemas/                 JSON Schema definitions (6 schemas)
data/                    Runtime data (gitignored)
```

## Usage

### Setup

```bash
cp .env.example .env
# Fill in OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL
```

### CLI -- Standard Analysis

```bash
python -m src.main input.txt --output result.json
python -m src.main input.txt --output result.json --model gpt-4o --use-cache
```

### CLI -- Crawl

```bash
python -m src.main --crawl-url https://example.com/novel/ --output novel.txt
python -m src.main --crawl-url https://example.com/novel/ --chapter-start 1 --chapter-end 50
python -m src.main --crawl-url https://example.com/novel/ --list-chapters
python -m src.main --crawl-url https://example.com/novel/ --crawl-limit 100
python -m src.main --crawl-url https://example.com/novel/ --crawl-json-output chapters.json
python -m src.main --crawl-url https://example.com/novel/ --crawl-encoding gbk
```

### GUI

```bash
python -m src.api_server    # Backend on http://127.0.0.1:8765
cd gui && npm run dev        # Frontend on http://localhost:5173
```

Note: set `NO_PROXY="*"` before starting the API server if you have a system proxy configured, to avoid ProxyError/SSLEOFError.

## Environment Variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Required. API key for the primary provider. |
| `OPENAI_MODEL` | Model name. Default: `gpt-4.1-mini` (CLI) / `gpt-4o` (API server) |
| `OPENAI_BASE_URL` | Base URL for OpenAI-compatible endpoints |
| `OPENAI_TYPE` | `openai` (default) or `anthropic` |
| `USE_ANTHROPIC` | Set to `1` or `true` to use Anthropic API (CLI only) |
| `OPENAI_API_KEY_2` | Secondary provider API key (failover) |
| `OPENAI_BASE_URL_2` | Secondary provider base URL |
| `OPENAI_MODEL_2` | Secondary provider model |
| `OPENAI_TYPE_2` | Secondary provider type: `openai` or `anthropic` |
| `OPENAI_SANITIZE_2` | Set to `1` or `true` to enable sanitization for secondary provider |

## CLI Flags

| Flag | Description |
|---|---|
| `input` | Path to a UTF-8 text file (positional) |
| `--crawl-url URL` | Fetch a novel index page and save merged chapter text |
| `--crawl-limit N` | Only fetch the first N chapters |
| `--crawl-json-output PATH` | JSON output path for crawled chapters |
| `--crawl-encoding ENC` | Fixed response encoding for crawl mode |
| `--list-chapters` | Print chapter list then exit |
| `--chapter-start N` | 1-based starting chapter number |
| `--chapter-end N` | 1-based ending chapter number |
| `--context-before-chapters N` | Prepend N earlier chapters as context |
| `--output PATH` | JSON result path |
| `--model MODEL` | Override model name |
| `--base-url URL` | Override OpenAI-compatible base URL |
| `--use-anthropic` | Use Anthropic API |
| `--model-config JSON` | Per-stage model config JSON |
| `--use-cache` | Enable LLM response caching |
| `--no-cache` | Disable LLM response caching |
| `--project NAME` | Project name for cache namespace |
| `--max-workers N` | Max concurrent workers |

## API Endpoints

Base URL: `http://127.0.0.1:8765`

### POST

| Endpoint | Description |
|---|---|
| `/api/pipeline/start` | Start a pipeline run. Body: `{inputPath, mode, model, projectName, outputDir, useCache}` |

### GET -- Pipeline

| Endpoint | Description |
|---|---|
| `/api/health` | Health check |
| `/api/pipeline/status` | Current pipeline run status |
| `/api/runs` | List previous runs |

### GET -- Results

| Endpoint | Description |
|---|---|
| `/api/results/dashboard` | Dashboard summary (chapter counts, key stages, characters) |
| `/api/results/standard-analysis` | Raw standard analysis JSON |
| `/api/results/chapter-analysis` | Chapter analysis data |
| `/api/results/characters` | Character list with event counts |
| `/api/results/characters/{name}` | Character detail (events, related chapters) |
| `/api/results/timeline` | Timeline of story events |
| `/api/results/failures` | Failed chapters/stages |
| `/api/results/logs` | Pipeline execution logs |
| `/api/results/settings` | Current run settings |
| `/api/results/exports` | Export data |
| `/api/results/narrative` | Narrative analysis data |
| `/api/results/narrative/groups` | Narrative group summaries |
| `/api/results/narrative/synthesis` | Book-level narrative synthesis |

### GET -- Scan (synthesized from standard analysis)

| Endpoint | Description |
|---|---|
| `/api/scan/overview` | Book overview (plotline, key stages, core characters) |
| `/api/scan/segments` | Chapter segments with summaries |
| `/api/scan/segments/{id}` | Single segment detail |
| `/api/scan/key-chapters` | High-importance chapters |
| `/api/scan/reading-guide` | Generated reading guide |
| `/api/scan/chapter-index` | Full chapter index with scores |
| `/api/scan/stats` | Analysis statistics |

### GET -- Books

| Endpoint | Description |
|---|---|
| `/api/books` | List all indexed books |
| `/api/books/{id}` | Book metadata |
| `/api/books/{id}/chapters` | Chapter list for a book |
| `/api/books/{id}/chapters/{chapterId}` | Single chapter detail |
| `/api/books/{id}/analysis/latest` | Latest analysis result for a book |