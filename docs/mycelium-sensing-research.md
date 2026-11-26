# Research proposal: Spore as a sensing precedent for Mycelium

2026-11-25 | Proposed, not implemented.

Existing Spore init adapts to repository topology; hooks log retrieval; decay.py computes min(2, 1 + .1(n-1)) * exp(-.03t) by default; graph.py weights co-retrieval by shared sessions with decay since last co-retrieval and excludes sessions above the distinct-file cap. Analysis is invoked explicitly; proposals do not move/delete files. Existing importance overrides and controller-facing signal work (#2) are relevant.

Generalization belongs in Mycelium, not an OS manager inside Spore. Explore a versioned, read-only, privacy-minimized signal adapter for retrieval strength, affinity, resource spend, outcome/rework and sample confidence. Raw file paths and session content stay local by default; sharing requires explicit scope. Distinguish observed tool success, kept artifact and independently verified outcome. Frequency is not value; protected low-use documents must not decay into removal. No authority elevation or auto-install from a signal. Avoid duplicate instrumentation; coordinate with #2.

Evaluate against held-out workflows, sparse samples, repeated failures, broad scans and critical rare tasks. Report missing data and false positives. Current evidence is single-practitioner; no generality or machine-wide adaptation claim. See [RFC 0002](https://github.com/dakotafabro/mycelium/blob/main/rfcs/0002-substrate-adaptation.md).
