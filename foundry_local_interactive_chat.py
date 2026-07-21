#!/usr/bin/env python3
"""Download a Foundry Local model and chat with it interactively."""

from __future__ import annotations

import argparse

import foundry_local_model_utils as model_utils


DEFAULT_MODEL = "phi-4-mini"


def chat(model_name: str) -> None:
    model = model_utils.get_model(model_name)
    print(f"Downloading {model.alias} ({model_utils.download_size(model)}) if needed...")
    model_utils.download_model(model)

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
        model_utils.list_models(cached_only=args.cached_only)
        return

    chat(args.model)


if __name__ == "__main__":
    main()