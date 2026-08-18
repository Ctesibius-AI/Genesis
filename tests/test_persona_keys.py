from __future__ import annotations

import sys

import pytest

from genesys.persona.keys import (
    KEY1_PROMPT,
    KEY2_PROMPT,
    PT9_CONFIRMATION,
    FakeKeyClassifier,
    KeyKind,
    RealKeyClassifier,
    is_close_trigger,
    real_classifier,
    should_close,
)
from genesys.workers.backend import TIER_SONNET, FakeLLMBackend


def test_pt9_is_the_fixed_line():
    assert PT9_CONFIRMATION == "Do I have your confirmation to share my view on that?"


def test_fake_classifier_scripts_keys():
    c = FakeKeyClassifier()
    c.set("what do you think of me?", KeyKind.KEY1)
    c.set("yes", KeyKind.CONFIRM_YES)
    assert c.classify("what do you think of me?", subject="the principal") == KeyKind.KEY1
    assert c.classify("yes", subject="the principal") == KeyKind.CONFIRM_YES
    assert c.classify("ok cool", subject="the principal") == KeyKind.NOT_KEY  # default: not a key


def test_close_bias():
    assert is_close_trigger("idle") is True
    assert should_close("topic-change") is True
    assert should_close("session-end") is True
    assert should_close("something-weird") is True   # bias-to-closed on unknown
    assert should_close("none") is False             # only explicit 'none' stays open


def test_real_classifier_without_backend_is_a_documented_stub():
    # No injected backend → the live (anthropic) wiring path, which is not offline-runnable.
    with pytest.raises((RuntimeError, NotImplementedError)):
        real_classifier()


# --- Real KEY-1 / KEY-2 classifier over an INJECTED fake backend (offline; no network) ---


def _key1_reply(key: str, *, anchor: str | None = None, scope: str = "topic") -> str:
    a = "null" if anchor is None else f'"{anchor}"'
    return f'{{"key": "{key}", "anchor_hint": {a}, "scope": "{scope}"}}'


def test_real_classifier_with_backend_returns_wired_adapter():
    c = real_classifier(FakeLLMBackend(_key1_reply("no")))
    assert isinstance(c, RealKeyClassifier)


def test_module_does_not_import_anthropic_at_top_level():
    # Same guarantee AnthropicLLMBackend gives: importing keys must not pull the SDK.
    import genesys.persona.keys  # noqa: F401
    assert "anthropic" not in sys.modules


def test_prompts_are_the_verbatim_app_c_text():
    # Precision-first KEY-1 core sentence (App C.1) must survive verbatim.
    assert "Answer YES only if the principal is directly and in the first person" in KEY1_PROMPT
    assert "When unsure → NO." in KEY1_PROMPT
    assert "Answer NO (closed) if the principal has moved to a different subject" in KEY2_PROMPT
    assert "when unsure → NO." in KEY2_PROMPT


def test_key1_yes_maps_to_key1_and_substitutes_principal():
    b = FakeLLMBackend(_key1_reply("yes", anchor="Trait:rigor"))
    c = real_classifier(b, model=TIER_SONNET)
    assert c.classify("what do you think of me?", subject="the principal") == KeyKind.KEY1
    # subject is substituted into the KEY-1 system prompt; user turn is the turn verbatim.
    assert "{PRINCIPAL}" not in b.last["system"]
    assert "the principal" in b.last["system"]
    assert b.last["user"] == "what do you think of me?"
    assert b.last["model"] == TIER_SONNET


def test_key1_no_maps_to_not_key():
    c = real_classifier(FakeLLMBackend(_key1_reply("no")))
    assert c.classify("what do you think of the weather?", subject="the principal") == KeyKind.NOT_KEY


def test_key1_details_carry_anchor_and_scope():
    c = real_classifier(FakeLLMBackend(_key1_reply("yes", anchor="Trait:candor", scope="general")))
    d = c.key1_details("how do I come across in general?", subject="the principal")
    assert d == {"key": KeyKind.KEY1, "anchor_hint": "Trait:candor", "scope": "general"}


# --- FAIL-CLOSED coverage (never open release on uncertainty) ---


@pytest.mark.parametrize("reply", [
    "",                       # empty completion
    "   ",                    # whitespace only
    "I'm not sure honestly",  # prose, no JSON
    "{ this is not json",     # broken JSON
    "{}",                     # valid JSON, no 'key' field
    '{"key": "maybe"}',       # ambiguous value
    '{"key": "YES!"}',        # not an exact affirmative token
    '{"key": true}',          # wrong type
    '[1, 2, 3]',              # JSON but not an object
    '{"key": "no"}',          # explicit negative
])
def test_key1_fails_closed_on_ambiguous_or_garbage(reply):
    c = real_classifier(FakeLLMBackend(reply))
    assert c.classify("anything at all", subject="the principal") == KeyKind.NOT_KEY


def test_key1_details_fails_closed_to_topic_scope_on_garbage():
    c = real_classifier(FakeLLMBackend("garbage not json"))
    d = c.key1_details("anything", subject="the principal")
    assert d == {"key": KeyKind.NOT_KEY, "anchor_hint": None, "scope": "topic"}


def test_key1_details_bad_scope_falls_back_to_topic():
    c = real_classifier(FakeLLMBackend('{"key": "yes", "anchor_hint": "Trait:x", "scope": "everything"}'))
    d = c.key1_details("anything", subject="the principal")
    assert d["scope"] == "topic"  # unexpected scope narrows, never widens


def test_key1_fails_closed_when_backend_raises():
    class _Boom:
        def complete(self, system, user, *, model):
            raise RuntimeError("network down")
    assert RealKeyClassifier(_Boom()).classify("what do you think of me?", subject="the principal") == KeyKind.NOT_KEY


def test_key2_still_open_yes_keeps_open():
    b = FakeLLMBackend('{"still_open": "yes"}')
    c = real_classifier(b)
    assert c.still_open("and what else?", scope="Trait:rigor") is True
    assert "{SCOPE}" not in b.last["system"] and "Trait:rigor" in b.last["system"]


@pytest.mark.parametrize("reply", [
    "",
    "   ",
    "he changed the subject",
    "{ broken",
    "{}",
    '{"still_open": "no"}',
    '{"still_open": "maybe"}',
    '{"still_open": true}',
    '{"other": "yes"}',
])
def test_key2_fails_closed_on_ambiguous_or_garbage(reply):
    c = real_classifier(FakeLLMBackend(reply))
    assert c.still_open("let's talk about the deploy", scope="Trait:rigor") is False


def test_key2_fails_closed_when_backend_raises():
    class _Boom:
        def complete(self, system, user, *, model):
            raise RuntimeError("network down")
    assert RealKeyClassifier(_Boom()).still_open("still?", scope="Trait:rigor") is False
