from __future__ import annotations

from genesys.diary.anthropic_backend import AnthropicBackend
from genesys.diary.inputs import DiaryInputs, LedgerItem


class _FakeMessages:
    def __init__(self, capture): self._capture = capture
    def create(self, **kwargs):
        self._capture.update(kwargs)
        class _Block: text = "## TOP OF MIND\n- synthesized"
        class _Resp: content = [_Block()]
        return _Resp()


class _FakeClient:
    def __init__(self): self.captured = {}; self.messages = _FakeMessages(self.captured)


def test_synthesize_uses_injected_client_and_returns_text():
    client = _FakeClient()
    di = DiaryInputs(ledger=[LedgerItem("2026-08-16T10:00:00+00:00", "a thing", False, "s")],
                     tasks=[], open_questions=[])
    out = AnthropicBackend(client, model="claude-sonnet-4-6").synthesize("PROMPT", di)
    assert "synthesized" in out
    assert client.captured["model"] == "claude-sonnet-4-6"


def test_system_prompt_is_cached():
    client = _FakeClient()
    AnthropicBackend(client).synthesize("PROMPT", DiaryInputs())
    system = client.captured["system"]
    # system is a list of blocks; the prompt block carries ephemeral cache_control
    assert any(b.get("cache_control", {}).get("type") == "ephemeral" for b in system)


def test_module_does_not_import_anthropic_at_top_level():
    import sys
    import genesys.diary.anthropic_backend  # noqa: F401
    assert "anthropic" not in sys.modules  # lazy import only; sandbox never loads the SDK
