"""Test alignment (Clerk diff §9.2) + persona journal emitters."""

from __future__ import annotations

from genesys.journal.journal import read_journal
from genesys.persona.alignment import (
    Alignment,
    align,
    journal_alignment,
    journal_perceive,
)
from genesys.persona.anchors import Sample
from genesys.persona.perceives import PerceivesEdge, PerceivesSample


def _perceived(n):
    return PerceivesEdge(to="Trait:rigor", samples=[
        PerceivesSample(anchor="Trait:rigor", episode=f"EP-{i}", valid_at="t") for i in range(n)])


def test_aligned_when_both_speak():
    a = align("Trait:rigor", [Sample(provenance="EP-1", valid_at="t")], _perceived(2))
    assert a.status == "aligned" and a.magnitude == 1


def test_divergent_when_one_side_silent():
    a = align("Trait:rigor", [], _perceived(2))
    assert a.status == "divergent" and a.magnitude == 2
    b = align("Trait:rigor", [Sample(provenance="EP-1", valid_at="t")], None)
    assert b.status == "divergent" and b.magnitude == 1


def test_journal_perceive_and_alignment(tmp_path):
    journal_perceive(tmp_path, ts="2026-08-17T10:00:00Z", anchor="Trait:rigor", episode="EP-1")
    journal_alignment(tmp_path, ts="2026-08-17T23:00:00Z", day="2026-08-17",
                      alignment=Alignment(anchor="Trait:rigor", status="divergent", magnitude=2))
    actions = [e.action for e in read_journal(tmp_path)]
    assert actions == ["perceive", "alignment"]
    align_entry = [e for e in read_journal(tmp_path) if e.action == "alignment"][0]
    assert align_entry.after["status"] == "divergent" and align_entry.author == "supervisor"
