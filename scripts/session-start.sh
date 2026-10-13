#!/usr/bin/env bash
set -euo pipefail

payload="$(cat)"
# shellcheck source=session-lib.sh
. "$(dirname "$0")/session-lib.sh"

session_id="$(spore_session_id)"
if [ -z "$session_id" ]; then
  session_id="$(date +%Y-%m-%d)-$(openssl rand -hex 3 2>/dev/null || printf '%04x' $$)"
fi

repo_root="$(spore_repo_root)"

mkdir -p "$spore_sessions_dir"
find "$spore_sessions_dir" -type f -mtime +2 -delete 2>/dev/null || true
state_file="$(spore_state_file "$session_id")"
printf '%s\n%s\n0\n' "$session_id" "$repo_root" > "$state_file"

printf '{"banner":"  🌱 spore active | call spore_log_retrieval for Code Mode file reads"}\n'
