---
name: spore
description: Biomimetic agent memory - retrieval tracking, interoception, and proximity graphs
---

## Retrieval Logging

Hooks capture file reads automatically for `developer__read_file` and shell commands (`cat`, `head`, `tail`, `less`, `more`, `bat`). No action needed for those.

**Code Mode (execute_typescript) bypasses all hooks.** When you read a knowledge-base document in Code Mode, call `spore_log_retrieval` with the file path and context. Without this call, the retrieval is invisible to the memory system.

What counts as a knowledge-base document:
- Markdown docs, design docs, conventions, research notes
- YAML/JSON config that encodes decisions or architecture
- Any file the practitioner authored as reference material

What to skip:
- Tool output, temp files, build artifacts
- Files outside the tracked repo
- INDEX.md files (these are navigation, not retrievals)

## Proposal Opportunities

When a retrieval response includes `proposal_opportunity`, generate a proposal for the indicated trust category and present it to the practitioner for confirmation.

## Interoception

At natural transition points, call `spore_log_interoception`:
- After a batch of retrievals
- After producing a deliverable
- At phase transitions in a workflow
- When you notice your own efficiency shifting

The observation field is your interpretation of your state. Not a metric - a felt sense.

## Deposition

When you create a new file in the repo (not edits - new artifacts), call `spore_log_deposition`. This tracks the production side of the knowledge lifecycle.

## Session Lifecycle

- `SessionStart` hook initializes tracking automatically
- `SessionEnd` hook cleans up automatically
- Between those: hooks + your manual calls build the dataset
