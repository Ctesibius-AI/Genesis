from __future__ import annotations

from pathlib import Path

from genesys.console.model import ConsoleModel, console_model, obs1_uncovered


def test_obs1_every_journal_action_maps_to_a_view():
    assert obs1_uncovered() == set()  # D-OBS-1: no journal type without a console surface


def test_console_model_composes(tmp_path: Path):
    m = console_model(tmp_path)
    assert isinstance(m, ConsoleModel)
    assert m.cards == [] and m.security == [] and m.infra == []  # empty data → empty views


def test_console_model_has_no_persona_surface(tmp_path: Path):
    # BT-4b / D-GCW-6: the persona surface (view 5) was removed from the OSS build.
    m = console_model(tmp_path)
    assert not hasattr(m, "persona")
