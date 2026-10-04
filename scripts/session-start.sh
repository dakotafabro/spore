#!/usr/bin/env bash
set -euo pipefail

payload="$(cat)"
session_id="$(date +%Y-%m-%d)-$(openssl rand -hex 3 2>/dev/null || printf '%04x' $$)"

plugin_root="${PLUGIN_ROOT:-.}"
config_file="$plugin_root/.spore-env"

if [ -f "$config_file" ]; then
  # shellcheck disable=SC1090
  source "$config_file"
fi

repo_root="${SPORE_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"

state_file="$plugin_root/.session-state"
printf '%s\n' "$session_id" > "$state_file"
printf '%s\n' "$repo_root" >> "$state_file"
printf '0\n' >> "$state_file"
printf '0\n' >> "$state_file"
printf '0\n' >> "$state_file"

retrieval_log="$repo_root/.retrieval-log.csv"
retrieval_count=0
if [ -f "$retrieval_log" ]; then
  retrieval_count=$(($(wc -l < "$retrieval_log") - 1))
  [ "$retrieval_count" -lt 0 ] && retrieval_count=0
fi

printf '{"banner":"  🌱 spore active | call spore_log_retrieval for Code Mode file reads"}\n'
