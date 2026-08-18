"""DR-38 secret hygiene & redaction (spec v1.5 §4.2b).

Three mechanisms, all *before the first byte hits disk*:

1. ``scrubber`` — scrub-at-capture: deterministic pattern + high-entropy detection,
   with the R3 entropy allowlist (git SHAs / Genesys IDs / tombstone hashes are
   exempt). Matches become a typed placeholder ``<redacted:secret kind=… hash=…>``.
2. ``redaction`` — the redaction verb: tombstone-in-place with a *keyed* HMAC (R4),
   not a plain sha256 oracle.
3. ``cascade`` — R2 cascade to derived graph copies. STUBBED in this increment: the
   graph engine does not exist yet. Clear typed interface + TODO; it does not fake work.
"""

from genesys.scrub.scrubber import (
    ScrubResult,
    ScrubMatch,
    scrub_text,
)
from genesys.scrub.redaction import (
    Tombstone,
    redact_in_place,
    tombstone_hash,
)
from genesys.scrub.cascade import (
    CascadeStub,
    CascadeNotImplementedError,
)

__all__ = [
    "ScrubResult",
    "ScrubMatch",
    "scrub_text",
    "Tombstone",
    "redact_in_place",
    "tombstone_hash",
    "CascadeStub",
    "CascadeNotImplementedError",
]
