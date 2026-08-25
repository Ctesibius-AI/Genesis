"""LLM judgment backend (spec §12 tiers). Every Supervisor worker calls `complete`.

FakeLLMBackend (canned reply) drives every test; AnthropicLLMBackend is the live path with
the `anthropic` SDK imported LAZILY (never at module top-level) and the system prompt
prompt-cached. Model tiers per §12: Sonnet (Screen/Class-Auditor/Clerk/Judge),
Opus (Verifier).
"""

from __future__ import annotations

from typing import Protocol

TIER_SONNET = "claude-sonnet-4-6"
TIER_OPUS = "claude-opus-4-8"


def safe_json_object(raw: str) -> dict:
    """Parse an LLM reply into a JSON object, returning {} on any failure.

    A single malformed or empty model reply must never crash the drain: each worker
    applies its own conservative .get() defaults to the empty dict (spec §12 — fail
    closed, don't act without a valid ruling). Uses strip_fences to tolerate models
    that reason before emitting JSON or wrap it in ```json fences.
    """
    import json as _json  # noqa: PLC0415 — stdlib

    try:
        obj = _json.loads(strip_fences(raw))
    except (ValueError, TypeError):
        return {}
    return obj if isinstance(obj, dict) else {}


def strip_fences(text: str) -> str:
    """Extract a JSON object or array from an LLM response before parsing.

    The Anthropic API occasionally reasons before producing the JSON, or wraps JSON in
    ```json ... ``` blocks. This function extracts the JSON payload regardless of placement:
    1. Search for fenced ```[json]...``` blocks; try each candidate (last first) via json.loads.
    2. If no valid fenced JSON, extract using bracket-depth matching from any { or [ in the text.
       We walk from the LAST { or [ with depth-tracking to find the complete, balanced JSON value.
    Pure, no I/O, safe to call on already-clean responses. Returns the original stripped text if
    no JSON can be extracted (let json.loads raise with its natural error message).
    """
    import json as _json  # noqa: PLC0415 — stdlib, lazy alias to avoid shadowing outer json
    import re  # noqa: PLC0415 — stdlib

    text = text.strip()

    # Collect all valid JSON candidates across the whole text.
    # Strategy: prefer the LONGEST (outermost) valid JSON value — the top-level response
    # object from the LLM is always the largest. Candidates come from:
    #   (a) fenced ```[json]...``` code blocks
    #   (b) bracket-depth scan of the full text
    all_candidates: list[str] = []

    # (a) fenced blocks
    fence_matches = list(re.finditer(r"```(?:json|JSON)?\s*\n?(.*?)```", text, re.DOTALL))
    for m in fence_matches:
        c = m.group(1).strip()
        try:
            _json.loads(c)
            all_candidates.append(c)
        except (_json.JSONDecodeError, ValueError):
            pass

    # (b) bracket-depth scan
    for start in range(len(text)):
        ch = text[start]
        if ch not in ("{", "["):
            continue
        open_ch = ch
        close_ch = "}" if open_ch == "{" else "]"
        depth = 0
        in_string = False
        escaped = False
        end = -1
        for i in range(start, len(text)):
            c = text[i]
            if escaped:
                escaped = False
                continue
            if c == "\\" and in_string:
                escaped = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == open_ch:
                depth += 1
            elif c == close_ch:
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end != -1:
            candidate = text[start:end + 1]
            try:
                _json.loads(candidate)
                all_candidates.append(candidate)
            except (_json.JSONDecodeError, ValueError):
                pass

    if all_candidates:
        # Return the longest valid JSON candidate — this is always the top-level object.
        return max(all_candidates, key=len)

    # Nothing worked — return stripped text; json.loads will raise with a clear error
    return text


class LLMBackend(Protocol):
    def complete(self, system: str, user: str, *, model: str) -> str: ...


class FakeLLMBackend:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.last: dict | None = None

    def complete(self, system: str, user: str, *, model: str) -> str:
        self.last = {"system": system, "user": user, "model": model}
        return self.reply


def default_client():
    import anthropic  # noqa: PLC0415 — lazy: keeps the offline sandbox SDK-free

    return anthropic.Anthropic()


class AnthropicLLMBackend:
    def __init__(self, client, max_tokens: int = 1024) -> None:
        self._client = client
        self._max_tokens = max_tokens

    def complete(self, system: str, user: str, *, model: str) -> str:
        resp = self._client.messages.create(
            model=model,
            max_tokens=self._max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        return "".join(getattr(b, "text", "") for b in resp.content)
