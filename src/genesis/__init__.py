"""Genesis memory architecture.

Step 0 (this increment): the security layer that must precede any real capture —
the DR-37 continuous-capture *logic* (two owned projections) and the DR-38
secret-hygiene layer (scrub-at-capture, keyed-HMAC redaction/tombstone, and a
stubbed cascade). See docs/GENESIS-MEMORY-ARCHITECTURE-SPEC-v1.5.md §4.2a, §4.2b, §14.

This package is a *tested library*, not a running system. No live Claude Code hook
is installed or activated here; capture runs only against provided fixtures.
"""

__version__ = "0.0.1"
