#!/usr/bin/env bash
set -euo pipefail

repo_root="${SPORE_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
config_file="$repo_root/.spore.yaml"
retrieval_log="$repo_root/.retrieval-log.csv"

if [ -f "$config_file" ]; then
  lambda="${SPORE_DECAY_RATE:-$(grep 'decay_rate:' "$config_file" 2>/dev/null | awk '{print $2}' || echo "0.03")}"
  threshold="${SPORE_CONSOLIDATION_THRESHOLD:-$(grep 'consolidation_threshold:' "$config_file" 2>/dev/null | awk '{print $2}' || echo "0.3")}"
else
  lambda="${SPORE_DECAY_RATE:-0.03}"
  threshold="${SPORE_CONSOLIDATION_THRESHOLD:-0.3}"
fi

echo ""
echo "  ╭─────────────────────────────────────╮"
echo "  │       🌱 spore consolidation         │"
echo "  ╰─────────────────────────────────────╯"
echo ""

if [ ! -f "$retrieval_log" ]; then
  echo "  No retrieval data. Still in germination phase."
  exit 0
fi

total_entries=$(tail -n +2 "$retrieval_log" | wc -l | tr -d ' ')
if [ "$total_entries" -lt 10 ]; then
  echo "  Only $total_entries retrievals logged. Need at least 10 for consolidation."
  echo "  Keep working - data accumulates naturally."
  exit 0
fi

echo "  Computing decay for all tracked documents..."
echo "  Lambda: $lambda | Threshold: $threshold"
echo ""

today=$(date +%s)

echo "  Decay Candidates (strength < $threshold):"
echo "  ────────────────────────────────────"

tail -n +2 "$retrieval_log" | awk -F, '{print $3}' | sort -u | while read file; do
  last_date=$(grep "$file" "$retrieval_log" | tail -1 | awk -F, '{print $1}')
  count=$(grep -c "$file" "$retrieval_log" || echo "0")

  if [ -n "$last_date" ]; then
    last_epoch=$(date -j -f "%Y-%m-%d" "$last_date" +%s 2>/dev/null || date -d "$last_date" +%s 2>/dev/null || echo "$today")
    days_since=$(( (today - last_epoch) / 86400 ))

    base_strength=$(echo "$count" | awk '{s = 1.0 + ($1 - 1) * 0.1; if (s > 2.0) s = 2.0; print s}')
    strength=$(echo "$base_strength $lambda $days_since" | awk '{printf "%.3f", $1 * exp(-$2 * $3)}')

    is_candidate=$(echo "$strength $threshold" | awk '{print ($1 < $2) ? 1 : 0}')
    if [ "$is_candidate" -eq 1 ]; then
      printf '  %-50s strength: %s (last: %s, %dd ago)\n' "$file" "$strength" "$last_date" "$days_since"
    fi
  fi
done

echo ""
echo "  Present candidates to practitioner for confirmation."
echo "  Never archive silently."
