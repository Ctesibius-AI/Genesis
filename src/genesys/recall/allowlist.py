"""Recall leak-guard = the CLOSED allow-list (D-GCW-7, replaces the fail-open persona fence).

Fail-closed: a served edge is kept ONLY if its relation `type` is one of the 8 named memory
relations (the single source is `graph.ontology.ALLOWED_EDGE_TYPES`). An untyped / generic /
`perceives` edge has a type outside the list and is EXCLUDED — the exact case the old fence let
through. Drops are COUNTED (AC-DROP1): a memory tool must not lose memory invisibly, so the caller
can see the exclusion rate and judge whether the 8-relation list is too narrow (A-GCW-13).
"""

from __future__ import annotations

from genesys.graph.engine import GraphEdge
from genesys.graph.ontology import ALLOWED_EDGE_TYPES


def is_allowed(edge: GraphEdge) -> bool:
    """True iff the edge's relation type is in the closed allow-list. Fail-closed on None/unknown."""
    return edge.type in ALLOWED_EDGE_TYPES


def filter_allowed(edges: list[GraphEdge]) -> tuple[list[GraphEdge], int]:
    """Return (kept, dropped_count): keep only allow-listed edges; count the exclusions (AC-DROP1)."""
    kept: list[GraphEdge] = []
    dropped = 0
    for e in edges:
        if is_allowed(e):
            kept.append(e)
        else:
            dropped += 1
    return kept, dropped
