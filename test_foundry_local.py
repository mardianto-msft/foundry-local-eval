#!/usr/bin/env python3
"""Download a Foundry Local model and chat with it interactively."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Iterable

from foundry_local_sdk import Configuration, FoundryLocalManager


DEFAULT_MODEL = "phi-4-mini"
APP_DATA_DIR = Path(__file__).resolve().parent / ".foundry-local"


def _configuration(app_name: str) -> Configuration:
    return Configuration(app_name=app_name, app_data_dir=str(APP_DATA_DIR))


def _value(model: Any, name: str, default: str = "-") -> str:
    value = getattr(model, name, None)
    if value is None or value == "":
        return default
    return str(value)


def _download_size(model: Any) -> str:
    size_mb = getattr(getattr(model, "info", None), "file_size_mb", None)
    if size_mb is None:
        return "-"
    if size_mb >= 1024:
        return f"{size_mb / 1024:.1f} GB"
    return f"{size_mb} MB"


def _is_cached(model: Any) -> bool:
    value = getattr(model, "is_cached", False)
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes"}
    return bool(value)


def print_models(models: Iterable[Any]) -> None:
    rows = []
    for model in models:
        rows.append(
            (
                _value(model, "alias"),
                _download_size(model),
                _value(model, "capabilities"),
                _value(model, "input_modalities"),
                _value(model, "output_modalities"),
                _value(model, "is_cached"),
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


def list_models(cached_only: bool = False) -> None:
    FoundryLocalManager.initialize(_configuration("foundry-local"))
    models = FoundryLocalManager.instance.catalog.list_models()
    if cached_only:
        models = [model for model in models if _is_cached(model)]
    print_models(models)


def chat(model_name: str) -> None:
    FoundryLocalManager.initialize(_configuration("foundry-local"))
    catalog = FoundryLocalManager.instance.catalog

    model = catalog.get_model(model_name)
    print(f"Downloading {model.alias} ({_download_size(model)}) if needed...")
    model.download()

    print(f"Loading {model.alias}...")
    model.load()

    client = model.get_chat_client()
    messages = []

    print("Enter a prompt. Type 'exit' or 'quit' to stop.")
    try:
        while True:
            prompt = input("You: ").strip()
            if prompt.lower() in {"exit", "quit"}:
                break
            if not prompt:
                continue

            messages.append({"role": "user", "content": prompt})
            response = client.complete_chat(messages)
            answer = response.choices[0].message.content
            print(f"Assistant: {answer}")
            messages.append({"role": "assistant", "content": answer})
    finally:
        print(f"Unloading {model.alias}...")
        model.unload()


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat with a Foundry Local model.")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model alias to download and chat with. Defaults to {DEFAULT_MODEL}.",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available models with download sizes, then exit.",
    )
    parser.add_argument(
        "--cached",
        "--downloaded",
        dest="cached_only",
        action="store_true",
        help="List only downloaded/cached models, then exit.",
    )
    args = parser.parse_args()

    if args.list_models or args.cached_only:
        list_models(cached_only=args.cached_only)
        return

    chat(args.model)


if __name__ == "__main__":
    main()