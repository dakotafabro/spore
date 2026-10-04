#!/usr/bin/env bash
set -euo pipefail

spore_root="${SPORE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
if [ -z "${SPORE_REPO_ROOT:-}" ] && [ -f "$spore_root/.spore-env" ]; then
  # shellcheck disable=SC1091
  source "$spore_root/.spore-env"
fi
repo_root="${SPORE_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
retrieval_log="$repo_root/.retrieval-log.csv"
interoception_log="$repo_root/.interoception-log.csv"
proximity_graph="$repo_root/.proximity-graph.csv"

if [ ! -f "$retrieval_log" ]; then
  echo "  🌱 No retrieval log at $retrieval_log. Set SPORE_REPO_ROOT to the repo spore instruments." >&2
  exit 1
fi

today=$(date +"%b %d, %Y" | sed 's/  / /g')

retrievals=0
unique_docs=0
interoception_obs=0
proximity_edges=0
cross_domain=0

if [ -f "$retrieval_log" ]; then
  retrievals=$(tail -n +2 "$retrieval_log" | wc -l | tr -d ' ')
  unique_docs=$(tail -n +2 "$retrieval_log" | awk -F, '{print $3}' | sort -u | wc -l | tr -d ' ')
fi

if [ -f "$interoception_log" ]; then
  interoception_obs=$(tail -n +2 "$interoception_log" | wc -l | tr -d ' ')
fi

if [ -f "$proximity_graph" ]; then
  proximity_edges=$(tail -n +2 "$proximity_graph" | wc -l | tr -d ' ')
  cross_domain=$(tail -n +2 "$proximity_graph" | awk -F, '{split($1,a,"/"); split($2,b,"/"); if(a[1]!=b[1]) print}' | wc -l | tr -d ' ')
fi

echo "  🌱 Spore metrics (local only, $today)"
echo "     Retrievals: $retrievals | Docs: $unique_docs | Interoception: $interoception_obs"
echo "     Proximity edges: $proximity_edges | Cross-domain bridges: $cross_domain"
