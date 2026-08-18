"""Real GraphitiClient factory + version-drift canary (spec §4.9a, §8.1 QA #6, DR-35).

graphiti-core and falkordblite are imported lazily INSIDE these functions — the offline
sandbox has neither (no network, no libomp). `real_client` wires FalkorDB Lite (dev) or a
FalkorDB server from env (prod). `assert_transaction_time_in_window` is the CI canary: it fails
the build if a pinned-Graphiti upgrade stops stamping transaction-time inside the Genesys
commit window, which would silently break post-commit invalidation attribution (F-11).
"""

from __future__ import annotations

import os
from typing import Mapping


def real_client(*, db_path: str | None = None, env: Mapping[str, str] | None = None):
    """Return a live GraphitiCoreClient backed by graphiti-core + embedded FalkorDB.

    graphiti_backend is imported lazily here — the offline sandbox (system Python 3.9,
    no graphiti-core) never reaches this import (spec §4.9a, DR-35).
    """
    env = env if env is not None else os.environ
    # Zero manufacturer phone-home from the memory layer: Graphiti ships usage telemetry to
    # PostHog (us.i.posthog.com) ON BY DEFAULT. Set the off-switch BEFORE graphiti_core is
    # imported/initialized so it's honored regardless of how Genesys is launched. Uses
    # setdefault so an explicit GRAPHITI_TELEMETRY_ENABLED override (if ever wanted) still wins.
    os.environ.setdefault("GRAPHITI_TELEMETRY_ENABLED", "false")
    try:
        import graphiti_core  # noqa: F401  (lazy — absent in the offline sandbox)
        # falkordblite installs its modules under 'redislite'; check that
        import redislite  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised only where extra is absent
        raise RuntimeError(
            "the 'graph' extra is required for a real client: pip install '.[graph]'"
        ) from exc
    # Lazy import: only reached when graphiti-core is present (venv, not offline suite)
    from genesys.graph.graphiti_backend import build_graphiti_client  # noqa: PLC0415
    return build_graphiti_client(db_path=db_path, env=env)


def assert_transaction_time_in_window(client, *, now) -> None:  # pragma: no cover - integration
    """Canary: a real add_episode must stamp expired_at inside this writer's commit window."""
    from genesys.graph.adapter import GraphitiEngine
    from genesys.graph.client import CommitMarker

    eng = GraphitiEngine(client, marker=CommitMarker(), clock=now)
    eng.add_episode("canary-ep", "canary body")
    start, end = eng.window_for("canary-ep")
    inv = eng.invalidated_in_window(start, end)
    assert inv, "version drift: no expired edge attributed inside the Genesys commit window"
    for e in inv:
        assert start <= (e.expired_at or "") <= end, (
            f"version drift: expired_at {e.expired_at} outside commit window [{start}, {end}]"
        )
