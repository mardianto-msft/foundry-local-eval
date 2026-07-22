#!/usr/bin/env python3
"""Download a Foundry Local model and chat with it interactively."""

from __future__ import annotations

import argparse

import foundry_local_model_utils as model_utils


DEFAULT_MODEL = "phi-4-mini"


def delete_cached_model(model_name: str) -> None:
    model, deleted = model_utils.delete_cached_model(model_name)
    if not deleted:
        print(f"Model '{model.alias}' is not downloaded.")
        return

    print(f"Deleted downloaded model '{model.alias}'.")


def chat(model_name: str, *, streaming: bool = True) -> None:
    model = model_utils.get_model(model_name)
    print(f"Downloading {model.alias} ({model_utils.download_size(model)}) if needed...")
    model_utils.download_model(model)

    print(f"Loading {model.alias}...")
    model.load()

    client = model.get_chat_client()
    # Preserve prior turns so each completion has the full conversation context.
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
            if streaming:
                print("Assistant: ", end="", flush=True)
                # Print each text delta immediately while rebuilding the complete reply.
                answer_parts = []
                for chunk in client.complete_streaming_chat(messages):
                    if not chunk.choices:
                        continue
                    content = chunk.choices[0].delta.content
                    if content:
                        print(content, end="", flush=True)
                        answer_parts.append(content)
                print()
                answer = "".join(answer_parts)
            else:
                response = client.complete_chat(messages)
                answer = response.choices[0].message.content
                print(f"Assistant: {answer}")
            messages.append({"role": "assistant", "content": answer})
    finally:
        # Release native model resources even if input or generation fails.
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
        dest="cached_only",
        action="store_true",
        help="List only downloaded/cached models, then exit.",
    )
    parser.add_argument(
        "--delete-model",
        metavar="MODEL",
        help="Delete a downloaded Foundry Local model from the local cache, then exit.",
    )
    parser.add_argument(
        "--stream",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Stream response text as it is generated. Enabled by default.",
    )
    args = parser.parse_args()

    if args.delete_model:
        delete_cached_model(args.delete_model)
        return

    if args.list_models or args.cached_only:
        model_utils.list_models(cached_only=args.cached_only)
        return

    chat(args.model, streaming=args.stream)


if __name__ == "__main__":
    main()