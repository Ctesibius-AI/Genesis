"""genesis.backfill — batch backfill injection door.

A THIN DRIVER over the existing capture pipeline (genesis.hooks.adapter.dispatch).
It feeds historical Claude Code .jsonl session transcripts through the SAME
SessionEnd path a live hook would use, injecting each session's OWN end timestamp
as the clock so episodes land on the bi-temporal baseline chronologically instead
of at wall-clock. No new transcript parsing lives here.

OFFLINE by construction: the SessionEnd dispatch path is model-free (backend only
matters for PreCompact). No network, no LLM. Extraction is NOT run here — backfill
only enqueues; the drain (genesis.extraction.live.run_once) is a separate step.
"""
