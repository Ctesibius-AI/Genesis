from __future__ import annotations

import sys

from genesys.workers.backend import (
    TIER_OPUS, TIER_SONNET, AnthropicLLMBackend, FakeLLMBackend,
)


def test_tiers_are_the_spec_model_ids():
    assert TIER_SONNET == "claude-sonnet-4-6"
    assert TIER_OPUS == "claude-opus-4-8"


def test_fake_backend_returns_reply_and_records_call():
    b = FakeLLMBackend('{"ok": true}')
    out = b.complete("SYS", "USR", model=TIER_SONNET)
    assert out == '{"ok": true}'
    assert b.last == {"system": "SYS", "user": "USR", "model": TIER_SONNET}


class _FakeMsgs:
    def __init__(self, cap): self._cap = cap
    def create(self, **kw):
        self._cap.update(kw)
        class _B: text = "RESULT"
        class _R: content = [_B()]
        return _R()


class _FakeClient:
    def __init__(self): self.cap = {}; self.messages = _FakeMsgs(self.cap)


def test_anthropic_backend_uses_injected_client_cached_system():
    c = _FakeClient()
    out = AnthropicLLMBackend(c).complete("SYS", "USR", model=TIER_OPUS)
    assert out == "RESULT"
    assert c.cap["model"] == TIER_OPUS
    assert any(b.get("cache_control", {}).get("type") == "ephemeral" for b in c.cap["system"])


def test_module_does_not_import_anthropic_at_top_level():
    import genesys.workers.backend  # noqa: F401
    assert "anthropic" not in sys.modules
