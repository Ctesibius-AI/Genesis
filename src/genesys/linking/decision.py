"""The Supervisor's supersession/causal decision for one episode (spec §8.2, §4.9).

A pure value object carried from the judgment surface (live worker / QA console / test) into
`genesys.linking.supersession.apply_supersession`. The *decision* of what supersedes/causes
what is the Supervisor's (LLM judgment, §8); the *execution* is deterministic code. This
carrier keeps the two decoupled and lets "no supersession" be a first-class honest-empty state.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SupersessionDecision:
    superseded_entry_ids: list[str] = field(default_factory=list)
    superseded_edge_ids: list[str] = field(default_factory=list)
    caused_by: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.superseded_entry_ids or self.superseded_edge_ids or self.caused_by)
