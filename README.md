# Web Novel Extraction Pipeline (网文提取管线)

Dual-mode pipeline for extracting structured story data from Chinese web novels. Python 3.10+, sole external dependency is the `openai` SDK.

Supports OpenAI-compatible and Anthropic-compatible API endpoints. Includes a React/TypeScript GUI frontend and a built-in API server.

## Modes

### fast_scan (default)

9-step pipeline for quick book overviews, designed for long novels (hundreds of chapters):

1. Chapter split
2. Rule-based tagging (keyword matching, importance scoring)
3. Coverage check
4. Segment grouping (~30 chapters/segment)
5. Segment summary (LLM)
6. Key chapter selection (rules + LLM, max 15%)
7. Key chapter summary (LLM)
8. Book overview (LLM)
9. Reading guide (LLM)

Per-item caching: segment summaries and key chapter summaries are cached individually. Failed items can be retried without re-running the whole book.

### deep_analysis

Full 7-stage LLM pipeline:

1. Genre classification
2. Scene splitting
3. Per-scene event extraction
4. Cross-scene event normalization
5. Causal analysis
6. Event scoring
7. Episode summary generation

In book mode: chapter split → per-chapter pipeline → knowledge update → episode planning → episode-level stages.

Cross-chapter state tracked by CausalEngine (foreshadowing/causal chains), KnowledgeManager (characters/factions/world/timeline), and CharacterTracker (cards/relationships).

## Cache System

- Book-level cache at `data/cache/books/<book_hash>/`
- Cache key: `{book_fingerprint}:{model}:v{pipeline_version}`
- Same book + same model = cache hit across runs
- Prompt/schema/version changes auto-invalidate
- Failed items only re-run on retry, successful items reused

## Project Structure

```
src/           Python backend (pipeline, stages, fast_scan modules, API server)
gui/           React frontend (TypeScript, Vite)
prompts/       LLM prompt templates
schemas/       JSON Schema definitions (9 schemas)
data/          Runtime data (gitignored)
  cache/       Book-level model cache
  runs/        Per-run state and artifacts
  raw/         Sample input data
  exports/     Export outputs
docs/          Project documentation
```

## Usage

### Setup

```bash
cp .env.example .env
# Fill in OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL
```

### CLI — Fast Scan (default)

```bash
python -m src.main input.txt --mode fast_scan --output data/processed/output.json
```

### CLI — Deep Analysis

```bash
python -m src.main input.txt --mode book --output data/runs/run_001
python -m src.main input.txt --mode deep_analysis --output data/runs/run_001
```

### CLI — Batch

```bash
python -m src.main --input-dir data/raw/ --glob "*.txt" --mode book --output data/runs/
```

### CLI — Resume

```bash
python -m src.main input.txt --resume data/runs/run_001
```

### CLI — Crawl

```bash
python -m src.main --crawl-url https://example.com/novel/ --output data/raw/novel.txt
python -m src.main --crawl-url https://example.com/novel/ --chapter-start 1 --chapter-end 50 --output data/raw/selection.txt
python -m src.main --crawl-url https://example.com/novel/ --list-chapters
```

### GUI

```bash
python -m src.api_server    # Backend on http://127.0.0.1:8765
cd gui && npm run dev        # Frontend on http://localhost:5173
```

## Environment Variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Required. API key for the primary provider. |
| `OPENAI_MODEL` | Model name. Default: `gpt-4.1-mini` |
| `OPENAI_BASE_URL` | Base URL for OpenAI-compatible endpoints |
| `OPENAI_TYPE` | `openai` (default) or `anthropic` |
| `OPENAI_API_KEY_2` | Secondary provider API key (failover) |
| `OPENAI_BASE_URL_2` | Secondary provider base URL |
| `OPENAI_MODEL_2` | Secondary provider model |
| `OPENAI_TYPE_2` | Secondary provider type: `openai` or `anthropic` |
| `GENRE_MODEL` | Per-stage override: genre classification |
| `EXTRACTION_MODEL` | Per-stage override: scene split + extraction |
| `ANALYSIS_MODEL` | Per-stage override: normalization + scoring |
| `SUMMARY_MODEL` | Per-stage override: episode summary |
| `*_BASE_URL` | Corresponding base URL for each per-stage model |

## Key CLI Flags

| Flag | Description |
|---|---|
| `--mode {excerpt,book,fast_scan,deep_analysis}` | Run mode (`fast_scan` default) |
| `--no-cache` | Disable on-disk caching |
| `--chapters-per-episode N` | Chapter grouping for book/deep_analysis (default: 5) |
| `--split-strategy {v1,v2}` | Episode split: v1 (threshold) or v2 (climax-aware, default) |
| `--skip-quality` | Skip quality assessment |
| `--export-format {json,markdown,csv,api}` | Additional export format |
| `--resume RUN_DIR` | Resume a previous run |
| `--input-dir DIR` | Batch mode: process all files in directory |
| `--glob PATTERN` | File pattern for batch mode (default: `*.txt`) |
| `--crawl-url URL` | Crawl a web novel index page |
| `--chapter-start N` / `--chapter-end N` | Select chapter range for crawl |
| `--list-chapters` | Print chapter list from crawl, then exit |
| `--crawl-encoding ENC` | Force encoding for crawl (e.g. `gbk`) |
| `--price-per-1m-prompt N` | Cost estimation: price per 1M prompt tokens (USD) |
| `--price-per-1m-completion N` | Cost estimation: price per 1M completion tokens (USD) |
