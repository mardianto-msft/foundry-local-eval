#!/usr/bin/env sh
set -eu

if [ -z "${AZURE_AI_PROJECT_ENDPOINT:-}" ]; then
  printf '%s\n' 'AZURE_AI_PROJECT_ENDPOINT is not set; provisioning outputs were not available.' >&2
  exit 1
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_root=$(dirname "$script_dir")
env_file=${ENV_FILE:-"$project_root/.env"}
temp_file="${env_file}.tmp"

mkdir -p "$(dirname "$env_file")"

if [ -f "$env_file" ]; then
  awk '!/^[[:space:]]*AZURE_AI_PROJECT_ENDPOINT[[:space:]]*=/' "$env_file" > "$temp_file"
else
  : > "$temp_file"
fi

printf 'AZURE_AI_PROJECT_ENDPOINT="%s"\n' "$AZURE_AI_PROJECT_ENDPOINT" >> "$temp_file"
mv "$temp_file" "$env_file"

printf 'Updated %s with AZURE_AI_PROJECT_ENDPOINT.\n' "$env_file"