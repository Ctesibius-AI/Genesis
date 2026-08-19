"""Tier 0 deterministic pre-checks (spec §3, CS3): hard->route, soft->hints, zero-facts tripwire.

Pure/offline, NO LLM. A Tier 0 hit NEVER auto-quarantines.
"""
from __future__ import annotations

from genesys.graph.engine import GraphEdge
from genesys.inspection.tier0 import (
    Tier0Flag,
    Tier0Hint,
    Tier0Result,
    number_date_tokens,
    tier0_check,
    _ATTRIBUTION_STOPWORDS,
)

SPEAKERS = {"the principal", "Daimon"}


def _edge(eid: str, fact: str) -> GraphEdge:
    return GraphEdge(edge_id=eid, fact=fact, episodes=["EP-1"])


def test_number_date_tokens_extracts_numbers_and_dates():
    toks = number_date_tokens("invoice PHR008 for 1250 on 2026-05-31 at 40%")
    assert "1250" in toks and "2026-05-31" in toks and "40" in toks


def test_hard_flag_number_absent_from_window_and_ridealong():
    # The fact claims 1250 but neither window nor ride-along mentions it -> hard route.
    created = [_edge("e1", "the invoice was 1250 euros")]
    r = tier0_check(created, window="we talked about the invoice", ride_along="",
                    speakers=SPEAKERS)
    assert r.hard_flags == [Tier0Flag(edge_id="e1", kind="number_date_absent", token="1250")]
    assert r.routes() is True


def test_number_present_in_ridealong_is_not_flagged():
    # Grounding-over-completeness: the number is in the 3-episode ride-along -> not absent.
    created = [_edge("e1", "the invoice was 1250 euros")]
    r = tier0_check(created, window="we talked about the invoice",
                    ride_along="last month it was 1250", speakers=SPEAKERS)
    assert r.hard_flags == []


def test_hard_flag_attribution_to_a_non_participant():
    created = [_edge("e2", "Nikos said the deadline is fixed")]
    r = tier0_check(created, window="Nikos said the deadline is fixed", ride_along="",
                    speakers=SPEAKERS)  # Nikos is NOT in the speaker set
    assert Tier0Flag(edge_id="e2", kind="non_participant", token="Nikos") in r.hard_flags


def test_attribution_to_a_participant_passes():
    created = [_edge("e2", "the principal said the deadline is fixed")]
    r = tier0_check(created, window="the principal said the deadline is fixed", ride_along="",
                    speakers=SPEAKERS)
    assert r.hard_flags == []


def test_entity_not_verbatim_is_a_soft_hint_never_a_flag():
    created = [_edge("e3", "the project ships Friday")]
    r = tier0_check(created, window="he said it ships Friday", ride_along="",
                    speakers=SPEAKERS, entities={"e3": ["Genesys"]})
    assert r.hard_flags == []                       # never auto-routes
    assert r.hints == [Tier0Hint(edge_id="e3", entity="Genesys")]


def test_zero_facts_on_a_nontrivial_window_trips_the_completeness_wire():
    r = tier0_check([], window=" ".join(["word"] * 50), ride_along="", speakers=SPEAKERS)
    assert r.tripwire is True and r.hard_flags == [] and r.hints == []


def test_zero_facts_on_a_trivial_window_does_not_trip():
    r = tier0_check([], window="ok", ride_along="", speakers=SPEAKERS)
    assert r.tripwire is False


def test_result_never_exposes_a_quarantine_path():
    # Adversarial: use an edge whose fact has a number ABSENT from the window — a hard flag DOES
    # fire — yet the result still exposes no quarantine field/state (only hard_flags/hints/tripwire).
    created = [_edge("e", "the total was 9999 units")]
    r = tier0_check(created, window="we discussed the total", ride_along="", speakers=SPEAKERS)
    assert r.hard_flags  # hard flag fires (9999 absent from corpus)
    assert set(vars(r)) == {"hard_flags", "hints", "tripwire"}
    assert isinstance(r, Tier0Result)


# ---------------------------------------------------------------------------
# Fix 1: Entity-verbatim SOFT check — word-boundary, not substring
# ---------------------------------------------------------------------------

def test_entity_substring_in_corpus_fires_hint():
    # "Gene" is a substring of "Genesys" but NOT a standalone word -> hint fires (missed verbatim).
    created = [_edge("e4", "Gene will review the draft")]
    r = tier0_check(created, window="Genesys will review the draft", ride_along="",
                    speakers=SPEAKERS, entities={"e4": ["Gene"]})
    assert r.hints == [Tier0Hint(edge_id="e4", entity="Gene")]


def test_entity_whole_word_in_corpus_no_hint():
    # "Genesys" appears as a whole word in the corpus -> no hint.
    created = [_edge("e5", "Genesys will review the draft")]
    r = tier0_check(created, window="Genesys will review the draft", ride_along="",
                    speakers=SPEAKERS, entities={"e5": ["Genesys"]})
    assert r.hints == []


# ---------------------------------------------------------------------------
# Fix 2: Attribution STOPWORDS — function/temporal words must NOT hard-flag
# ---------------------------------------------------------------------------

def test_pronoun_attribution_does_not_hard_flag():
    # "He said hello" — "He" is a pronoun, not a party name.
    created = [_edge("e6", "He said hello")]
    r = tier0_check(created, window="He said hello", ride_along="", speakers=SPEAKERS)
    non_p_flags = [f for f in r.hard_flags if f.kind == "non_participant"]
    assert non_p_flags == []


def test_day_attribution_does_not_hard_flag():
    # "Monday told us" — "Monday" is a temporal word, not a party name.
    created = [_edge("e7", "Monday told us to prepare")]
    r = tier0_check(created, window="Monday told us to prepare", ride_along="", speakers=SPEAKERS)
    non_p_flags = [f for f in r.hard_flags if f.kind == "non_participant"]
    assert non_p_flags == []


def test_genuine_non_speaker_name_still_hard_flags():
    # "Zeus said X" — Zeus is NOT in speakers and NOT a stopword -> hard non_participant flag.
    created = [_edge("e8", "Zeus said the deadline is tomorrow")]
    r = tier0_check(created, window="Zeus said the deadline is tomorrow", ride_along="",
                    speakers=SPEAKERS)
    assert Tier0Flag(edge_id="e8", kind="non_participant", token="Zeus") in r.hard_flags


def test_listed_speaker_still_passes():
    # "the principal said X" — the principal is in speakers -> no flag (unchanged behavior).
    created = [_edge("e9", "the principal said the plan is ready")]
    r = tier0_check(created, window="the principal said the plan is ready", ride_along="",
                    speakers=SPEAKERS)
    non_p_flags = [f for f in r.hard_flags if f.kind == "non_participant"]
    assert non_p_flags == []


# ---------------------------------------------------------------------------
# Fix 3: number_date_tokens alphanumeric-code behavior + stopwords coverage
# ---------------------------------------------------------------------------

def test_alphanumeric_code_does_not_yield_embedded_standalone_token():
    # "PHR008" is an alphanumeric code; "008" should NOT appear as a standalone numeric token
    # because the digit sequence is preceded by alphabetic characters (not a word boundary start).
    assert "008" not in number_date_tokens("PHR008")


def test_stopwords_set_coverage():
    # All canonical stopword categories must be present: a pronoun, an article, a day, a month.
    assert "He" in _ATTRIBUTION_STOPWORDS
    assert "The" in _ATTRIBUTION_STOPWORDS
    assert "Monday" in _ATTRIBUTION_STOPWORDS
    assert "January" in _ATTRIBUTION_STOPWORDS
