"""Tests for the rendered QA-console dashboard (spec §14 D-QA-7, view 5).

The dashboard is a single stdlib HTML string served at `/`. It renders `/api/model`,
which now carries `persona` (the four sub-surfaces). These tests assert the persona surface
is actually rendered — the audit gap this branch closes — and that its render is fenced:
the release-log render must never reach for opinion-content fields.
"""

from __future__ import annotations

from genesys.console.dashboard import DASHBOARD_HTML


def test_dashboard_has_persona_surface_container():
    # a rendered surface, not just a data route (§14 view 5 must be visible)
    assert 'id="personaSurface"' in DASHBOARD_HTML


def test_dashboard_renders_all_four_persona_sub_surfaces():
    html = DASHBOARD_HTML
    # the JS consumes m.persona and renders each sub-surface into its own hook
    assert "m.persona" in html
    assert 'id="factConflicts"' in html
    assert 'id="perceived"' in html
    assert 'id="discussionRequests"' in html
    assert 'id="releaseLog"' in html


def test_dashboard_perceived_panel_renders_both_records_and_notice():
    html = DASHBOARD_HTML
    # both records side-by-side + PT-7 notice on divergence (§10.1b)
    assert "self_samples" in html
    assert "perceived_strength" in html
    assert "notice" in html
    assert "alignment" in html


def test_dashboard_release_log_never_references_opinion_content_fields():
    html = DASHBOARD_HTML
    # release log shows lifecycle only — action + scope + close reason (§14, Security-view posture)
    assert "close_reason" in html
    assert "scope" in html
    # the fence: the release-log payload from /api/model carries no opinion/observation
    # content field at all, so there is nothing for the client to render or leak.
    assert "observation" not in html
    assert "opinion_content" not in html
    assert "opinion_text" not in html
