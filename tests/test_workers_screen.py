from __future__ import annotations

from genesys.workers.backend import FakeLLMBackend
from genesys.workers.screen import SCREEN_PROMPT, ScreenResult, screen


def test_prompt_is_verbatim_c31_anchors():
    assert "You are the Screen" in SCREEN_PROMPT
    assert "S3. DIAGNOSIS" in SCREEN_PROMPT
    assert "The failure mode you must never have is a quiet PASS" in SCREEN_PROMPT


def test_screen_parses_pass():
    b = FakeLLMBackend('{"verdict": "PASS", "flags": []}')
    r = screen(b, jot="j", manifest="m")
    assert isinstance(r, ScreenResult)
    assert r.verdict == "PASS" and r.flags == []


def test_screen_parses_flag_and_passes_jot_and_manifest():
    b = FakeLLMBackend('{"verdict": "FLAG", "flags": [{"code": "S3", "artifact": "e1", "jot_evidence": "x"}]}')
    r = screen(b, jot="the jot", manifest="the manifest")
    assert r.verdict == "FLAG" and r.flags[0]["code"] == "S3"
    assert "the jot" in b.last["user"] and "the manifest" in b.last["user"]
    assert b.last["model"].startswith("claude-sonnet")
