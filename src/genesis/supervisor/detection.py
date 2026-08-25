"""Post-commit detection — D-SUP-1 (spec §8.1).

`AddEpisodeResults` exposes no invalidations (F-GENESIS-11), so after each add_episode the
Supervisor queries the graph: creations one-hop from the episode; invalidations by
`expired_at` within the commit window (attribution-by-exclusivity on the serial lane).
"""

from __future__ import annotations

from dataclasses import dataclass

from genesis.graph.engine import GraphEdge, GraphEngine


@dataclass
class Detection:
    created: list[GraphEdge]
    invalidated: list[GraphEdge]


def detect(engine: GraphEngine, episode_id: str, commit_start: str, commit_end: str) -> Detection:
    return Detection(
        created=engine.created_in_episode(episode_id),
        invalidated=engine.invalidated_in_window(commit_start, commit_end),
    )
