#!/usr/bin/env bash
set -euo pipefail

state_file="${PLUGIN_ROOT:-.}/.session-state"
repo_root="${SPORE_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"

if [ ! -f "$state_file" ]; then
  printf '{"error": "no active session"}\n'
  exit 0
fi

session_id="$(sed -n '1p' "$state_file")"
retrieval_count="$(sed -n '3p' "$state_file")"
tokens_spent="$(sed -n '4p' "$state_file")"
deliverables="$(sed -n '5p' "$state_file")"

retrieval_log="$repo_root/.retrieval-log.csv"
total_retrievals=0
if [ -f "$retrieval_log" ]; then
  total_retrievals=$(tail -n +2 "$retrieval_log" | wc -l | tr -d ' ')
fi

printf '{\n'
printf '  "session_id": "%s",\n' "$session_id"
printf '  "retrievals_this_session": %d,\n' "$retrieval_count"
printf '  "tokens_spent_estimate": %d,\n' "$tokens_spent"
printf '  "deliverables_this_session": %d,\n' "$deliverables"
printf '  "total_retrievals_all_time": %d\n' "$total_retrievals"
printf '}\n'
