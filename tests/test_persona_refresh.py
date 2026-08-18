from __future__ import annotations

import pytest

from genesys.journal.journal import read_journal
from genesys.persona.anchors import Sample, ValueAnchor
from genesys.persona.constitution import CategorizedAnchor
from genesys.persona.perceives import PerceivesEdge
from genesys.persona.refresh import FakeDrafter, draft_constitution, ratify


def _item(name, quote, cat="Values", directive="d"):
    v = ValueAnchor(name=name, articulations=[Sample(provenance="EP-1", valid_at="t",
                                                     quote=quote, author="stated")])
    return CategorizedAnchor(v, cat, directive)


def test_draft_rejects_perceives_input():
    with pytest.raises(TypeError):
        draft_constitution(FakeDrafter(), [PerceivesEdge(to="Trait:rigor")])


def test_draft_passes_through_ordinary_items():
    items = [_item("Value:honesty", "true")]
    assert draft_constitution(FakeDrafter(), items) == items


def test_ratify_compiles_and_journals(tmp_path):
    items = [_item("Value:honesty", "tell me what's true")]
    lines = ratify(tmp_path, ts="2026-08-17T10:00:00Z", ratified_items=items)
    assert len(lines) == 1 and lines[0].gr_ref == "Value:honesty"
    entries = [e for e in read_journal(tmp_path) if e.action == "constitution-refresh"]
    assert len(entries) == 1 and entries[0].author == "principal"
    assert 'gr:Value:honesty' in entries[0].after["lines"][0]
