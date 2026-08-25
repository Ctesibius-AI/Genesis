"""Live diary backend over the Anthropic API (spec §12 tiers; App E.5).

⚠ The `anthropic` SDK is imported LAZILY (only in default_client) so the offline sandbox
never loads it. The client is injected, so tests exercise the request shape with a fake and
the real API path runs only live (owner-gated). The E.5 system prompt is prompt-cached
(claude-api skill).
"""

from __future__ import annotations

from genesis.diary.inputs import DiaryInputs


def default_client():
    """Construct the real Anthropic client — imported lazily; live use only."""
    import anthropic  # noqa: PLC0415 — deliberate lazy import (keeps the sandbox SDK-free)

    return anthropic.Anthropic()


def _render_inputs(inputs: DiaryInputs) -> str:
    lines = ["<inputs>", "LEDGER:"]
    for i in inputs.ledger:
        mark = " [unverified]" if i.unverified else ""
        lines.append(f"- ({i.ts}) {i.summary}{mark}")
    lines.append(f"TASKS: {inputs.tasks or 'none'}")
    lines.append(f"OPEN_QUESTIONS: {inputs.open_questions or 'none'}")
    lines.append("</inputs>")
    return "\n".join(lines)


class AnthropicBackend:
    def __init__(self, client, model: str = "claude-sonnet-4-6", max_tokens: int = 2000):
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def synthesize(self, prompt: str, inputs: DiaryInputs) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=[{"type": "text", "text": prompt, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": _render_inputs(inputs)}],
        )
        return "".join(getattr(b, "text", "") for b in resp.content)
