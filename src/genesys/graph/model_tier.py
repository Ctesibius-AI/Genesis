"""R5 model-tier routing (D-GCW-8): route graphiti's small-tier LLM calls to Haiku.

graphiti-core's AnthropicClient ignores `config.small_model` (R6 — `anthropic_client.py:293`,
design §0b) ⚠ NOT re-verified offline; confirm at the live run (C1, live-run checklist). This
Genesys-side wrapper honours `model_size` so extraction's cheap sub-calls use Haiku, the primary
v1 cost lever. When the 1-line upstream R6 PR lands + graphiti-core is bumped, delete this wrapper.

The model-SELECTION rule is a pure function (offline-tested). The graphiti subclass is built lazily
so this module imports offline (the subclass needs graphiti-core, absent in the offline sandbox).
"""

from __future__ import annotations

# Tunable (P-2): the small tier routes to a current Haiku snapshot; the standard tier stays Sonnet.
SMALL_MODEL_DEFAULT = "claude-haiku-4-5"
STANDARD_MODEL_DEFAULT = "claude-sonnet-4-6"


def resolve_model(model_size, *, standard: str, small: str) -> str:
    """Return the model id for a call's tier: small tier → `small`, everything else → `standard`.

    graphiti passes `model_size` as an enum or str ("small"/"medium"). Fail-safe: anything that is
    not explicitly "small" uses the standard model (never silently downgrade a standard call).
    """
    size = getattr(model_size, "value", model_size)
    return small if str(size).strip().lower() == "small" else standard


def build_tiered_anthropic_client(config, *, small_model: str = SMALL_MODEL_DEFAULT):  # pragma: no cover - live only
    """Build a graphiti AnthropicClient subclass that honours `model_size` (R5).

    Lazy import: graphiti-core is absent in the offline sandbox. ⚠ The exact `_generate_response`
    signature of graphiti-core v0.29.3 is confirmed at the live run (C1); if upstream already
    honours `small_model`, this wrapper is unnecessary — `request clarification` and drop it.
    """
    from graphiti_core.llm_client.anthropic_client import AnthropicClient

    standard_model = getattr(config, "model", None) or STANDARD_MODEL_DEFAULT

    class _TieredAnthropicClient(AnthropicClient):
        async def _generate_response(self, messages, response_model=None, max_tokens=None,
                                     model_size=None, **kwargs):
            chosen = resolve_model(model_size, standard=standard_model, small=small_model)
            prior = self.model
            self.model = chosen  # route this call's tier (R5); restore after
            try:
                return await super()._generate_response(
                    messages, response_model=response_model, max_tokens=max_tokens,
                    model_size=model_size, **kwargs)
            finally:
                self.model = prior

    return _TieredAnthropicClient(config=config)
