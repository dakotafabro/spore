#!/usr/bin/env bash
set -euo pipefail

repo_root="${SPORE_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
config_file="$repo_root/.spore.yaml"
retrieval_log="$repo_root/.retrieval-log.csv"
proximity_graph="$repo_root/.proximity-graph.csv"

echo ""
echo "  ╭─────────────────────────────────────╮"
echo "  │          🌱 spore suggest            │"
echo "  ╰─────────────────────────────────────╯"
echo ""

if [ ! -f "$retrieval_log" ]; then
  echo "  Not enough data yet."
  echo "  Need at least 10 retrievals across 3+ sessions."
  echo ""
  exit 0
fi

total_retrievals=$(tail -n +2 "$retrieval_log" | wc -l | tr -d ' ')
total_sessions=$(tail -n +2 "$retrieval_log" | awk -F, '{print $2}' | sort -u | wc -l | tr -d ' ')

if [ "$total_retrievals" -lt 10 ] || [ "$total_sessions" -lt 3 ]; then
  echo "  Not enough data yet."
  echo "  Have $total_retrievals retrievals across $total_sessions sessions."
  echo "  Need at least 10 retrievals across 3+ sessions."
  echo ""
  exit 0
fi

echo "  Analyzing $total_retrievals retrievals across $total_sessions sessions..."
echo ""

suggestion_count=0

echo "  Grouping Suggestions"
echo "  ────────────────────────────────────"

if [ -f "$proximity_graph" ]; then
  grouping_suggestions=$(tail -n +2 "$proximity_graph" | awk -F, '$5 >= 3 {
    split($1, a, "/")
    split($2, b, "/")
    if (a[1] != b[1] || (length(a) > 2 && length(b) > 2 && a[2] != b[2])) {
      printf "    %s\n      ↔ %s (%s sessions together)\n", $1, $2, $5
    }
  }')

  if [ -n "$grouping_suggestions" ]; then
    echo "$grouping_suggestions"
    echo ""
    echo "    → What to do: Consider adding a shared INDEX entry linking"
    echo "      these files, or evaluate whether they belong in the same directory."
    suggestion_count=$((suggestion_count + 1))
  else
    echo "    No co-retrieval clusters detected yet."
  fi
else
  echo "    Proximity graph not computed. Run: spore graph"
fi
echo ""

echo "  INDEX.md Suggestions"
echo "  ────────────────────────────────────"

dirs_needing_index=$(tail -n +2 "$retrieval_log" | awk -F, '{print $3}' | \
  awk -F/ '{OFS="/"; NF--; print}' | sort | uniq -c | sort -rn | \
  while read count dir; do
    if [ "$count" -ge 4 ] && [ -n "$dir" ] && [ ! -f "$repo_root/$dir/INDEX.md" ]; then
      echo "$count $dir"
    fi
  done)

if [ -n "$dirs_needing_index" ]; then
  echo "$dirs_needing_index" | while read count dir; do
    echo "    $dir/ ($count retrievals, no INDEX.md)"
    echo ""
    echo "    Suggested INDEX.md skeleton:"
    echo "    ┌──────────────────────────────────"
    echo "    │ # $dir"
    echo "    │"
    echo "    │ ## Files"

    tail -n +2 "$retrieval_log" | awk -F, -v d="$dir" '$3 ~ "^"d"/" {print $3}' | \
      sort | uniq -c | sort -rn | head -8 | while read fcount file; do
        basename=$(echo "$file" | awk -F/ '{print $NF}')
        echo "    │ - \`$basename\` - (retrieved ${fcount}x)"
      done

    echo "    │"
    echo "    │ ## Tags"
    echo "    │ #needs-classification"
    echo "    └──────────────────────────────────"
    echo ""
    echo "    → What to do: Create $dir/INDEX.md with file summaries so the"
    echo "      agent can decide relevance without opening each file."
    echo ""
    suggestion_count=$((suggestion_count + 1))
  done
else
  echo "    All frequently-accessed directories have INDEX.md files."
fi
echo ""

echo "  Consolidation Nudge"
echo "  ────────────────────────────────────"

cutoff_date=""
if date -v-30d +%Y-%m-%d >/dev/null 2>&1; then
  cutoff_date=$(date -v-30d +%Y-%m-%d)
else
  cutoff_date=$(date -d "30 days ago" +%Y-%m-%d)
fi

stale_files=$(tail -n +2 "$retrieval_log" | awk -F, '{
  if ($1 > last[$3]) last[$3] = $1
}
END {
  for (f in last) print last[f], f
}' | awk -v cutoff="$cutoff_date" '$1 < cutoff {print $2}' | wc -l | tr -d ' ')

if [ "$stale_files" -gt 0 ]; then
  echo "    $stale_files files haven't been retrieved in 30+ days."
  echo ""
  echo "    → What to do: Run \`spore consolidate\` to review candidates"
  echo "      for archival or distillation."
  suggestion_count=$((suggestion_count + 1))
else
  echo "    All retrieved files are still active. No consolidation needed."
fi
echo ""

echo "  Bridge Detection"
echo "  ────────────────────────────────────"

bridges=$(tail -n +2 "$retrieval_log" | awk -F, '
{
  split($3, parts, "/")
  domain = parts[1]
  key = $2 SUBSEP domain
  if (!(key in sd)) { sd[key] = 1; sess_dom[$2] = sess_dom[$2] ? sess_dom[$2] "," domain : domain }
  key2 = $3 SUBSEP $2
  if (!(key2 in fs)) { fs[key2] = 1; file_sess[$3] = file_sess[$3] ? file_sess[$3] "," $2 : $2 }
  split($3, fp, "/")
  file_domain[$3] = fp[1]
}
END {
  for (file in file_sess) {
    own_domain = file_domain[file]
    n = split(file_sess[file], sessions, ",")
    delete foreign
    for (i = 1; i <= n; i++) {
      m = split(sess_dom[sessions[i]], doms, ",")
      for (j = 1; j <= m; j++) {
        if (doms[j] != own_domain) foreign[doms[j]] = 1
      }
    }
    count = 0; dlist = ""
    for (d in foreign) { count++; dlist = dlist ? dlist ", " d : d }
    if (count >= 3) printf "    %s\n      bridges %s to: %s\n", file, own_domain, dlist
  }
}')

if [ -n "$bridges" ]; then
  echo "$bridges"
  echo ""
  echo "    → What to do: These files serve as cross-domain connectors."
  echo "      Consider adding importance overrides in .spore.yaml so they"
  echo "      resist decay during consolidation."
  suggestion_count=$((suggestion_count + 1))
else
  if [ -f "$proximity_graph" ]; then
    cross_bridges=$(tail -n +2 "$proximity_graph" | awk -F, '{
      split($1, a, "/")
      split($2, b, "/")
      if (a[1] != b[1]) {
        files[a[1] "/" a[2] "/" a[3]]++
        files[b[1] "/" b[2] "/" b[3]]++
      }
    }
    END {
      for (f in files) if (files[f] >= 2) printf "    %s (appears in %d cross-domain edges)\n", f, files[f]
    }' | sort -t'(' -k2 -rn | head -5)

    if [ -n "$cross_bridges" ]; then
      echo "$cross_bridges"
      echo ""
      echo "    → What to do: Mark these as importance overrides in .spore.yaml."
      suggestion_count=$((suggestion_count + 1))
    else
      echo "    No cross-domain bridge files detected yet."
    fi
  else
    echo "    No cross-domain bridge files detected yet."
  fi
fi
echo ""

echo "  Retrieval Hotspots"
echo "  ────────────────────────────────────"

hotspot_data=$(tail -n +2 "$retrieval_log" | awk -F, '{print $3}' | sort | uniq -c | sort -rn)
median=$(echo "$hotspot_data" | awk '{print $1}' | sort -n | awk '{
  a[NR] = $1
}
END {
  if (NR % 2 == 1) print a[(NR+1)/2]
  else print (a[NR/2] + a[NR/2+1]) / 2
}')

threshold=$(echo "$median" | awk '{printf "%d", $1 * 3}')

echo "  Top 5 most-retrieved files (median: $median):"
echo ""

echo "$hotspot_data" | head -5 | while read count file; do
  if [ "$count" -ge "$threshold" ] && [ "$threshold" -gt 0 ]; then
    printf '    ⚡ %3d  %s\n' "$count" "$file"
  else
    printf '       %3d  %s\n' "$count" "$file"
  fi
done
echo ""

hotspot_count=$(echo "$hotspot_data" | head -5 | awk -v t="$threshold" '$1 >= t && t > 0 {count++} END {print count+0}')

if [ "$hotspot_count" -gt 0 ]; then
  echo "    ⚡ = retrieved 3x+ above median"
  echo ""
  echo "    → What to do: These files are opened far more than others."
  echo "      Consider splitting large files, or improving their INDEX.md"
  echo "      summary so the agent can decide relevance without opening them."
  suggestion_count=$((suggestion_count + 1))
else
  echo "    No extreme hotspots. Retrieval distribution looks healthy."
fi
echo ""

echo "  ────────────────────────────────────"
if [ "$suggestion_count" -gt 0 ]; then
  echo "  $suggestion_count suggestion(s) generated from your retrieval patterns."
else
  echo "  No suggestions right now. Topology looks healthy."
fi
echo ""
