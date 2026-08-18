"""genesys.hooks — Claude Code hook adapter (go-live Step 1).

Glue that lets Claude Code hooks drive the Genesys capture pipeline.
See genesys.hooks.adapter for dispatch logic and genesys.hooks.cli for the
entry-point. genesys.hooks.translate converts Claude Code .jsonl transcript
records into Genesys capture event dicts.

Spec references: F-GENESYS-03 (save ritual / provisional jot), DR-08 (SessionStart
injection), DR-14 (PreCompact flush durability).
"""

from __future__ import annotations
