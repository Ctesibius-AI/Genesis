"""Graphiti telemetry off-switch — Genesis zero-phone-home posture.

Graphiti ships usage telemetry to PostHog (us.i.posthog.com) ON BY DEFAULT.
`real_client` sets `GRAPHITI_TELEMETRY_ENABLED=false` BEFORE graphiti_core is
imported/initialized, so no manufacturer phone-home occurs regardless of how
Genesis is launched. These run OFFLINE: the env-set precedes the lazy graphiti
import, so it is honoured even when graphiti_core is absent (the offline sandbox).
"""

from __future__ import annotations

import os


def test_real_client_sets_telemetry_off(monkeypatch):
    monkeypatch.delenv("GRAPHITI_TELEMETRY_ENABLED", raising=False)
    from genesis.graph.factory import real_client

    # Offline: graphiti_core absent → real_client raises RuntimeError. The telemetry
    # off-switch is set FIRST (before the lazy import), so it is applied regardless.
    try:
        real_client()
    except Exception:
        pass

    assert os.environ.get("GRAPHITI_TELEMETRY_ENABLED") == "false"


def test_explicit_telemetry_choice_is_respected(monkeypatch):
    # setdefault must never clobber a deliberate override.
    monkeypatch.setenv("GRAPHITI_TELEMETRY_ENABLED", "true")
    from genesis.graph.factory import real_client

    try:
        real_client()
    except Exception:
        pass

    assert os.environ.get("GRAPHITI_TELEMETRY_ENABLED") == "true"
