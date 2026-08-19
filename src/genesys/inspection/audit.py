"""Sampling audit + Screen false-pass control chart (spec §3; CS2).

A random 5% (LadderConfig.audit_rate default; NOT a literal) of PASSED commits is routed to the
Verifier — cheap insurance against lenient Screen drift that a flag-only Screen never catches.
Audits are ALWAYS adjudicated by the top tier (Opus Verifier). The RNG is INJECTED (a seeded
random.Random) so the sampling decision is deterministic in tests — no global Math.random-style
nondeterminism. The FalsePassChart is the control chart on the Screen false-pass rate: when an
audit UPHOLDS a flag on a commit the Screen had PASSED, that is a Screen false pass.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


def should_audit(rng: random.Random, *, rate: float) -> bool:
    """True iff this passed commit is drawn for a sampling audit (injected RNG => deterministic)."""
    return rng.random() < rate


@dataclass
class FalsePassChart:
    passes: int = 0          # commits the Screen PASSED
    false_passes: int = 0    # of those, ones an audit later UPHELD (Screen was wrong to pass)

    def record_pass(self) -> None:
        self.passes += 1

    def record_false_pass(self) -> None:
        self.false_passes += 1

    def false_pass_rate(self) -> float:
        return self.false_passes / self.passes if self.passes else 0.0

    def breached(self, threshold: float) -> bool:
        return self.passes > 0 and self.false_pass_rate() > threshold
