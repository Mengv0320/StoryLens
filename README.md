# Web Novel Extraction MVP

This workspace now contains the minimum structure for a novel-to-episode extraction pipeline:

- `prompts/`: prompt banks and taxonomies
- `schemas/`: JSON schemas for major outputs
- `src/`: a Python skeleton for genre classification, event extraction, scoring, and episode building
- `data/examples/`: sample input text

## Current Status

The pipeline now includes a concrete OpenAI-compatible adapter for the locally installed `openai` package.

- `src/stages.py` defines `LLMClient`
- `OpenAILLMClient` uses `chat.completions.create()` with JSON output, which is friendlier to OpenAI-compatible gateways such as iFlow
- `src/schema_validator.py` performs local shape validation without extra dependencies
- you can still replace it with Anthropic or a local model adapter later

## Files

- `prompts/novel_genre_taxonomy.md`
- `prompts/event_type_taxonomy.md`
- `prompts/webnovel_prompts.md`
- `schemas/genre_classification.schema.json`
- `schemas/scene_split.schema.json`
- `schemas/extracted_events.schema.json`
- `schemas/normalized_events.schema.json`
- `schemas/event_scores.schema.json`
- `schemas/episode_summary.schema.json`
- `src/pipeline.py`
- `src/schema_validator.py`
- `.env.example`
- `data/examples/sample_excerpt.txt`

## Usage

Copy `.env.example` to `.env` and fill in your API key.

Then run:

```bash
python -m src.main data/examples/sample_excerpt.txt --output data/processed/output.json
```

Optional flags:

```bash
python -m src.main data/examples/sample_excerpt.txt --model gpt-4.1-mini
python -m src.main data/examples/sample_excerpt.txt --env-file .env
python -m src.main novel.txt --mode book --output data/runs/run_001 --chapters-per-episode 5
python -m src.main novel.txt --mode book --output data/runs/run_001 --no-cache
```

Environment variables:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_BASE_URL`

For iFlow, a typical setup is:

```env
OPENAI_API_KEY=...
OPENAI_MODEL=qwen3-max
OPENAI_BASE_URL=https://apis.iflow.cn/v1
```

## Next Step

The pipeline now runs:

1. genre classification
2. scene splitting
3. per-scene event extraction
4. cross-scene event normalization
5. event scoring
6. episode summary generation

For batch runs, the CLI now writes:

- `cache/`: per-stage reusable results
- `artifacts/chapters/`: per-chapter intermediate outputs
- `artifacts/episodes/`: per-episode intermediate outputs
- `artifacts/failures/`: failed chapter or episode records
- `artifacts/aliases.json`: accumulated character alias memory
- `artifacts/episode_plan.json`: anime-style episode planning table
- `logs/run.jsonl`: append-only stage log

This makes reruns much cheaper and lets you resume long jobs without recomputing finished stages.

Book mode now uses chapter boundaries plus high `climax/suspense` chapters as soft cut points, instead of blindly grouping every fixed `N` chapters into one episode.
