"""Tests for the rendered QA-console dashboard (spec §14 D-QA-7).

BT-4b / D-GCW-6: the persona surface (view 5) was removed from the OSS build with the persona
profiler. These tests assert it is gone from the rendered dashboard — no container, no JS render,
no persona data hooks.
"""

from __future__ import annotations

from genesis.console.dashboard import DASHBOARD_HTML


def test_dashboard_has_no_persona_surface_container():
    assert 'id="personaSurface"' not in DASHBOARD_HTML
    assert "m.persona" not in DASHBOARD_HTML


def test_dashboard_has_no_persona_data_hooks():
    for hook in ('id="factConflicts"', 'id="perceived"', 'id="discussionRequests"', 'id="releaseLog"'):
        assert hook not in DASHBOARD_HTML


def test_dashboard_still_renders_core_surfaces():
    # the non-persona surfaces are untouched
    for hook in ('id="security"', 'id="infra"'):
        assert hook in DASHBOARD_HTML
