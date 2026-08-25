"""Genesis WAL — rolling append-only capture record (spec §2.1, DR-24 revised, DR-37).

The vault becomes a write-ahead log: TWO parallel append-only projection records per data
root — memory-grade (clean; the pipeline reads this) and flight-recorder (full incl. thinking;
QA-only) — each SEGMENTED PER-DAY (the journal/ledger-month pattern). The records are
Genesis-owned and PERMANENT (CS1): NOT subject to the harness's 30-day transcript cleanup;
the owner prunes explicitly (no auto-rotation here). The courier appends the delta to both on
each ring, SCRUBBING AT APPEND before the first byte hits disk (DR-38 — position FROZEN).
A save is a ledger annotation over these records, not a copy (§2.2, DR-43).
"""

from __future__ import annotations
