#!/usr/bin/env bash
set -euo pipefail

repo_root="${SPORE_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
retrieval_log="$repo_root/.retrieval-log.csv"
proximity_graph="$repo_root/.proximity-graph.csv"

echo ""
echo "  ╭─────────────────────────────────────╮"
echo "  │       🌱 spore proximity graph       │"
echo "  ╰─────────────────────────────────────╯"
echo ""

if [ ! -f "$retrieval_log" ]; then
  echo "  No retrieval data. Still in germination phase."
  exit 0
fi

total_sessions=$(tail -n +2 "$retrieval_log" | awk -F, '{print $2}' | sort -u | wc -l | tr -d ' ')
if [ "$total_sessions" -lt 3 ]; then
  echo "  Only $total_sessions sessions logged. Need at least 3 for proximity computation."
  exit 0
fi

echo "  Computing co-retrieval graph from $total_sessions sessions..."
echo ""

echo "source,target,weight,last_co_retrieval,sessions_shared" > "$proximity_graph"

tail -n +2 "$retrieval_log" | awk -F, '{print $2}' | sort -u | while read session; do
  files_in_session=$(grep ",$session," "$retrieval_log" | awk -F, '{print $3}' | sort -u)
  file_count=$(echo "$files_in_session" | wc -l | tr -d ' ')

  if [ "$file_count" -ge 2 ]; then
    echo "$files_in_session" | while read file_a; do
      echo "$files_in_session" | while read file_b; do
        if [[ "$file_a" < "$file_b" ]]; then
          echo "$file_a,$file_b,$session"
        fi
      done
    done
  fi
done | sort | awk -F, '{
  key = $1 "," $2
  count[key]++
  last[key] = $3
}
END {
  for (key in count) {
    split(key, parts, ",")
    printf "%s,%s,%d,%s,%d\n", parts[1], parts[2], count[key], last[key], count[key]
  }
}' | sort -t, -k3 -rn >> "$proximity_graph"

edges=$(tail -n +2 "$proximity_graph" | wc -l | tr -d ' ')
cross_domain=$(tail -n +2 "$proximity_graph" | awk -F, '{split($1,a,"/"); split($2,b,"/"); if(a[1]!=b[1]) print}' | wc -l | tr -d ' ')

echo "  Graph computed:"
echo "  Edges:          $edges ($cross_domain cross-domain)"
echo ""
echo "  Strongest connections:"
tail -n +2 "$proximity_graph" | head -5 | while IFS=, read source target weight last sessions; do
  printf '    %s ↔ %s (weight: %s, %s sessions)\n' "$source" "$target" "$weight" "$sessions"
done
echo ""

if [ "$cross_domain" -gt 0 ]; then
  echo "  Cross-domain bridges:"
  tail -n +2 "$proximity_graph" | awk -F, '{split($1,a,"/"); split($2,b,"/"); if(a[1]!=b[1]) print}' | head -5 | while IFS=, read source target weight last sessions; do
    printf '    %s ↔ %s (weight: %s)\n' "$source" "$target" "$weight"
  done
  echo ""
fi
