"""``genesis-setup`` — the install-time identity prompt.

Genesis is owner-agnostic: who the memory is *for* (the principal) and what the
assistant persona is *called* are configuration, not code. This command runs once
at install time, asks for those two values, and writes them to the config file that
``genesis.config`` reads (env var → this config file → generic default).

Design constraints:
  - Offline, stdlib only. No network, no LLM.
  - Testable: input/output streams and a non-interactive answer source are injectable,
    so the prompt loop can be exercised without a real TTY.
  - Idempotent: re-running simply rewrites the same config file (merging, preserving
    any unrelated keys).
"""

from __future__ import annotations

import argparse
import secrets
import sys
from typing import Callable, TextIO

from genesis.config import (
    DEFAULT_ASSISTANT,
    DEFAULT_PRINCIPAL,
    HMAC_KEY_ENV,
    get_assistant_name,
    get_local_hmac_key_optional,
    get_principal,
    write_identity_config,
)


def offer_hmac_key(*, reader: Callable[[str], str], out: TextIO) -> None:
    """Offer to GENERATE the local redaction key when none is set (D-FB-4, F-01.1).

    genesis-setup writes identity only; the DR-38 redaction path needs a keyed HMAC
    (``GENESIS_LOCAL_HMAC_KEY``). With explicit consent this prints a fresh key ONCE and tells the
    user where to store it — it NEVER writes the key to disk itself (the user owns the secret, same
    pattern as the API key). If a key is already set, or the user declines, nothing is generated.
    """
    if get_local_hmac_key_optional() is not None:
        out.write(f"\nA redaction key ({HMAC_KEY_ENV}) is already configured — nothing to do.\n")
        return
    out.write(
        f"\nNo redaction key found. Genesis scrubs secrets at capture; a local key ({HMAC_KEY_ENV})\n"
        "lets it correlate redactions and keeps redaction markers from being guessed. It is optional\n"
        "(capture works without it) but recommended.\n"
    )
    try:
        answer = reader("Generate a redaction key now? [y/N]: ").strip().lower()
    except EOFError:
        answer = ""
    if answer not in ("y", "yes"):
        out.write(
            "Skipped. To create one later:\n"
            f"  openssl rand -hex 32   →   export {HMAC_KEY_ENV}=<the value>\n"
            "  (store it in a ~/.secrets/ file you source, same as your API key).\n"
        )
        return
    key = secrets.token_hex(32)
    # Printed ONCE; never persisted by Genesis. The user stores it themselves.
    out.write(
        "\nHere is your new redaction key — copy it now; Genesis does NOT store it:\n\n"
        f"  export {HMAC_KEY_ENV}={key}\n\n"
        "Put that line in a ~/.secrets/ file you source at login (same pattern as your API key).\n"
        "If you lose it, generate a new one — existing redaction fingerprints simply won't correlate.\n"
    )


def _prompt(
    label: str,
    default: str,
    *,
    reader: Callable[[str], str],
    out: TextIO,
) -> str:
    """Ask a single question, returning the entered value or the default.

    ``reader`` is the input function (``input`` in production, a fake in tests).
    A blank / whitespace-only answer accepts ``default``. On EOF the default is used
    (non-interactive / piped-empty stdin degrades gracefully rather than crashing).
    """
    suffix = f" [{default}]" if default else ""
    try:
        raw = reader(f"{label}{suffix}: ")
    except EOFError:
        out.write(f"(using default: {default})\n")
        return default
    value = raw.strip()
    return value if value else default


def run_setup(
    *,
    reader: Callable[[str], str] = input,
    out: TextIO | None = None,
    principal_default: str | None = None,
    assistant_default: str | None = None,
) -> dict:
    """Prompt for principal + assistant, persist them, and report the result.

    Returns a dict ``{"principal", "assistant", "config_path"}``. Defaults are the
    currently-configured values when present, otherwise the generic fallbacks — so
    re-running setup offers the existing answers.
    """
    out = out if out is not None else sys.stdout

    # Offer the current config (if any) as the default, else the generic fallback.
    current_principal = get_principal()
    current_assistant = get_assistant_name()
    p_default = principal_default or (
        current_principal if current_principal != DEFAULT_PRINCIPAL else DEFAULT_PRINCIPAL
    )
    a_default = assistant_default or (current_assistant or DEFAULT_ASSISTANT)

    out.write("Genesis setup — tell me who this memory is for.\n")
    out.write("(Press Enter to accept the default shown in brackets.)\n\n")

    principal = _prompt("Your name (the principal)", p_default, reader=reader, out=out)
    assistant = _prompt("Assistant name", a_default, reader=reader, out=out)

    config_path = write_identity_config(principal, assistant)

    out.write(
        f"\nSaved. Principal = {principal!r}, assistant = {assistant!r}.\n"
        f"Config written to {config_path}.\n"
    )

    # D-FB-4: after identity, offer to generate the local redaction key if none exists (consent-gated,
    # printed once, never persisted). First run no longer leaves the user with no key + no guidance.
    offer_hmac_key(reader=reader, out=out)
    return {
        "principal": principal,
        "assistant": assistant,
        "config_path": str(config_path),
    }


def main(argv: list[str] | None = None) -> int:
    """Console-script entry point for ``genesis-setup``."""
    parser = argparse.ArgumentParser(
        prog="genesis-setup",
        description="Configure the Genesis principal + assistant identity.",
    )
    parser.add_argument(
        "--principal",
        default=None,
        help="Set the principal non-interactively (skips the prompt for it).",
    )
    parser.add_argument(
        "--assistant",
        default=None,
        help="Set the assistant name non-interactively (default: Daimon).",
    )
    args = parser.parse_args(argv)

    # If both provided on the command line, write directly (no prompting).
    if args.principal is not None and args.assistant is not None:
        path = write_identity_config(args.principal, args.assistant)
        sys.stdout.write(
            f"Saved. Principal = {args.principal!r}, assistant = {args.assistant!r}.\n"
            f"Config written to {path}.\n"
        )
        return 0

    run_setup(
        principal_default=args.principal,
        assistant_default=args.assistant,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
