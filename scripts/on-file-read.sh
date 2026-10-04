#!/usr/bin/env bash
set -euo pipefail

payload="$(cat)"
state_file="${PLUGIN_ROOT:-.}/.session-state"

[ -f "$state_file" ] || exit 0

session_id="$(sed -n '1p' "$state_file")"
repo_root="$(sed -n '2p' "$state_file")"
retrieval_count="$(sed -n '3p' "$state_file")"

file_path="$(printf '%s' "$payload" | sed -n 's/.*"matcher_context":"\([^"]*\)".*/\1/p')"

[ -z "$file_path" ] && exit 0

case "$file_path" in
  "$repo_root"/*) ;;
  *) exit 0 ;;
esac

relative_path="${file_path#$repo_root/}"

case "$relative_path" in
  *INDEX.md) exit 0 ;;
  .retrieval-log.csv|.interoception-log.csv|.trust-state.yaml|.spore.yaml|.proximity-graph.csv|.deposition-log.csv) exit 0 ;;
esac

case "$relative_path" in
  *.md|*.csv|*.yaml|*.yml|*.json|*.txt|*.sh|*.py|*.kt|*.swift|*.ts|*.js) ;;
  *) exit 0 ;;
esac

retrieval_count=$((retrieval_count + 1))
sed -i '' "3s/.*/$retrieval_count/" "$state_file"

retrieval_log="$repo_root/.retrieval-log.csv"
if [ ! -f "$retrieval_log" ]; then
  echo "date,session_id,file,context" > "$retrieval_log"
fi
printf '%s,%s,%s,%s\n' "$(date +%Y-%m-%d)" "$session_id" "$relative_path" "hook:read_file" >> "$retrieval_log"

printf '📖 [spore] retrieval #%d: %s\n' "$retrieval_count" "$relative_path" 1>&2
