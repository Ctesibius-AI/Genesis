from __future__ import annotations

from pathlib import Path

from genesys.console.model import ConsoleModel, console_model, obs1_uncovered
from genesys.console.persona import PersonaSurface
from genesys.journal.journal import JOURNAL_ACTIONS


def test_obs1_every_journal_action_maps_to_a_view():
    assert obs1_uncovered() == set()  # D-OBS-1: no journal type without a console surface


def test_console_model_composes(tmp_path: Path):
    m = console_model(tmp_path)
    assert isinstance(m, ConsoleModel)
    assert m.cards == [] and m.security == [] and m.infra == []  # empty data → empty views


def test_console_model_carries_persona_surface(tmp_path: Path):
    m = console_model(tmp_path)
    assert isinstance(m.persona, PersonaSurface)
    # empty data -> all four sub-surfaces honest-empty
    assert m.persona.fact_conflicts == [] and m.persona.perceived == []
    assert m.persona.discussion_requests == [] and m.persona.release_log == []
