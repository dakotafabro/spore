#!/usr/bin/env bash
set -euo pipefail

repo_root="${SPORE_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
session_id="${AGENT_SESSION_ID:-}"

if ! [[ "$session_id" =~ ^[A-Za-z0-9_.-]{1,128}$ ]]; then
  printf '{"error": "no session: AGENT_SESSION_ID is not set"}\n'
  exit 0
fi

count_rows() {
  [ -f "$1" ] || { echo 0; return; }
  awk -F, -v id="$session_id" '$2 == id' "$1" | wc -l | tr -d ' '
}

retrieval_log="$repo_root/.retrieval-log.csv"
total_retrievals=0
if [ -f "$retrieval_log" ]; then
  total_retrievals=$(tail -n +2 "$retrieval_log" | wc -l | tr -d ' ')
fi

goose_db="${SPORE_GOOSE_DB:-$HOME/.local/share/goose/sessions/sessions.db}"
tokens_spent=0
if [ -f "$goose_db" ] && command -v sqlite3 >/dev/null; then
  tokens_spent="$(sqlite3 "file:$goose_db?mode=ro" "select coalesce(accumulated_total_tokens, total_tokens, 0) from sessions where id = '$session_id'" 2>/dev/null || true)"
fi

printf '{\n'
printf '  "session_id": "%s",\n' "$session_id"
printf '  "retrievals_this_session": %d,\n' "$(count_rows "$retrieval_log")"
printf '  "tokens_spent_estimate": %d,\n' "${tokens_spent:-0}"
printf '  "deliverables_this_session": %d,\n' "$(count_rows "$repo_root/.deposition-log.csv")"
printf '  "total_retrievals_all_time": %d\n' "$total_retrievals"
printf '}\n'
