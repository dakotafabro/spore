# 🌱 Spore

**Biomimetic agent memory for goose: use-driven decay, proximity graphs and interoception.**

A [goose](https://github.com/aaif-goose/goose) plugin and MCP server that watches which documents an agent actually uses, connects documents used together, and lets unused knowledge decay so it can be consolidated. Inspired by mycelial networks, where the topology is the memory: used paths strengthen and unused paths fade.

> [!NOTE]
> Spore observes and proposes. It never deletes, moves or rewrites your files on its own, and nothing leaves your machine.

## Install

```bash
bpm install spore
```

Or install the goose plugin directly:

```bash
goose plugin add github:dakotafabro/spore
```

## Quick start

In the repo you want spore to observe:

```bash
spore init
```

Then work normally. Every file the agent reads is logged to `.retrieval-log.csv`. After 10 or more retrievals, ask the agent to run `spore_suggest` for grouping, INDEX and consolidation suggestions based on your actual use, or `spore_status` for a summary.

> [!WARNING]
> **Limits**
> - Spore has one practitioner's data behind it (n=1). Its defaults, like the decay rate of `0.03` (a half-life of about 23 days), are starting guesses meant to be tuned.
> - Hooks only see files the agent reads through goose's file tools and simple shell reads (`cat`, `head`, `tail`, `less`, `more`, `bat`). In Code Mode, log reads with `spore_log_retrieval`.
> - Interoception is the agent's self-report. There's no ground truth for it.

<details>
<summary>How it works</summary>

Spore is an [Open Plugins](https://open-plugins.com) plugin. It hooks into goose's session and tool-use lifecycle to observe behavior without changing it, and exposes its analysis as MCP tools.

```
┌─────────────────────────────────────────────┐
│  Practitioner's repo / knowledge system     │
└──────────────────┬──────────────────────────┘
                   │ file reads (BeforeReadFile hook)
                   ▼
┌─────────────────────────────────────────────┐
│  spore plugin                               │
│                                             │
│  hooks/hooks.json    → event interception   │
│  scripts/            → computation engines  │
│                                             │
│  Engines:                                   │
│  ├── retrieval logging (append-only CSV)    │
│  ├── decay computation (exponential)        │
│  ├── proximity graph (co-retrieval)         │
│  ├── interoception (self-sensing)           │
│  └── consolidation (compress + archive)     │
└─────────────────────────────────────────────┘
```

### What runs, and when

**On every session start:** Generates a session ID, initializes a counter. No network calls. No data leaves your machine.

**On every file read (by the agent):** Appends one line to `.retrieval-log.csv` (date, session_id, file_path, context). Skips INDEX.md and spore's own data files. No analysis runs - just a single CSV append.

**On your command only:** All analysis (`status`, `suggest`, `consolidate`, `graph`, `sense`, `scaffold`) runs only when you invoke it.

**Spore never:**
- Deletes or moves files without your explicit confirmation
- Sends data to any external service
- Modifies your source code or documents
- Runs background processes between sessions
- Makes decisions on your behalf

All data is plain-text CSV/YAML in your repo root. Inspect anytime: `cat .retrieval-log.csv`

</details>

<details>
<summary>Reference: hooks, MCP tools, init and configuration</summary>

### Hooks

| Event | What spore does |
|---|---|
| `SessionStart` | Creates a session ID and resets the session counters |
| `BeforeReadFile` | Logs the read to `.retrieval-log.csv` and increments the session count. Skips `INDEX.md` and spore's own data files |
| `AfterShellExecution` | Logs files read through `cat`, `head`, `tail`, `less`, `more` and `bat` |
| `SessionEnd` | Records an interoception observation when the session read any files |

### MCP tools

| Tool | What it does |
|---|---|
| `spore_init` | Detect topology, create data files, configure. Idempotent. |
| `spore_status` | Retrieval stats, trust state, graph summary |
| `spore_suggest` | Data-driven topology recommendations (INDEX drafts, groupings, bridges, hotspots) |
| `spore_consolidate` | Compute decay, identify candidates, present for confirmation |
| `spore_graph` | Regenerate proximity graph from co-retrieval data |
| `spore_sense` | Return current session resource state |
| `spore_log_retrieval` | Manually log a file retrieval when hooks don't fire (e.g., Code Mode) |
| `spore_log_deposition` | Log a file creation - new knowledge deposited into the substrate |
| `spore_log_interoception` | Log the agent's self-observed resource state at a natural transition point |

### What `spore init` does

Spore adapts to whatever structure it finds. No specific topology is required.

| Your repo has... | Spore does... |
|---|---|
| INDEX.md files | Skips INDEX reads from retrieval log, computes INDEX sufficiency, uses directory structure for domain grouping |
| No INDEX.md | Logs ALL file reads, uses top-level directories for domain grouping, skips INDEX sufficiency metrics |
| Existing goose sessions.db | Computes behavioral baselines immediately, may skip pure germination phase |
| rp-why data | Enables outcome correlation (context quality to collaboration quality) |
| Flat file structure | Works fine - proximity graph uses filenames instead of directory paths for grouping |
| Deep nested structure | Works fine - uses first path segment as domain for cross-domain bridge detection |
| Nothing (empty repo) | Creates data files, starts in germination, accumulates from scratch |

`spore init` creates:
- `.retrieval-log.csv` - where retrieval data accumulates
- `.interoception-log.csv` - agent self-sensing observations
- `.trust-state.yaml` - trust escalation tracking
- `.spore.yaml` - configuration (decay rate, thresholds, phase)

If you skip `spore init`, the plugin still works - it auto-creates `.retrieval-log.csv` on first file read and logs a reminder to run init for full setup.

### Configuration

Set `SPORE_REPO_ROOT` to point at your knowledge repo, or spore will auto-detect via `git rev-parse --show-toplevel`.

Edit `.spore.yaml` to tune:

```yaml
spore:
  decay_rate: 0.03              # lambda - higher = faster decay (default half-life ~23 days)
  consolidation_threshold: 0.3  # strength below this = consolidation candidate
  proximity_decay_days: 60      # co-retrieval edges not reinforced in N days get halved
  proximity_prune_threshold: 0.5
  importance_overrides: []      # paths that never decay (e.g., ["conventions/", "README.md"])
```

### Growing your topology with `spore_suggest`

Analyzes your actual retrieval patterns and proposes personalized improvements:

- **Grouping suggestions** - files always co-retrieved that might belong together
- **INDEX.md drafts** - auto-generated skeletons for high-traffic directories
- **Consolidation nudge** - files not retrieved in 30+ days
- **Bridge detection** - files that connect 3+ domains (candidates for importance overrides)
- **Retrieval hotspots** - files opened 3x above median (might need splitting or better INDEX summaries)

Suggest tells you what your data actually supports. No restructuring required - topology emerges from practice.

The `scripts/scaffold.sh` script can generate a `.spore-scaffold/` reference topology for comparison and incremental adoption.

</details>

<details>
<summary>The experiment: problem, hypotheses, method and timeline</summary>

### Problem

Agent memory systems today are static, accumulative, and blind to practitioner behavior. They store everything, forget nothing principled, and can't learn from how knowledge is actually used. The topology of knowledge - what relates to what, what's load-bearing, what's stale - is invisible to the system.

Simultaneously, cross-discipline practitioners generate integrative knowledge through their work - connections between fields that no taxonomy predicts - but this knowledge formation is unobserved and unmeasured.

### Hypotheses

1. **Retrieval follows a power law.** A small number of documents account for most retrievals. The long tail is consolidation-eligible.
2. **INDEX sufficiency increases over time.** As summaries improve through consolidation, the agent needs full docs less often.
3. **Consolidation improves retrieval relevance.** Fewer documents competing for attention means the right context surfaces faster.
4. **Collaboration quality correlates with context relevance.** Better context in = better collaboration out (measured via rp-why).
5. **Cross-discipline bridges emerge from practice.** The proximity graph reveals connections between domains that directory taxonomy doesn't encode.
6. **Bridge documents are disproportionately valuable.** High-betweenness documents correlate with higher-DOK sessions.
7. **Interoceptive accuracy improves over time.** The agent gets better at sensing and interpreting its own resource state.

### Method

The practitioner's natural workflow IS the instrumentation. No synthetic tasks. No separate experiment protocol. The system observes work and learns from it.

```
natural workflow → generates data → records automatically → analyzes (weekly/monthly) → distills into findings
```

**Instruments:**
- `.retrieval-log.csv` - every full-document access with session grouping
- `.proximity-graph.csv` - co-retrieval graph computed from session-grouped retrievals
- `.interoception-log.csv` - agent self-reported resource state at natural checkpoints
- `.trust-state.yaml` - per-category trust escalation tracking
- rp-why session scores - collaboration quality outcome measure

### Theoretical foundation

**Biomimicry:** Nature is efficient because cost is structural, not imposed. An organism that wastes energy dies. This experiment applies the same principle to agent memory - knowledge that wastes attention decays. Both are efficient because cost is felt, not managed.

**Mechanisms borrowed from mycelium:**
- Reinforce/decay (pheromone rule) - used paths strengthen, unused paths atrophy
- Consolidation as sleep - compress and migrate from expensive to cheap storage
- Co-activation wiring (Hebbian) - nodes that fire together wire together
- Spend only on surprise - good summaries mean less full-doc retrieval
- Intrinsic sensing - monitoring is a property of the system, not bolted on

**Regenerative systems design:** A system without a feedback loop is extractive by default. This experiment closes the loops - retrieval patterns feed back to memory structure, quality scores feed back to practitioner behavior, cost awareness feeds back to agent behavior.

### Timeline

| Phase | Dates | Activity |
|---|---|---|
| Germination | Jul 13 - Aug 10, 2026 | Log retrievals + interoception. Undifferentiated sensing. |
| First consolidation | Aug 10, 2026 | First decay computation. Identify candidates. |
| Differentiation | Aug 10 - Oct 5, 2026 | Baselines emerge per task type. Calibration. |
| Maturation | Oct 5, 2026+ | Self-regulation. Trust escalation. Calibrated interoception. |
| Analysis | Oct 2026 | Test hypotheses. First findings. |

### Controls and limitations

- Single practitioner (n=1). Findings may not generalize.
- The practitioner knows they're being measured, so a Hawthorne effect is possible.
- The decay rate (lambda=0.03) is a starting guess, to be tuned from the promotion rate.
- Interoceptive accuracy is self-assessed, with no ground truth for a "correct" internal state.

</details>

<details>
<summary>Design principles</summary>

1. **The practitioner governs.** Spore proposes, never acts autonomously on high-stakes decisions.
2. **Data stays local.** All computation happens in the practitioner's repo. No external services.
3. **Work IS the experiment.** No synthetic tasks. The natural workflow generates all data.
4. **Efficiency is structural.** The system doesn't need management - it self-organizes through use.
5. **Feedback loops are closed.** Every output feeds back as input. Nothing is discarded without becoming signal.

</details>

<details>
<summary>Verify it works</summary>

49 pytest tests cover the core modules: decay computation, the proximity graph, config resolution and CSV I/O.

```bash
cd mcp && python3 -m pytest tests/
```

Expected: `49 passed`.

The 12 shell scripts in `scripts/` run the hooks and the standalone commands:

- `session-start.sh`, `session-end.sh`: session lifecycle hooks
- `on-file-read.sh`, `on-shell-exec.sh`: retrieval capture hooks
- `status.sh`, `suggest.sh`, `consolidate.sh`, `graph.sh`, `sense.sh`, `init.sh`, `scaffold.sh`: CLI wrappers
- `metrics.sh`: prints experiment metrics from your local logs to the terminal. It never writes them to a tracked file

</details>

<details>
<summary>Version history</summary>

| Version | Date | Changes |
|---|---|---|
| 0.2.1 | 2026-10 | Package ships only declared files. Live metrics removed from the README; `scripts/metrics.sh` prints them locally |
| 0.2.0 | 2026-08 | Structural interoception (session-end hook auto-captures), trust proposal triggers (retrieval threshold fires proposal_opportunity), SKILL.md proposal handling |
| 0.1.0 | 2026-07 | Initial release. Retrieval logging, proximity graph, interoception (manual), decay computation, consolidation, trust state, deposition tracking, MCP extension |

</details>

## Related

- [hyphae](https://github.com/dakotafabro/hyphae): session continuity across machines, a spore peer
- [rp-why](https://github.com/dakotafabro/rp-why): collaboration quality measurement, the outcome measure for this experiment
- [goose](https://github.com/aaif-goose/goose): the agent platform spore instruments
- [Open Plugins](https://open-plugins.com): the plugin format

## License

Apache 2.0

<sub>A spore carries the full genetic potential of a mycelial network compressed into the smallest possible form. It lands on new substrate and develops based on what it encounters.</sub>
