# spore - what changes for you

spore watches which files your agent reads and builds a picture of how your knowledge is actually used: what gets read often, what's going stale, and what gets read together.

## What it does, and to the agent

Hooks log each file the agent reads (skipping INDEX files and spore's own data), and a row of session stats at session end. Tools let the agent report stats (`spore_status`), suggest structure (`spore_suggest`), compute decay and propose archival (`spore_consolidate`), and log its own sense of its resource state (`spore_log_interoception`). The README says the hooks observe behavior without modifying it.

## When to use it

On a knowledge repo you work in daily, where you want structure to follow use. It needs weeks of data before patterns mean much.

## Reserved for human judgment

Consolidation presents candidates for confirmation. What gets archived, merged or rewritten is yours. The README names its own limits: one practitioner, a starting-guess decay rate, and self-assessed interoception with no ground truth.

## What it reads, writes and sends

- Writes plain CSV and YAML in your repo root: `.retrieval-log.csv`, `.proximity-graph.csv`, `.interoception-log.csv`, `.trust-state.yaml`, plus per-session files under `.sessions/`.
- Reads token counts from goose's `sessions.db`.
- The README says no network calls and no data leaves your machine. If the repo is pushed, the log files go with it, file paths included.

## Cost

About 1,900 tokens of context (`token_cost` in bpm.json).

## Check it's working

Run `spore_status`, or `cat .retrieval-log.csv` after a session that read files.

## Turn it off

Remove the goose plugin, then `bpm remove spore`. The data files stay in your repo until you delete them.
