"""genesis.hooks — Claude Code hook adapter (go-live Step 1).

Glue that lets Claude Code hooks drive the Genesis capture pipeline.
See genesis.hooks.adapter for dispatch logic and genesis.hooks.cli for the
entry-point. genesis.hooks.translate converts Claude Code .jsonl transcript
records into Genesis capture event dicts.

Spec references: F-GENESIS-03 (save ritual / provisional jot), DR-08 (SessionStart
injection), DR-14 (PreCompact flush durability).
"""

from __future__ import annotations
