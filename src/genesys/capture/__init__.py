"""DR-37 continuous curated capture — the two owned projections (spec v1.5 §4.2a).

Step 0 scope: the *logic* that turns transcript events into the two projections
(flight recorder + memory-grade), applies the DR-38 scrubber before write, and excludes
Anthropic system prompts + harness plumbing.

⚠ NOT in scope for this increment: installing or activating any live Claude Code hook,
or running capture against a real transcript. Activation is a separate deploy step that
needs the owner's explicit go-ahead. The CLI operates only on provided fixtures.
"""

from genesys.capture.mirror import (
    TranscriptEvent,
    Projection,
    ProjectionKind,
    CaptureResult,
    mirror_events,
    HARNESS_EXCLUDED_TYPES,
)

__all__ = [
    "TranscriptEvent",
    "Projection",
    "ProjectionKind",
    "CaptureResult",
    "mirror_events",
    "HARNESS_EXCLUDED_TYPES",
]
