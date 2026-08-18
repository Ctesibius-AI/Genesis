"""Project a ledger entry's links into typed episode edges (spec §4.6, D-SPINE-4).

The ledger is authoritative for links (DR-15/DR-36); the graph typed edge is a *rebuildable
projection* of `entry.links` — "Realized as Graphiti typed edges … no bespoke relationship
graph" (D-SPINE-4). This module reads `entry.links` and emits one typed edge per link through
`GraphEngine.link_episode(src, dst, label)`. It NEVER mutates the ledger (read-only).

DR-09: it projects only links already set on the entry (populated by lookback+backfill over
prior entries at save/drain) — it never reads or waits on a future entry.

⚠ §4.6 saga-label caveat: the constants below are Genesys-side strings. The literal Graphiti
binding (`HAS_EPISODE`/`NEXT_EPISODE`/`previous_episode_uuids`) is version-sensitive and is
verified at the FalkorDB integration boundary, not offline (same posture as the P3.5 client).
`session_id` is the saga container (`HAS_EPISODE`), handled by the graph's episode ingest — it
is deliberately NOT projected as a Genesys typed edge.
"""

from __future__ import annotations

from genesys.graph.engine import GraphEngine
from genesys.ledger.entry import LedgerEntry

PREV = "PREV_ENTRY"
NEXT = "NEXT_ENTRY"
CONTINUES = "CONTINUES"
REFERENCES = "REFERENCES"
SAME_TOPIC = "SAME_TOPIC"
SUPERSEDES = "SUPERSEDES"
CAUSED_BY = "CAUSED_BY"


def project_entry_links(entry: LedgerEntry, engine: GraphEngine) -> int:
    """Emit one typed episode edge per populated link on `entry`; return the edge count."""
    src = entry.entry_id
    links = entry.links
    count = 0
    for target, label in ((links.prev, PREV), (links.next, NEXT), (links.continues, CONTINUES)):
        if target is not None:
            engine.link_episode(src, target, label)
            count += 1
    for targets, label in ((links.references, REFERENCES), (links.same_topic, SAME_TOPIC),
                           (links.supersedes, SUPERSEDES), (links.caused_by, CAUSED_BY)):
        for target in targets:
            engine.link_episode(src, target, label)
            count += 1
    return count
