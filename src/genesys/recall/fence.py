"""Recall persona read-fence — a CALL into the built P6 lock/leakcheck (spec §8.6 S2, V-1a).

Load-bearing (design §2): every recall read is a persona-filtered read. This module does NOT
re-derive the filter — it applies the built P6 predicates at the graph-edge layer where recall
reads. Non-perceived edges (facts, self-view) are always kept. A perceived-of-principal edge
reaches context ONLY when the session ReleaseContext is open AND covers its anchor (the same
`covers` gate as persona.lock.visible_perceived); fail-closed on None/closed. Served perceived
anchors are then run through assert_no_unkeyed_leak (V-1a). Recall never consults her opinion
of the principal from the perception department (R-M): opinion_edges_for_recall wraps
for_task_read, which returns [] for subject == PRINCIPAL.
"""

from __future__ import annotations

from genesys.graph.engine import GraphEdge
from genesys.persona.department import PerceptionDepartment
from genesys.persona.leakcheck import assert_no_unkeyed_leak
from genesys.persona.lock import for_task_read
from genesys.persona.perceives import PRINCIPAL
from genesys.persona.release import ReleaseContext, covers

PERCEIVES_CLASS = "perceives"


def perceives_anchor(edge: GraphEdge) -> str | None:
    """The anchor a perceived-of-principal graph edge is about, else None.

    The graph tags perceived edges C3/C4 with class_="perceives" (§9.4/R-N). For a plain fact
    (class_ != "perceives") this returns None and the edge is always kept.
    """
    if edge.class_ == PERCEIVES_CLASS:
        return edge.fact  # the anchor the perceived edge is about
    return None


def fence_edges(edges: list[GraphEdge], ctx: ReleaseContext | None, *,
                allowed_anchors: set[str] | None = None) -> tuple[list[GraphEdge], list[str]]:
    """Keep facts always; keep a perceived-of-principal edge only if ctx covers its anchor.

    Returns (kept_edges, served_perceived_anchors) and asserts V-1a (no unkeyed leak).
    Fail-closed: ctx None/closed, or an anchor not in open_anchors, drops the perceived edge.
    """
    kept: list[GraphEdge] = []
    served: list[str] = []
    for edge in edges:
        anchor = perceives_anchor(edge)
        if anchor is None:
            kept.append(edge)  # plain fact / self-view — always kept
            continue
        if covers(ctx, anchor) and (allowed_anchors is None or anchor in allowed_anchors):
            kept.append(edge)
            served.append(anchor)
        # else: fail-closed drop
    assert_no_unkeyed_leak(served, ctx)  # V-1a — raises if any served anchor is unkeyed
    return kept, served


def opinion_edges_for_recall(dept: PerceptionDepartment, ctx: ReleaseContext | None) -> list:
    """R-M: recall never consults her opinion of the principal — always []."""
    return for_task_read(dept, ctx, subject=PRINCIPAL)
