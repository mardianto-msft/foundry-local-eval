"""Shared Foundry Local model catalog and cache operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from foundry_local_sdk import Configuration, FoundryLocalManager


APP_DATA_DIR = Path(__file__).resolve().parent / ".foundry-local"


def initialize_catalog() -> Any:
    """Initialize Foundry Local and return its model catalog."""
    FoundryLocalManager.initialize(
        Configuration(app_name="foundry-local", app_data_dir=str(APP_DATA_DIR))
    )
    return FoundryLocalManager.instance.catalog


def model_value(model: Any, name: str, default: str = "-") -> str:
    value = getattr(model, name, None)
    if value is None or value == "":
        return default
    return str(value)


def download_size(model: Any) -> str:
    size_mb = getattr(getattr(model, "info", None), "file_size_mb", None)
    if size_mb is None:
        return "unknown size"
    if size_mb >= 1024:
        return f"{size_mb / 1024:.1f} GB"
    return f"{size_mb} MB"


def is_cached(model: Any) -> bool:
    value = getattr(model, "is_cached", False)
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes"}
    return bool(value)


def print_models(models: Iterable[Any]) -> None:
    rows = []
    for model in models:
        rows.append(
            (
                model_value(model, "alias"),
                download_size(model),
                model_value(model, "capabilities"),
                model_value(model, "input_modalities"),
                model_value(model, "output_modalities"),
                model_value(model, "is_cached"),
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
    models = initialize_catalog().list_models()
    if cached_only:
        models = [model for model in models if is_cached(model)]
    print_models(models)


def get_model(model_name: str) -> Any:
    model = initialize_catalog().get_model(model_name)
    if model is None:
        raise RuntimeError(f"Model '{model_name}' was not found in the catalog.")
    return model


def download_model(
    model: Any,
    *,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> None:
    """Download a model if needed, optionally reporting percentage progress."""
    model.download(progress_callback=progress_callback)


def delete_cached_model(model_name: str) -> tuple[Any, bool]:
    """Delete a model from the cache and return the model and deletion status."""
    model = get_model(model_name)
    if not is_cached(model):
        return model, False

    model.remove_from_cache()
    return model, True
