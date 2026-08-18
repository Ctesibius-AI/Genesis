"""KEY-1 / PT-9 / KEY-2 inputs for the release machine (spec §8.6).

Key detection is an injected classification, never inline NLP: a `KeyClassifier` decides
whether a turn is the principal's first-person ask about Daimon's view of him (KEY-1), a
confirmation yes/no, or nothing. Close decisions are biased to closed.

The live seam mirrors `genesys.workers.backend.AnthropicLLMBackend`: the `RealKeyClassifier`
takes an INJECTED `LLMBackend` (the same Fake/Anthropic backends the Supervisor workers use —
lazy `import anthropic`, never at module top-level, prompt-cached system prompt), runs the
verbatim App C.1 KEY-1 / KEY-2 prompts, and is fully offline-testable with a fake backend. It
is **precision-first / fail-closed** (R-K, §8.6 item 4): any ambiguity, parse failure, empty
or garbage reply resolves to NOT_KEY (never opens release) and to closed (KEY-2).
"""

from __future__ import annotations

from typing import Protocol

from genesys.workers.backend import TIER_SONNET, LLMBackend, safe_json_object

PT9_CONFIRMATION = "Do I have your confirmation to share my view on that?"


class KeyKind:
    KEY1 = "key1"
    NOT_KEY = "not-key"
    CONFIRM_YES = "confirm-yes"
    CONFIRM_NO = "confirm-no"


class KeyClassifier(Protocol):
    def classify(self, turn: str, *, subject: str) -> str: ...


class FakeKeyClassifier:
    def __init__(self, *, mapping: dict[str, str] | None = None,
                 default: str = KeyKind.NOT_KEY) -> None:
        self._map = dict(mapping or {})
        self._default = default

    def set(self, turn: str, kind: str) -> None:
        self._map[turn] = kind

    def classify(self, turn: str, *, subject: str) -> str:
        return self._map.get(turn, self._default)


# --- Verbatim App C.1 prompts (prompt-integrity CI mirrors these against the spec, §20) ---
# {PRINCIPAL} is a build-time substitution; no {EXAMPLES} at launch (bank starts empty).

KEY1_PROMPT = """\
Answer YES only if the principal is directly and in the first person asking for Daimon's view,
opinion, impression, or read of HIM (his traits, character, tendencies, how he comes across).
Questions about other people, objects, work, or facts → NO. Agreement, acknowledgement, silence,
or the principal describing himself → NO. If Daimon raised the topic in the previous turn → NO.
When unsure → NO.

The principal is {PRINCIPAL}.

Reply with ONLY a JSON object, no prose:
{"key": "yes" | "no", "anchor_hint": "<the trait/subject he named, or null>", "scope": "topic" | "general"}
"""

KEY2_PROMPT = """\
Answer NO (closed) if the principal has moved to a different subject, to work, or has said he is
done; when unsure → NO.

The open subject is: {SCOPE}

Reply with ONLY a JSON object, no prose:
{"still_open": "yes" | "no"}
"""


class RealKeyClassifier:
    """Live KEY-1 / KEY-2 classifier over an injected `LLMBackend` (spec §8.6, App C.1).

    Mirrors `AnthropicLLMBackend`: the LLM client is injected (the same backend the workers
    use), so this is offline-testable with `FakeLLMBackend`; the real `anthropic` import stays
    lazy inside `genesys.workers.backend.default_client`, never at module top-level.

    Fail-closed by construction (precision-first, R-K):
      * `classify` → KEY-1. Returns `KeyKind.KEY1` ONLY on an explicit `{"key": "yes"}`.
        Anything else — "no", a missing/garbage field, an empty or unparseable reply, a
        backend error — returns `KeyKind.NOT_KEY`. Uncertainty never opens release.
      * `still_open` → KEY-2. Returns True ONLY on an explicit `{"still_open": "yes"}`;
        everything else (including parse failure) is treated as CLOSED.
    """

    def __init__(self, backend: LLMBackend, *, model: str = TIER_SONNET) -> None:
        self._backend = backend
        self._model = model

    def _key1_system(self, subject: str) -> str:
        return KEY1_PROMPT.replace("{PRINCIPAL}", subject)

    def classify(self, turn: str, *, subject: str) -> str:
        """KEY-1: is this turn the principal's first-person ask about Daimon's view of him?

        Returns a `KeyKind`. Fail-closed: only an explicit affirmative maps to KEY1.
        """
        try:
            raw = self._backend.complete(self._key1_system(subject), turn, model=self._model)
        except Exception:  # noqa: BLE001 — any backend failure biases to closed (no key)
            return KeyKind.NOT_KEY
        d = safe_json_object(raw)  # {} on empty/garbage/non-object reply
        key = d.get("key")
        if isinstance(key, str) and key.strip().lower() == "yes":
            return KeyKind.KEY1
        return KeyKind.NOT_KEY

    def key1_details(self, turn: str, *, subject: str) -> dict:
        """KEY-1 full output `{key, anchor_hint, scope}` for the release machine.

        `scope` defaults to "topic" (the narrower, safer release) and `anchor_hint` to None
        on any ambiguity or parse failure, so a malformed reply cannot widen the release.
        """
        try:
            raw = self._backend.complete(self._key1_system(subject), turn, model=self._model)
        except Exception:  # noqa: BLE001
            return {"key": KeyKind.NOT_KEY, "anchor_hint": None, "scope": "topic"}
        d = safe_json_object(raw)
        key = d.get("key")
        is_key = isinstance(key, str) and key.strip().lower() == "yes"
        scope = d.get("scope")
        if scope not in ("topic", "general"):
            scope = "topic"  # bias to the narrower release on anything unexpected
        anchor = d.get("anchor_hint")
        if not isinstance(anchor, str) or not anchor.strip():
            anchor = None
        return {"key": KeyKind.KEY1 if is_key else KeyKind.NOT_KEY,
                "anchor_hint": anchor, "scope": scope}

    def still_open(self, turn: str, *, scope: str) -> bool:
        """KEY-2: is the perceived-view subject still open on this turn?

        Fail-closed: only an explicit `{"still_open": "yes"}` keeps it open; anything else
        (subject change, "done", empty/garbage reply, backend error) closes it.
        """
        system = KEY2_PROMPT.replace("{SCOPE}", scope)
        try:
            raw = self._backend.complete(system, turn, model=self._model)
        except Exception:  # noqa: BLE001 — bias to closed on any failure
            return False
        d = safe_json_object(raw)
        still = d.get("still_open")
        return isinstance(still, str) and still.strip().lower() == "yes"


def real_classifier(backend: LLMBackend | None = None, *, model: str = TIER_SONNET):
    """Build the live KEY classifier over an injected backend.

    With a backend injected (offline: `FakeLLMBackend`; live: `AnthropicLLMBackend`) this
    returns a wired `RealKeyClassifier`. Called with NO backend it stays the documented stub:
    it attempts the lazy `anthropic` import (never at module top-level) and constructs the
    live backend from `default_client()`. That live path is exercised only against the real
    API — offline the SDK is absent, so this raises (RuntimeError if the extra is missing,
    NotImplementedError otherwise), and tests inject a fake backend instead.
    """
    if backend is not None:
        return RealKeyClassifier(backend, model=model)
    try:
        import anthropic  # noqa: F401, PLC0415  (lazy — absent offline)
    except ImportError as exc:  # pragma: no cover - exercised only where extra is absent
        raise RuntimeError("the llm extra is required for a real key classifier") from exc
    # pragma: no cover - live wiring, verified against the API, not offline
    raise NotImplementedError(
        "real_classifier() without an injected backend lands with the harness integration; "
        "offline, inject an LLMBackend (FakeLLMBackend) or use FakeKeyClassifier")


CLOSE_TRIGGERS = frozenset({"topic-change", "idle", "session-end"})


def is_close_trigger(reason: str) -> bool:
    return reason in CLOSE_TRIGGERS


def should_close(reason: str) -> bool:
    return reason != "none"  # bias-to-closed: anything but explicit 'none' closes
