"""Genesis inspection ladder — Tier 0/1/2 (spec §3, DR-44).

Replaces "Screen-on-jot -> flag -> Verifier" with a three-tier ladder over the raw window:
  Tier 0 — deterministic pre-checks (NEW; code, free, offline, unit-tested): number/date-token
           membership + non-participant attribution -> HARD (route to Tier 2, rare + near-certain);
           entity-not-verbatim -> SOFT hint for Tier 1 (never routes); zero-facts completeness
           tripwire. A Tier 0 hit NEVER auto-quarantines. Commissioned in SHADOW MODE first (CS3).
  Tier 1 — Screen-on-raw (Sonnet), grounded on read_window() output (+Tier 0 hints), flag-only,
           two-stage shape preserved; never a machine summary of the raw (§3 circularity ban).
  Tier 2 — Verifier (Opus), full adjudication + a random 5% sampling audit of PASSED commits
           (CS2) with a control chart on the Screen false-pass rate. Audits adjudicated by Opus.

Model tiers per §12 unchanged. Grounding-over-completeness: false facts compound; missed facts
are recoverable from the vault + the zero-facts tripwire. The deterministic spine is FROZEN —
this package is additive at the judgment layer only.
"""

from __future__ import annotations
