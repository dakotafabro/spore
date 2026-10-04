#!/usr/bin/env bash
set -euo pipefail

payload="$(cat)"
state_file="${PLUGIN_ROOT:-.}/.session-state"

[ -f "$state_file" ] || exit 0

session_id="$(sed -n '1p' "$state_file")"
repo_root="$(sed -n '2p' "$state_file")"
retrieval_count="$(sed -n '3p' "$state_file")"

command_str="$(printf '%s' "$payload" | sed -n 's/.*"matcher_context":"\([^"]*\)".*/\1/p')"

[ -z "$command_str" ] && exit 0

extract_read_paths() {
  local cmd="$1"
  local repo="$2"

  echo "$cmd" | grep -oE '(cat|head|tail|less|more|bat)\s+[^|;&>]+' 2>/dev/null | while read -r match; do
    echo "$match" | tr ' ' '\n' | tail -n +2 | while read -r arg; do
      case "$arg" in
        -*) continue ;;
        */*|*.md|*.csv|*.yaml|*.yml|*.json|*.txt|*.sh|*.py|*.kt|*.swift|*.ts|*.js)
          local resolved="$arg"
          resolved="${resolved/#\~/$HOME}"
          if [[ "$resolved" == /* ]]; then
            echo "$resolved"
          else
            echo "$repo/$resolved"
          fi
          ;;
      esac
    done
  done
}

paths="$(extract_read_paths "$command_str" "$repo_root" || true)"

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
  esac

  retrieval_count=$((retrieval_count + 1))
  printf '%s,%s,%s,%s\n' "$(date +%Y-%m-%d)" "$session_id" "$relative_path" "hook:shell_read" >> "$retrieval_log"
  logged=$((logged + 1))
done <<< "$paths"

if [ "$logged" -gt 0 ]; then
  sed -i '' "3s/.*/$retrieval_count/" "$state_file"
  printf '📖 [spore] %d retrieval(s) from shell command\n' "$logged" 1>&2
fi
