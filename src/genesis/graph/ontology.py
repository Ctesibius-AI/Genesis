"""Memory-only ontology (D-GCW-14) — the single source that doubles as the recall allow-list.

Name once, use twice (D-GCW-14 / A-GCW-13): the entity set + the 8 named relations defined here are
(1) the typed feed passed to graphiti's `add_episode` (entity_types + edge_type_map, so the graph
promotes typed nodes instead of generic `Entity`, AC-G1) and (2) the CLOSED recall allow-list the
leak-guard enforces (D-GCW-7, fail-closed — `recall.allowlist` imports `ALLOWED_EDGE_TYPES` from HERE).

This module is offline-safe: it declares the ontology as plain data (no graphiti/pydantic import at
module load, so the offline suite reaches it). The graphiti-native structures (pydantic entity models,
graphiti `edge_type_map`) are built lazily by `build_entity_types()` / `build_edge_type_map()` and are
reached only on the live graph path. `DECIDED_BY` is deferred to fast-follow (D-GCW-14), deliberately
absent from the closed list.
"""

from __future__ import annotations

# The 7 memory entity types (design §7). "Session" is an episodic node, not an entity type.
ENTITY_TYPES: tuple[str, ...] = (
    "Person", "Organization", "Project", "Task", "Decision", "Artifact", "Agent",
)

# The 8 named relations, each: relation -> (source entity types, target entity types) (design §7).
# The KEYS are the closed recall allow-list; the endpoints shape the graphiti edge_type_map.
EDGE_DEFINITIONS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "WORKS_ON":        (("Person",),           ("Project",)),
    "MEMBER_OF":       (("Person",),           ("Organization",)),
    "ASSIGNED":        (("Person",),           ("Task",)),
    "BLOCKS":          (("Task",),             ("Task",)),
    "PART_OF":         (("Task", "Artifact"),  ("Project",)),
    "ABOUT":           (("Decision",),         ("Project", "Artifact", "Task")),
    "PRODUCED":        (("Agent", "Person"),   ("Artifact",)),
    "PARTICIPATED_IN": (("Agent", "Person"),   ("Session",)),
}

# The CLOSED recall allow-list (D-GCW-7). No generic / RELATES_TO catch-all — fail-closed: any edge
# whose type is not one of these is excluded from recall (accepted, counted memory-loss; AC-DROP1).
ALLOWED_EDGE_TYPES: frozenset[str] = frozenset(EDGE_DEFINITIONS)


def build_entity_types() -> dict:  # pragma: no cover - live graph path (needs pydantic/graphiti)
    """Build graphiti-core `entity_types` (name -> pydantic BaseModel) from ENTITY_TYPES.

    Lazy: imports pydantic INSIDE the function so the offline suite never reaches it. Each entity
    type is an empty typed model — graphiti classifies nodes into these labels (typed-node fix #2).
    """
    from pydantic import BaseModel, create_model

    return {name: create_model(name, __base__=BaseModel) for name in ENTITY_TYPES}


def build_edge_type_map() -> dict:  # pragma: no cover - live graph path
    """Build graphiti-core `edge_type_map`: (source_label, target_label) -> [relation names].

    Derived from EDGE_DEFINITIONS so the allow-list and the feed can never drift (name once).
    """
    mapping: dict[tuple[str, str], list[str]] = {}
    for rel, (sources, targets) in EDGE_DEFINITIONS.items():
        for s in sources:
            for t in targets:
                mapping.setdefault((s, t), []).append(rel)
    return mapping


def build_edge_types() -> dict:  # pragma: no cover - live graph path
    """Build graphiti-core `edge_types` (relation name -> pydantic BaseModel).

    CRITICAL (live-verified 2026-08-26): `edge_type_map` alone is only a HINT — without the edge
    MODELS graphiti's extraction invents variant names (ASSIGNED_TASK_TO, IS_ABOUT, CONTAINS…),
    which the closed recall allow-list then over-excludes (silent memory loss). Passing `edge_types`
    constrains extraction to EXACTLY the 8 named relations, so the emitted names match the allow-list.
    """
    from pydantic import BaseModel, create_model

    return {rel: create_model(rel, __base__=BaseModel) for rel in EDGE_DEFINITIONS}
