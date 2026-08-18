"""Supersession + causal linking (spec §4.6, §8.2 rightful closure).

Supervisor-driven: the gate/judgment decides which prior entries/edges a new entry supersedes;
this records `supersedes`/`caused_by` on the entry (ledger truth) and projects the graph
`superseded_by` via the engine. Idempotent; never infers supersession on its own.
"""

from __future__ import annotations

from pathlib import Path

from genesys.graph.engine import GraphEngine
from genesys.ledger.entry import LedgerEntry


def _dedup_append(target: list[str], value: str) -> None:
    if value not in target:
        target.append(value)


def apply_supersession(data_root: Path, entry: LedgerEntry, engine: GraphEngine, *,
                       superseded_entry_ids: list[str],
                       superseded_edge_ids: list[str] | None = None,
                       caused_by: list[str] | None = None) -> None:
    for eid in superseded_entry_ids:
        _dedup_append(entry.links.supersedes, eid)
    for edge_id in superseded_edge_ids or []:
        engine.write_superseded_by(edge_id, entry.entry_id)
    for cid in caused_by or []:
        _dedup_append(entry.links.caused_by, cid)
