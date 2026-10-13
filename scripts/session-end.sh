#!/usr/bin/env bash
set -euo pipefail

payload="$(cat)"
# shellcheck source=session-lib.sh
. "$(dirname "$0")/session-lib.sh"

session_id="$(spore_session_id)"
[ -n "$session_id" ] || exit 0
state_file="$(spore_state_file "$session_id")"
[ -f "$state_file" ] || exit 0

repo_root="$(sed -n '2p' "$state_file")"
retrieval_count="$(sed -n '3p' "$state_file")"

goose_db="${SPORE_GOOSE_DB:-$HOME/.local/share/goose/sessions/sessions.db}"
tokens_spent=0
if [ -f "$goose_db" ] && command -v sqlite3 >/dev/null; then
  tokens_spent="$(sqlite3 "file:$goose_db?mode=ro" "select coalesce(accumulated_total_tokens, total_tokens, 0) from sessions where id = '$session_id'" 2>/dev/null || true)"
fi
tokens_spent="${tokens_spent:-0}"

deliverables=0
deposition_log="$repo_root/.deposition-log.csv"
if [ -f "$deposition_log" ]; then
  deliverables="$(awk -F, -v id="$session_id" '$2 == id' "$deposition_log" | wc -l | tr -d ' ')"
fi

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
