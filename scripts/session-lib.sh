#!/usr/bin/env bash
# Shared helpers for spore's hooks. Source after reading the payload into
# $payload. Each goose session gets its own state file under
# $PLUGIN_ROOT/.sessions/<session id>, so sessions running side by side
# don't overwrite or merge each other's counts.

spore_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
spore_plugin_root="${PLUGIN_ROOT:-$(dirname "$spore_script_dir")}"
spore_sessions_dir="$spore_plugin_root/.sessions"

payload_field() {
  printf '%s' "$payload" | python3 "$spore_script_dir/hook_payload.py" field "$1" 2>/dev/null || true
}

spore_session_id() {
  local id
  id="$(payload_field session_id)"
  if [ -z "$id" ] && [[ "${AGENT_SESSION_ID:-}" =~ ^[A-Za-z0-9_.-]{1,128}$ ]]; then
    id="$AGENT_SESSION_ID"
  fi
  printf '%s' "$id"
}

spore_state_file() {
  printf '%s/%s' "$spore_sessions_dir" "$1"
}

spore_repo_root() {
  local config_file="$spore_plugin_root/.spore-env"
  if [ -f "$config_file" ]; then
    # shellcheck disable=SC1090
    source "$config_file"
  fi
  printf '%s' "${SPORE_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
}

spore_ensure_state() {
  local state_file
  state_file="$(spore_state_file "$1")"
  if [ ! -f "$state_file" ]; then
    mkdir -p "$spore_sessions_dir"
    printf '%s\n%s\n0\n' "$1" "$(spore_repo_root)" > "$state_file"
  fi
  printf '%s' "$state_file"
}
