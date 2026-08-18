"""The perceives edge — the perceived-view (spec §9.1, App A.2, Fence 4).

Daimon's opinion of the principal, held on `Agent:Daimon —[perceives]→ Trait/Value`. The
fixed fields (type/from/author/perceiver/verdict/lock) are structural: `verdict` is
`provisional` PERMANENTLY (Fence 4 — no count ever promotes it). Dispute is annotation-only
and scrubbed. `subject` scopes the owner-only lock (R-L).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from genesys.config import get_assistant_name, get_principal
from genesys.scrub.scrubber import scrub_text

# Identity is config-driven (owner-agnostic engine). We keep module-level constants
# for import compatibility — everything imports ``PRINCIPAL`` / ``DAIMON`` from here —
# but source their values from config (env var → setup config file → generic default)
# rather than hardcoding an owner name. The persona read-fence keys on ``PRINCIPAL``,
# so it works with whatever the install configured.
_ASSISTANT = get_assistant_name()
DAIMON = f"Agent:{_ASSISTANT}"
PERCEIVER = _ASSISTANT
PRINCIPAL = get_principal()


@dataclass
class PerceivesSample:
    anchor: str
    episode: str
    valid_at: str
    observation: str = ""


def _default_dispute() -> dict:
    return {"status": "none", "reason_ref": None}


@dataclass
class PerceivesEdge:
    to: str
    subject: str = PRINCIPAL
    samples: list[PerceivesSample] = field(default_factory=list)
    band: str = ""
    spread: str = ""
    verdict: str = "provisional"
    dispute: dict = field(default_factory=_default_dispute)

    # fixed structural fields (A.2)
    type: str = field(default="perceives", init=False)
    from_: str = field(default=DAIMON, init=False)
    author: str = field(default="inferred", init=False)
    perceiver: str = field(default=PERCEIVER, init=False)
    lock: str = field(default="default-locked", init=False)

    def __setattr__(self, name: str, value: object) -> None:
        if name == "verdict" and value != "provisional":
            raise ValueError("Fence 4: perceived verdict is permanently provisional")
        super().__setattr__(name, value)

    def __post_init__(self) -> None:
        assert_provisional(self)

    def strength(self) -> int:
        return len({s.episode for s in self.samples})


def assert_provisional(edge: PerceivesEdge) -> None:
    if edge.verdict != "provisional":
        raise ValueError(f"Fence 4: perceived verdict is permanently provisional, got {edge.verdict!r}")


def annotate_dispute(edge: PerceivesEdge, *, reason: str, reason_ref: str) -> None:
    edge.dispute = {"status": "disputed", "reason_ref": reason_ref,
                    "reason": scrub_text(reason).text}
