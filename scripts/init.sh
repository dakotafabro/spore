#!/usr/bin/env bash
set -euo pipefail

repo_root="${SPORE_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
config_file="$repo_root/.spore.yaml"

echo ""
echo '              ____'
echo '          _.-'"'"'78o `"`--._'
echo '      ,o888o.  .o888o,   '"'"''"'"'-.'
echo '    ,88888P  `78888P..______.]'
echo '   /_..__..----""        __.'"'"''
echo '   `-._       /""| _..-'"'"''"'"''
echo '       "`-----\  `\'
echo '               |   ;.-""--..        '
echo '               | ,8o.  o88. `.'
echo '               `;888P  `788P  :'
echo '         .o""-.|`-._         ./'
echo '        J88 _.-/    ";"-P----'"'"''
echo '        `--'"'"'\`|     /  /'
echo '            | /     |  |'
echo '            \|     /   |'
echo '             `-----`---'"'"''
echo '        ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌'
echo '       ~ ~ mycelium below ~ ~'
echo ""
echo "           s p o r e   i n i t"
echo ""
echo "  ────────────────────────────────────"
echo "  Substrate: $repo_root"
echo "  ────────────────────────────────────"
echo ""

if [ -f "$config_file" ]; then
  echo "  ⚠️  .spore.yaml already exists. Re-running init (safe - won't overwrite data)."
  echo ""
fi

retrieval_log="$repo_root/.retrieval-log.csv"
if [ ! -f "$retrieval_log" ]; then
  echo "date,session_id,file,context" > "$retrieval_log"
  echo "  ✅ Created .retrieval-log.csv"
else
  count=$(tail -n +2 "$retrieval_log" | wc -l | tr -d ' ')
  echo "  ✓  .retrieval-log.csv exists ($count entries)"
fi

interoception_log="$repo_root/.interoception-log.csv"
if [ ! -f "$interoception_log" ]; then
  echo "timestamp,session_id,context_remaining_pct,retrievals,tokens_spent,deliverables,efficiency_vs_baseline,agent_observation" > "$interoception_log"
  echo "  ✅ Created .interoception-log.csv"
else
  count=$(tail -n +2 "$interoception_log" | wc -l | tr -d ' ')
  echo "  ✓  .interoception-log.csv exists ($count entries)"
fi

proximity_graph="$repo_root/.proximity-graph.csv"
if [ ! -f "$proximity_graph" ]; then
  echo "  ℹ️  .proximity-graph.csv will be generated after 3+ sessions (spore graph)"
else
  edges=$(tail -n +2 "$proximity_graph" | wc -l | tr -d ' ')
  echo "  ✓  .proximity-graph.csv exists ($edges edges)"
fi

trust_state="$repo_root/.trust-state.yaml"
if [ ! -f "$trust_state" ]; then
  cat > "$trust_state" << 'EOF'
trust_levels:
  index_maintenance:
    level: 2
    consecutive_confirmations: 0
    threshold_for_level_3: 5
  retrieval_optimization:
    level: 2
    consecutive_confirmations: 0
    threshold_for_level_3: 8
  log_metadata_writes:
    level: 2
    consecutive_confirmations: 0
    threshold_for_level_3: 3
  proximity_informed:
    level: 2
    consecutive_confirmations: 0
    threshold_for_level_3: 5
EOF
  echo "  ✅ Created .trust-state.yaml (all categories at level 2)"
else
  echo "  ✓  .trust-state.yaml exists"
fi

if [ ! -f "$config_file" ]; then
  cat > "$config_file" << EOF
spore:
  version: 0.1.0
  repo_root: $repo_root
  decay_rate: 0.03
  consolidation_threshold: 0.3
  proximity_decay_days: 60
  proximity_prune_threshold: 0.5
  importance_overrides: []
  phase: germination
  initialized: $(date +%Y-%m-%d)
EOF
  echo "  ✅ Created .spore.yaml"
else
  echo "  ✓  .spore.yaml exists"
fi

echo ""
echo "  ╭─────────────────────────────────────╮"
echo "  │       How Spore Works (Background)  │"
echo "  ╰─────────────────────────────────────╯"
echo ""
echo "  Spore observes your agent's file reads and builds a living"
echo "  map of how knowledge flows through your work. Nothing is"
echo "  hidden. Here's exactly what runs and when:"
echo ""
echo "  ON EVERY SESSION START:"
echo "    → Generates a unique session ID"
echo "    → Initializes a session state counter"
echo "    → No network calls. No data leaves your machine."
echo ""
echo "  ON EVERY FILE READ (by the agent):"
echo "    → Appends one line to .retrieval-log.csv:"
echo "      date, session_id, file_path, context"
echo "    → Skips INDEX.md files and spore's own data files"
echo "    → Increments session retrieval counter"
echo "    → No analysis runs. Just a single CSV append."
echo ""
echo "  ON YOUR COMMAND ONLY:"
echo "    → spore status     - reads the CSV, shows stats"
echo "    → spore suggest    - analyzes patterns, proposes improvements"
echo "    → spore consolidate - computes decay, YOU confirm any changes"
echo "    → spore graph      - builds proximity map from co-retrievals"
echo "    → spore sense      - shows current session resource state"
echo "    → spore scaffold   - generates reference topology for comparison"
echo ""
echo "  SPORE NEVER:"
echo "    → Deletes or moves files without your explicit confirmation"
echo "    → Sends data to any external service"
echo "    → Modifies your source code or documents"
echo "    → Runs background processes between sessions"
echo "    → Makes decisions on your behalf"
echo ""
echo "  All data is plain-text CSV/YAML in your repo root."
echo "  Inspect anytime: cat .retrieval-log.csv"
echo ""
echo "  ────────────────────────────────────"
echo ""
echo "  Topology detection:"
echo "  ────────────────────────────────────"

has_index=false
has_git=false
has_dirs=false
dir_count=0

if [ -f "$repo_root/INDEX.md" ]; then
  has_index=true
  echo "  ✓  Root INDEX.md found (spore will skip INDEX reads from retrieval log)"
fi

if [ -d "$repo_root/.git" ]; then
  has_git=true
  echo "  ✓  Git repo detected"
fi

dir_count=$(find "$repo_root" -maxdepth 1 -type d | wc -l | tr -d ' ')
dir_count=$((dir_count - 1))
if [ "$dir_count" -gt 0 ]; then
  has_dirs=true
  echo "  ✓  $dir_count top-level directories detected"
fi

file_count=$(find "$repo_root" -maxdepth 3 -name "*.md" -type f 2>/dev/null | wc -l | tr -d ' ')
echo "  ℹ️  $file_count markdown files within 3 levels"

echo ""
echo "  Adaptation:"
echo "  ────────────────────────────────────"

if [ "$has_index" = true ]; then
  echo "  → INDEX.md topology detected. Spore will:"
  echo "    - Skip INDEX.md reads from retrieval logging"
  echo "    - Use directory structure for cross-domain bridge detection"
  echo "    - Compute INDEX sufficiency over time"
else
  echo "  → No INDEX.md topology. Spore will:"
  echo "    - Log ALL file reads as retrievals"
  echo "    - Use top-level directories for domain grouping (proximity graph)"
  echo "    - Skip INDEX sufficiency metrics (not applicable)"
fi

sessions_db="$HOME/.local/share/goose/sessions/sessions.db"
if [ -f "$sessions_db" ]; then
  session_count=$(sqlite3 "$sessions_db" "SELECT COUNT(*) FROM sessions WHERE session_type='user';" 2>/dev/null || echo "0")
  echo "  → Found goose sessions.db ($session_count prior sessions)"
  echo "    - Historical baselines available immediately"
  if [ "$session_count" -gt 10 ]; then
    echo "    - Sufficient history for differentiated sensing (skipping pure germination)"
  fi
else
  echo "  → No goose sessions.db found"
  echo "    - Starting from pure germination (undifferentiated sensing)"
fi

rpwhy_data=$(find "$repo_root" -name "rp-why-session-level.csv" -type f 2>/dev/null | head -1)
if [ -n "$rpwhy_data" ]; then
  echo "  → rp-why data found at: $rpwhy_data"
  echo "    - Outcome correlation available (context quality → collaboration quality)"
else
  echo "  → No rp-why data detected"
  echo "    - Spore will operate without outcome correlation"
  echo "    - Install rp-why for the full feedback loop"
fi

echo ""
echo "  ╭─────────────────────────────────────╮"
echo "  │       Configuration                 │"
echo "  ╰─────────────────────────────────────╯"
echo ""
echo "  All settings live in .spore.yaml at your repo root."
echo "  Edit anytime with any text editor. Changes take effect next session."
echo ""
echo "  ┌──────────────────────────────────────────────────────────────┐"
echo "  │ Setting                  │ Default │ What it controls        │"
echo "  ├──────────────────────────┼─────────┼─────────────────────────┤"
echo "  │ decay_rate               │ 0.03    │ How fast unused docs    │"
echo "  │                          │         │ lose strength           │"
echo "  │                          │         │ (half-life ~23 days)    │"
echo "  ├──────────────────────────┼─────────┼─────────────────────────┤"
echo "  │ consolidation_threshold  │ 0.3     │ Strength below this =   │"
echo "  │                          │         │ consolidation candidate │"
echo "  ├──────────────────────────┼─────────┼─────────────────────────┤"
echo "  │ proximity_decay_days     │ 60      │ Days before unreinforced│"
echo "  │                          │         │ graph edges get halved  │"
echo "  ├──────────────────────────┼─────────┼─────────────────────────┤"
echo "  │ proximity_prune_threshold│ 0.5     │ Edge weight below this  │"
echo "  │                          │         │ gets pruned from graph  │"
echo "  ├──────────────────────────┼─────────┼─────────────────────────┤"
echo "  │ importance_overrides     │ []      │ Paths that never decay  │"
echo "  │                          │         │ e.g. [\"conventions/\"]   │"
echo "  └──────────────────────────┴─────────┴─────────────────────────┘"
echo ""
echo "  Examples:"
echo "    Slower decay (keep docs active longer):"
echo "      decay_rate: 0.01          # half-life ~69 days"
echo ""
echo "    Faster decay (aggressive consolidation):"
echo "      decay_rate: 0.05          # half-life ~14 days"
echo ""
echo "    Protect critical paths from ever decaying:"
echo "      importance_overrides:"
echo "        - conventions/"
echo "        - README.md"
echo "        - src/core/"
echo ""

spore_files=(".retrieval-log.csv" ".interoception-log.csv" ".proximity-graph.csv" ".trust-state.yaml" ".spore.yaml")
gitignore_prompted=$(grep -q "gitignore_prompted: true" "$config_file" 2>/dev/null && echo "true" || echo "false")

if [ "$gitignore_prompted" = "false" ]; then
  all_ignored=true
  if [ -f "$repo_root/.gitignore" ]; then
    for f in "${spore_files[@]}"; do
      if ! grep -qxF "$f" "$repo_root/.gitignore"; then
        all_ignored=false
        break
      fi
    done
  else
    all_ignored=false
  fi

  if [ "$all_ignored" = "false" ]; then
    echo "  Data tracking:"
    echo "  ────────────────────────────────────"
    echo "  Spore data files can be committed or gitignored."
    echo ""
    echo "  Commit them:  Longitudinal data preserved, survives machine changes,"
    echo "                visible to collaborators"
    echo "  Gitignore:    Data stays local, no noise in commits, each machine"
    echo "                builds its own picture"
    echo ""
    echo "  Spore data files:"
    echo "    .retrieval-log.csv"
    echo "    .interoception-log.csv"
    echo "    .proximity-graph.csv"
    echo "    .trust-state.yaml"
    echo "    .spore.yaml"
    echo ""
    printf '  To gitignore:\n'
    printf '    echo -e ".retrieval-log.csv\\n.interoception-log.csv\\n.proximity-graph.csv\\n.trust-state.yaml\\n.spore.yaml" >> .gitignore\n'
    echo ""
    echo "  To commit (recommended for solo practitioners): just git add them normally."
    echo ""
  fi

  if grep -q "^spore:" "$config_file" 2>/dev/null; then
    echo "gitignore_prompted: true" >> "$config_file"
  fi
fi

echo "  ────────────────────────────────────"
echo ""
echo "       ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~"
echo "      The mycelium is listening."
echo "      Work naturally. Data accumulates."
echo "      Run 'spore status' anytime."
echo "       ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~"
echo ""
