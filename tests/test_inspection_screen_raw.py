"""Tier 1 Screen-on-raw (spec §3/§4): grounds S1-S7 on the raw window, flag-only, Sonnet.

Fake backend only — asserts the reference is the raw window (NOT the jot) + fail-closed parse.
The built workers.screen.screen / SCREEN_PROMPT are untouched (a separate test guards that).
"""
from __future__ import annotations

from genesys.inspection.screen_raw import SCREEN_RAW_PROMPT, screen_raw
from genesys.inspection.tier0 import Tier0Hint
from genesys.workers.backend import TIER_SONNET, FakeLLMBackend
from genesys.workers.screen import SCREEN_PROMPT, ScreenResult


def test_prompt_grounds_on_the_raw_window_not_the_jot():
    assert "raw window" in SCREEN_RAW_PROMPT.lower()
    assert "machine summary" in SCREEN_RAW_PROMPT.lower()     # circularity ban stated
    assert "S1" in SCREEN_RAW_PROMPT and "S7" in SCREEN_RAW_PROMPT
    # The built jot prompt is a DIFFERENT object, left intact.
    assert SCREEN_RAW_PROMPT != SCREEN_PROMPT


def test_screen_raw_passes_the_raw_window_and_manifest_on_sonnet():
    b = FakeLLMBackend('{"verdict": "PASS", "flags": []}')
    r = screen_raw(b, window="the actual conversation text", manifest="e1: a fact")
    assert isinstance(r, ScreenResult) and r.verdict == "PASS" and r.flags == []
    assert "the actual conversation text" in b.last["user"]
    assert "e1: a fact" in b.last["user"]
    assert b.last["model"] == TIER_SONNET                    # §12 tier FROZEN — exact build


def test_tier0_hints_are_attached_to_the_prompt():
    b = FakeLLMBackend('{"verdict": "FLAG", "flags": [{"code": "S1", "artifact": "e1"}]}')
    r = screen_raw(b, window="w", manifest="e1: a fact",
                   hints=(Tier0Hint(edge_id="e1", entity="Genesys"),))
    assert r.verdict == "FLAG"
    assert "Genesys" in b.last["user"]                        # the soft hint rode along


def test_fail_closed_on_garbage_reply_defaults_pass():
    b = FakeLLMBackend("not json at all")
    r = screen_raw(b, window="w", manifest="m")
    assert r.verdict == "PASS" and r.flags == []              # safe_json_object -> {}
