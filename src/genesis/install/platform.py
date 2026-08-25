"""Platform-conditional default profile (D-GCW-9 / AC-PLAT1).

The simple default (stdio + embedded FalkorDB Lite) has the HARDER platform floor: the Lite native
wheel needs macOS 15+/arm64 + libomp + Python 3.12 (A-GCW-11). "Self-contained" ≠ "portable". So the
installer PICKS: supported floor → stdio+Lite; unmet floor → the Docker (http+server) profile as the
portability path; neither → fail-loud with guidance. NEVER a broken stdio+Lite install.

`select_profile` is a pure decision (offline-tested); `detect_platform` reads the real host.
"""

from __future__ import annotations

from dataclasses import dataclass

STDIO_LITE = "stdio-lite"
DOCKER = "docker"


class PlatformError(RuntimeError):
    """Raised when neither the Lite floor is met nor a Docker fallback is available (fail-loud)."""


@dataclass(frozen=True)
class PlatformFacts:
    system: str            # e.g. "Darwin"
    macos_major: int | None  # major macOS version, or None off-mac
    arch: str              # e.g. "arm64"
    py: tuple[int, int]    # (3, 12)
    has_libomp: bool


def meets_lite_floor(facts: PlatformFacts) -> bool:
    """True iff the stdio+Lite native floor (D-GCW-9 / A-GCW-11) is satisfied."""
    return (
        facts.system == "Darwin"
        and (facts.macos_major or 0) >= 15
        and facts.arch == "arm64"
        and facts.py >= (3, 12)
        and facts.has_libomp
    )


def select_profile(facts: PlatformFacts, *, docker_available: bool) -> str:
    """Derive the deployment profile (AC-PLAT1): stdio-lite | docker | fail-loud.

    Supported floor → stdio+Lite. Unmet floor → Docker if available, else raise (never a broken
    stdio+Lite install).
    """
    if meets_lite_floor(facts):
        return STDIO_LITE
    if docker_available:
        return DOCKER
    raise PlatformError(
        "Genesis stdio+Lite needs macOS 15+/arm64 + libomp + Python 3.12, and no Docker fallback "
        "was found. Install Docker for the server profile, or run on a supported platform."
    )


def detect_platform() -> PlatformFacts:  # pragma: no cover - reads the real host
    import ctypes.util
    import platform as _p
    import sys

    system = _p.system()
    macos_major = None
    if system == "Darwin":
        rel = _p.mac_ver()[0].split(".")
        macos_major = int(rel[0]) if rel and rel[0].isdigit() else None
    has_libomp = ctypes.util.find_library("omp") is not None or ctypes.util.find_library("gomp") is not None
    return PlatformFacts(system=system, macos_major=macos_major, arch=_p.machine(),
                         py=(sys.version_info[0], sys.version_info[1]), has_libomp=has_libomp)
