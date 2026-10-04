#!/usr/bin/env bash
set -euo pipefail

payload="$(cat)"
state_file="${PLUGIN_ROOT:-.}/.session-state"

[ -f "$state_file" ] || exit 0

session_id="$(sed -n '1p' "$state_file")"
repo_root="$(sed -n '2p' "$state_file")"
retrieval_count="$(sed -n '3p' "$state_file")"
tokens_spent="$(sed -n '4p' "$state_file")"
deliverables="$(sed -n '5p' "$state_file")"

tokens_spent="${tokens_spent:-0}"
deliverables="${deliverables:-0}"

if [ "$retrieval_count" -gt 0 ] 2>/dev/null; then
  interoception_log="${repo_root}/.interoception-log.csv"
  if [ -f "$interoception_log" ]; then
    timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf '%s,%s,0,%s,%s,%s,auto,auto:session-end\n' \
      "$timestamp" "$session_id" "$retrieval_count" "$tokens_spent" "$deliverables" \
      >> "$interoception_log"
  fi
fi

printf '🌱 [spore] session %s ended | %d retrievals logged\n' "$session_id" "$retrieval_count" 1>&2

rm -f "$state_file"
