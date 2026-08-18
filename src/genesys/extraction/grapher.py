"""Grapher — feeds a prepared episode to the graph engine (spec §4.4, DR-25).

One save = one episode. Returns the engine's created edges (AddResult); invalidations are read
post-commit by the Supervisor (F-GENESYS-11), not here. `render_manifest` produces the fact list
the Screen compares against the jot.
"""

from __future__ import annotations

from genesys.extraction.analyst import Episode
from genesys.graph.engine import AddResult, GraphEngine


def run_grapher(engine: GraphEngine, episode: Episode) -> AddResult:
    return engine.add_episode(episode.episode_id, episode.content)


def render_manifest(result: AddResult) -> str:
    return "\n".join(f"{e.edge_id}: {e.fact}" for e in result.created)
