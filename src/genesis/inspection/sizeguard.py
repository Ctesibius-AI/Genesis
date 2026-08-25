"""Size guard for Tier 1 (spec §3/§4).

Large windows (backfill, long manual saves, precompact) are too big to screen cheaply. Per §3
the options are "chunk, or route straight to Tier 2." This build takes the route-to-Verifier
arm — deterministic and simple: a window over max_chars skips the Screen and goes to Opus. The
threshold is a config value (LadderConfig.max_window_chars), never a literal in the hot path.
"""

from __future__ import annotations


def size_route(window: str, *, max_chars: int) -> str:
    """"screen" if the window fits Sonnet's screen budget, else "verifier" (route to Tier 2)."""
    return "verifier" if len(window) > max_chars else "screen"
