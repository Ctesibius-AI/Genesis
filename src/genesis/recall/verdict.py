"""DR-33 verdict-aware serving (spec §4.7a, §4.7b).

`confirmed` = truth · `provisional`/`[unverified]` = served labelled · `quarantined` = never
served as truth · `contested` = never served without its contest. A pure gate over a GraphEdge;
recall applies it before ranking/scoring so quarantined facts never reach a result.
"""

from __future__ import annotations

from genesis.graph.engine import GraphEdge, Verdict


def is_servable(edge: GraphEdge) -> bool:
    return edge.verdict != Verdict.QUARANTINED


def serving_label(edge: GraphEdge) -> str:
    if edge.contested:
        return "[contested]"
    if edge.verdict == Verdict.PROVISIONAL:
        return "[unverified]"
    return ""


def servable_edges(edges: list[GraphEdge]) -> list[GraphEdge]:
    return [e for e in edges if is_servable(e)]
