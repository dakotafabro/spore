#!/usr/bin/env bash
set -euo pipefail

repo_root="${SPORE_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
config_file="$repo_root/.spore.yaml"
retrieval_log="$repo_root/.retrieval-log.csv"
trust_state="$repo_root/.trust-state.yaml"

echo ""
echo "  ╭─────────────────────────────────────╮"
echo "  │           🌱 spore status            │"
echo "  ╰─────────────────────────────────────╯"
echo ""

if [ ! -f "$config_file" ]; then
  echo "  ⚠️  Spore not initialized in this repo."
  echo "  Run: spore init"
  echo ""
  echo "  Spore will still log retrievals automatically,"
  echo "  but init gives you topology detection, trust state,"
  echo "  and configuration."
  echo ""
fi

if [ -f "$retrieval_log" ]; then
  total=$(tail -n +2 "$retrieval_log" | wc -l | tr -d ' ')
  this_week=$(tail -n +2 "$retrieval_log" | awk -F, -v d="$(date -v-7d +%Y-%m-%d)" '$1 >= d' | wc -l | tr -d ' ')
  unique_docs=$(tail -n +2 "$retrieval_log" | awk -F, '{print $3}' | sort -u | wc -l | tr -d ' ')
  most_retrieved=$(tail -n +2 "$retrieval_log" | awk -F, '{print $3}' | sort | uniq -c | sort -rn | head -5)

  echo "  Retrievals"
  echo "  ────────────────────────────────────"
  echo "  Total:          $total ($this_week this week)"
  echo "  Unique docs:    $unique_docs"
  echo ""
  echo "  Most retrieved:"
  echo "$most_retrieved" | while read count file; do
    printf '    %3d  %s\n' "$count" "$file"
  done
  echo ""
else
  echo "  No retrieval data yet (germination phase)"
  echo ""
fi

if [ -f "$trust_state" ]; then
  echo "  Trust State"
  echo "  ────────────────────────────────────"
  grep -A2 "consecutive_confirmations:" "$trust_state" | grep "consecutive_confirmations:" | while read line; do
    echo "    $line"
  done
  echo ""
fi

proximity_graph="$repo_root/.proximity-graph.csv"
if [ -f "$proximity_graph" ]; then
  edges=$(tail -n +2 "$proximity_graph" | wc -l | tr -d ' ')
  cross_domain=$(tail -n +2 "$proximity_graph" | awk -F, '{split($1,a,"/"); split($2,b,"/"); if(a[1]!=b[1]) print}' | wc -l | tr -d ' ')
  echo "  Proximity Graph"
  echo "  ────────────────────────────────────"
  echo "  Edges:          $edges ($cross_domain cross-domain)"
  echo ""
else
  echo "  Proximity graph: not yet computed"
  echo ""
fi
