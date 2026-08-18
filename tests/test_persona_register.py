from __future__ import annotations

from genesys.persona.perceives import PerceivesEdge, PerceivesSample, annotate_dispute
from genesys.persona.register import Voicing, voice_opinion, voice_or_silent
from genesys.persona.release import ReleaseContext, closed


def _edge(disputed=False, n=2):
    e = PerceivesEdge(to="Trait:rigor", band="leans rigorous",
                      samples=[PerceivesSample(anchor="Trait:rigor", episode=f"EP-{i}", valid_at="t")
                               for i in range(n)])
    if disputed:
        annotate_dispute(e, reason="he pushed back", reason_ref="DR-1")
    return e


def test_locked_is_honest_empty():
    v = voice_opinion(_edge(), None)
    assert v.spoken is False and v.text is None
    assert voice_opinion(_edge(), closed()).spoken is False
    assert voice_or_silent(_edge(), None) == ""


def test_open_and_covered_voices_as_opinion():
    ctx = ReleaseContext(open=True, open_anchors=["Trait:rigor"])
    v = voice_opinion(_edge(), ctx)
    assert v.spoken is True and v.text is not None
    assert "Trait:rigor" in v.text
    assert v.evidence_available == 2
    # framed as opinion, never as fact/his-persona
    assert "not fact" in v.text.lower()


def test_open_but_uncovered_anchor_is_locked():
    ctx = ReleaseContext(open=True, open_anchors=["Trait:other"])
    assert voice_opinion(_edge(), ctx).spoken is False  # anchor not covered → locked


def test_disputed_is_disclosed_and_flagged():
    ctx = ReleaseContext(open=True, open_anchors=["Trait:rigor"])
    v = voice_opinion(_edge(disputed=True), ctx)
    assert v.spoken is True and v.disputed is True
    assert "disputed" in v.text.lower()
