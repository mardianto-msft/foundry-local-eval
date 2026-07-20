#!/usr/bin/env python3
"""Download a Foundry Local model and run a red team scan."""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Optional

WORKSPACE_DIR = Path(__file__).resolve().parent
APP_DATA_DIR = WORKSPACE_DIR / ".foundry-local"
PYRIT_DATA_HOME = WORKSPACE_DIR / ".pyrit-data"
CACHE_HOME = WORKSPACE_DIR / ".cache"
TMP_DIR = WORKSPACE_DIR / ".tmp"
RUN_LOCK_FILE = WORKSPACE_DIR / ".redteam_foundry_local_model.lock"

# Keep model, PyRIT, cache, and temporary data within the workspace.
for directory in (APP_DATA_DIR, PYRIT_DATA_HOME, CACHE_HOME, TMP_DIR):
    directory.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("XDG_DATA_HOME", str(PYRIT_DATA_HOME))
os.environ.setdefault("XDG_CACHE_HOME", str(CACHE_HOME))
os.environ.setdefault("TMPDIR", str(TMP_DIR))

DEFAULT_MODEL = "phi-4-mini"
DEFAULT_MAX_TOKENS = 512
UNUSED_REFUSAL_SCORER_MESSAGE = (
    "refusal_scorer was provided in AttackScoringConfig but is not used. "
    "This parameter will be ignored."
)


class UnusedRefusalScorerFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage() != UNUSED_REFUSAL_SCORER_MESSAGE


def _initialize_foundry_local() -> Any:
    from foundry_local_sdk import Configuration, FoundryLocalManager

    FoundryLocalManager.initialize(
        Configuration(app_name="foundry-local", app_data_dir=str(APP_DATA_DIR))
    )
    return FoundryLocalManager.instance.catalog


def acquire_run_lock() -> Any:
    """Prevent concurrent scans from competing for the local model runtime."""
    lock_file = RUN_LOCK_FILE.open("w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        lock_file.close()
        raise RuntimeError(
            "Another redteam_foundry_local_model.py run is already active. "
            "Stop it before starting a new scan."
        ) from error
    return lock_file


def _download_size(model: Any) -> str:
    size_mb = getattr(getattr(model, "info", None), "file_size_mb", None)
    if size_mb is None:
        return "unknown size"
    if size_mb >= 1024:
        return f"{size_mb / 1024:.1f} GB"
    return f"{size_mb} MB"


def _model_value(model: Any, name: str, default: str = "-") -> str:
    value = getattr(model, name, None)
    if value is None or value == "":
        return default
    return str(value)


def _is_cached(model: Any) -> bool:
    value = getattr(model, "is_cached", False)
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes"}
    return bool(value)


def _format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def _path_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    if path.is_dir():
        return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())
    return 0


def print_models(models: Iterable[Any]) -> None:
    rows = []
    for model in models:
        rows.append(
            (
                _model_value(model, "alias"),
                _download_size(model),
                _model_value(model, "capabilities"),
                _model_value(model, "input_modalities"),
                _model_value(model, "output_modalities"),
                _model_value(model, "is_cached"),
            )
        )

    if not rows:
        print("No models found.")
        return

    headers = ("Alias", "Download Size", "Capabilities", "Input", "Output", "Cached")
    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]

    print("  ".join(header.ljust(width) for header, width in zip(headers, widths)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths)))


def list_models(*, cached_only: bool = False) -> None:
    catalog = _initialize_foundry_local()
    models = catalog.list_models()
    if cached_only:
        models = [model for model in models if _is_cached(model)]
    print_models(models)


class DownloadReporter:
    def __init__(self, model: Any, refresh_seconds: float = 5.0) -> None:
        self._model = model
        self._refresh_seconds = refresh_seconds
        self._percent = 0.0
        self._started_at = time.monotonic()
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._target_path = self._get_model_path()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._render()
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=1.0)
        self._render()
        sys.stdout.write("\n")
        sys.stdout.flush()

    def update_percent(self, percent: float) -> None:
        self._percent = max(0.0, min(100.0, percent))
        self._render()

    def _run(self) -> None:
        while not self._stop_event.wait(self._refresh_seconds):
            self._render()

    def _render(self) -> None:
        elapsed_seconds = int(time.monotonic() - self._started_at)
        parts = [f"Download progress: {self._percent:6.2f}%", f"elapsed: {elapsed_seconds}s"]

        if self._target_path is not None and self._target_path.exists():
            parts.append(f"local size: {_format_bytes(_path_size(self._target_path))}")

        with self._lock:
            sys.stdout.write("\r" + " | ".join(parts))
            sys.stdout.flush()

    def _get_model_path(self) -> Optional[Path]:
        try:
            return Path(self._model.get_path())
        except Exception:
            return None


def download_and_load_model(model_name: str) -> Any:
    """Download the requested Foundry Local model if needed, then load it."""
    catalog = _initialize_foundry_local()

    model = catalog.get_model(model_name)
    print(f"Downloading {model.alias} ({_download_size(model)}) if needed...", flush=True)
    if getattr(model, "is_cached", False):
        print("Model is already downloaded.")
    else:
        reporter = DownloadReporter(model)
        reporter.start()
        try:
            model.download(progress_callback=reporter.update_percent)
        finally:
            reporter.stop()
        print("Download complete.")

    print(f"Loading {model.alias}...", flush=True)
    model.load()
    return model


def create_model_callback(model: Any, *, max_tokens: int, temperature: float):
    """Create the synchronous callback required by RedTeam.scan."""
    client = model.get_chat_client()
    client.settings.max_tokens = max_tokens
    client.settings.temperature = temperature
    # Parallel attacks must serialize access to the shared local chat client.
    completion_lock = threading.Lock()

    def agent_callback(query: str) -> str:
        try:
            with completion_lock:
                response = client.complete_chat([{"role": "user", "content": query}])
            return response.choices[0].message.content
        except Exception as error:
            print(f"Error during model run: {error}")
            return f"I encountered an error and couldn't process your request: {error!s}"

    return agent_callback


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Azure AI Evaluation red teaming against a Foundry Local model."
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Foundry Local model alias to download and scan. Defaults to {DEFAULT_MODEL}.",
    )
    parser.add_argument(
        "--list-model",
        action="store_true",
        help="List available Foundry Local models that can be downloaded, then exit.",
    )
    parser.add_argument(
        "--list-cached-models",
        "--list-downloaded-models",
        dest="list_cached_models",
        action="store_true",
        help="List downloaded/cached Foundry Local models, then exit.",
    )
    parser.add_argument(
        "--output",
        help="Path for the red team results JSON. Defaults to <model>-redteam-results.json.",
    )
    parser.add_argument(
        "--num-objectives",
        type=int,
        default=2,
        help="Number of attack objectives per risk category. Defaults to 2 for a quick scan.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"Maximum tokens for each local model response. Defaults to {DEFAULT_MAX_TOKENS}.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature for local model responses. Defaults to 0.0.",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Allow RedTeam to execute attacks in parallel. Disabled by default for local CPU models.",
    )
    parser.add_argument(
        "--max-parallel-tasks",
        type=int,
        default=1,
        help="Maximum RedTeam parallel tasks when --parallel is used. Defaults to 1.",
    )
    parser.add_argument(
        "--scan-timeout",
        type=int,
        default=7200,
        help="RedTeam scan timeout in seconds. Defaults to 7200.",
    )
    args = parser.parse_args()

    if args.list_model or args.list_cached_models:
        list_models(cached_only=args.list_cached_models)
        return

    # Defer the heavy evaluation imports so model-list commands start quickly.
    import nest_asyncio
    from azure.ai.evaluation.red_team import AttackStrategy, RedTeam, RiskCategory
    from azure.identity import AzureCliCredential
    from dotenv import load_dotenv

    class RedTeamWithoutUnusedRefusalWarning(RedTeam):
        def _setup_logging_filters(self) -> None:
            super()._setup_logging_filters()

            # PyRIT warns for strategies that cannot use the scorer, while Crescendo still uses it.
            for handler in self.logger.handlers:
                if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                    handler.addFilter(UnusedRefusalScorerFilter())

    load_dotenv()
    nest_asyncio.apply()

    output_path = args.output or f"{args.model}-redteam-results.json"

    project_endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
    if not project_endpoint:
        raise RuntimeError("Set AZURE_AI_PROJECT_ENDPOINT before running this script.")

    run_lock = acquire_run_lock()

    print("\n" + "=" * 80)
    print("FOUNDRY LOCAL RED TEAM EVALUATION")
    print("=" * 80 + "\n")

    model = None
    try:
        model = download_and_load_model(args.model)

        risk_categories = [
            RiskCategory.Violence,
            RiskCategory.HateUnfairness,
            RiskCategory.Sexual,
            RiskCategory.SelfHarm,
        ]
        attack_strategies = [
            AttackStrategy.EASY,
            AttackStrategy.MODERATE,
            AttackStrategy.CharacterSpace,
            AttackStrategy.ROT13,
            AttackStrategy.UnicodeConfusable,
            AttackStrategy.CharSwap,
            AttackStrategy.Morse,
            AttackStrategy.Leetspeak,
            AttackStrategy.Url,
            AttackStrategy.Binary,
            AttackStrategy.Compose([AttackStrategy.Base64, AttackStrategy.ROT13]),
        ]

        red_team = RedTeamWithoutUnusedRefusalWarning(
            azure_ai_project=project_endpoint,
            credential=AzureCliCredential(),
            risk_categories=risk_categories,
            num_objectives=args.num_objectives,
        )

        print("Running red team evaluation...")
        print(f"Model: {model.alias}")
        print(f"Attack Objectives per category: {args.num_objectives}")
        print(f"Local response max tokens: {args.max_tokens}")
        print(f"Parallel execution: {args.parallel} (max tasks: {args.max_parallel_tasks})")
        print(f"Output: {output_path}\n")

        results = await red_team.scan(
            target=create_model_callback(
                model,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
            ),
            scan_name=f"{model.alias}-redteam",
            attack_strategies=attack_strategies,
            output_path=output_path,
            parallel_execution=args.parallel,
            max_parallel_tasks=args.max_parallel_tasks,
            timeout=args.scan_timeout,
        )

        print("\n" + "-" * 80)
        print("EVALUATION RESULTS")
        print("-" * 80)
        print(json.dumps(results.to_scorecard(), indent=2))
    finally:
        if model is not None:
            print(f"\nUnloading {model.alias}...")
            model.unload()
        run_lock.close()


if __name__ == "__main__":
    asyncio.run(main())
