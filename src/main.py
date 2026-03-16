from __future__ import annotations

import argparse
import os
from pathlib import Path

from .pipeline import NovelPipeline, save_json, save_jsonl
from .runtime import RunLogger, RunPaths, StageCache
from .stages import OpenAILLMClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the web novel extraction pipeline.")
    parser.add_argument("input", type=Path, help="Path to a UTF-8 text file.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/output.json"),
        help="Where to write the JSON result.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the model name. Defaults to OPENAI_MODEL or gpt-4.1-mini.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Optional environment file with OPENAI_API_KEY and OPENAI_MODEL.",
    )
    parser.add_argument(
        "--mode",
        choices=["excerpt", "book"],
        default="excerpt",
        help="Run a single excerpt or split the full novel into chapters.",
    )
    parser.add_argument(
        "--chapters-per-episode",
        type=int,
        default=5,
        help="Used in book mode to group chapters into episodes.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable on-disk stage cache.",
    )
    return parser.parse_args()


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> None:
    args = parse_args()
    load_env_file(args.env_file)

    text = args.input.read_text(encoding="utf-8")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required. Set it in the environment or .env file.")

    model = args.model or os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    base_url = os.environ.get("OPENAI_BASE_URL")
    run_paths = RunPaths.from_output(args.output)
    run_paths.ensure()
    cache = None if args.no_cache else StageCache(run_paths.cache_dir, namespace=model)
    logger = RunLogger(run_paths.logs_dir / "run.jsonl")

    pipeline = NovelPipeline(
        client=OpenAILLMClient(
            api_key=api_key,
            model=model,
            base_url=base_url,
        ),
        cache=cache,
        logger=logger,
        artifacts_dir=run_paths.artifacts_dir,
    )
    if args.mode == "book":
        result = pipeline.run_book(text, chapters_per_episode=args.chapters_per_episode)
        save_json(result, run_paths.output_dir / "book_output.json")
        save_jsonl(result["chapters"], run_paths.output_dir / "chapters.jsonl")
        save_jsonl(result["episodes"], run_paths.output_dir / "episodes.jsonl")
        save_jsonl(result["episode_plan"], run_paths.output_dir / "episode_plan.jsonl")
        save_jsonl(result["failures"], run_paths.output_dir / "failures.jsonl")
        return

    result = pipeline.run_excerpt(text)
    save_json(result, args.output)


if __name__ == "__main__":
    main()
