"""DR-38 mechanism (2), R2 cascade — STUBBED (spec v1.5 §4.2b, "Cascade to derived
copies (R2) — the largest gap").

A secret *stated in dialogue* gets extracted and then survives, after the truth file is
tombstoned, in up to five live derived copies:

    1. edge fact-text
    2. entity attributes
    3. embedding vectors
    4. FTS rows
    5. an enriched entry or diary line

Redaction must therefore CASCADE: tombstone the file → walk the episode provenance (the
deterministic episode ID indexes exactly which graph artifacts cite the poisoned span —
Graphiti episode provenance) → scrub/rewrite the citing edges, nodes, and derived views
→ reindex (deterministic grade, DR-26) → propagate to snapshots.

⚠ This increment (Step 0) is *file I/O + scrubbing only* — there is no graph engine,
no embeddings, no FTS, no snapshots yet. Faithfully to the build order, the cascade is
**stubbed with a clear typed interface**, not faked: calling it raises so no caller can
mistake a no-op for a completed cascade.

TODO(DR-38 R2 / cascade): implement once the graph engine + snapshots exist (spec §14
P1+). It must:
  - resolve the poisoned span's episode ID -> Graphiti episode provenance,
  - enumerate + scrub citing edges / entity attributes / enriched entries / diary lines,
  - purge/re-embed affected embedding vectors and FTS rows,
  - trigger a deterministic reindex (DR-26 grade-1),
  - re-write or purge affected permanent snapshots (retention math per DR-31).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


class CascadeNotImplementedError(NotImplementedError):
    """Raised when a cascade is requested before the graph engine exists (Step 0)."""


@dataclass(frozen=True)
class CascadeRequest:
    """Input to the R2 cascade: which tombstoned span to chase into derived copies."""

    episode_id: str  # deterministic Genesys episode ID indexing the poisoned span
    tombstone_hash: str  # keyed HMAC of the removed content (R4), for correlation
    reason: str
    actor: str


@dataclass(frozen=True)
class CascadeReport:
    """Result of a cascade run: which derived artifacts were scrubbed/reindexed.

    Defined now so the eventual implementation and its callers/tests have a stable,
    typed contract. Not produced by anything in Step 0.
    """

    edges_scrubbed: Sequence[str]
    nodes_scrubbed: Sequence[str]
    derived_views_scrubbed: Sequence[str]
    vectors_purged: int
    fts_rows_purged: int
    snapshots_rewritten: Sequence[str]
    reindexed: bool


class CascadeEngine(Protocol):
    """Typed interface the future graph-backed cascade must satisfy.

    Kept as a Protocol so Step 0 depends on the *shape*, not on any graph library.
    """

    def cascade(self, request: CascadeRequest) -> CascadeReport:
        ...


class CascadeStub:
    """The Step 0 cascade: a faithful stub that refuses to pretend.

    Implements the ``CascadeEngine`` shape but raises ``CascadeNotImplementedError`` on
    ``cascade`` — because the graph engine, embeddings, FTS and snapshots it must walk do
    not exist yet. This is deliberate (see module TODO): a silent no-op here would leave
    a redacted secret alive in derived copies while reporting success.
    """

    def cascade(self, request: CascadeRequest) -> CascadeReport:  # noqa: D401
        raise CascadeNotImplementedError(
            "DR-38 R2 cascade requires the graph engine / snapshots, which do not exist "
            "in this increment (Step 0). See genesys/scrub/cascade.py TODO(DR-38 R2). "
            f"Requested cascade for episode_id={request.episode_id!r}."
        )
