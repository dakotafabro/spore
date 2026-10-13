#!/usr/bin/env bash
set -euo pipefail

payload="$(cat)"
# shellcheck source=session-lib.sh
. "$(dirname "$0")/session-lib.sh"

session_id="$(spore_session_id)"
[ -n "$session_id" ] || exit 0
state_file="$(spore_ensure_state "$session_id")"

repo_root="$(sed -n '2p' "$state_file")"
retrieval_count="$(sed -n '3p' "$state_file")"

paths="$(printf '%s' "$payload" | python3 "$spore_script_dir/hook_payload.py" shell-reads 2>/dev/null || true)"
[ -z "$paths" ] && exit 0

retrieval_log="$repo_root/.retrieval-log.csv"
if [ ! -f "$retrieval_log" ]; then
  echo "date,session_id,file,context" > "$retrieval_log"
fi

logged=0
while IFS= read -r file_path; do
  [ -z "$file_path" ] && continue

  case "$file_path" in
    "$repo_root"/*) ;;
    *) continue ;;
  esac

  relative_path="${file_path#$repo_root/}"

  case "$relative_path" in
    *INDEX.md) continue ;;
    .retrieval-log.csv|.interoception-log.csv|.trust-state.yaml|.spore.yaml|.proximity-graph.csv|.deposition-log.csv) continue ;;
    *,*) continue ;;
  esac

  case "$relative_path" in
    *.md|*.csv|*.yaml|*.yml|*.json|*.txt|*.sh|*.py|*.kt|*.swift|*.ts|*.js) ;;
    *) continue ;;
  esac

  retrieval_count=$((retrieval_count + 1))
  printf '%s,%s,%s,%s\n' "$(date +%Y-%m-%d)" "$session_id" "$relative_path" "hook:shell_read" >> "$retrieval_log"
  logged=$((logged + 1))
done <<< "$paths"

if [ "$logged" -gt 0 ]; then
  sed -i '' "3s/.*/$retrieval_count/" "$state_file"
  printf '📖 [spore] %d retrieval(s) from shell command\n' "$logged" 1>&2
fi
