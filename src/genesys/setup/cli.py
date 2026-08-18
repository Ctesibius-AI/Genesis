"""``genesys-setup`` — the install-time identity prompt.

Genesys is owner-agnostic: who the memory is *for* (the principal) and what the
assistant persona is *called* are configuration, not code. This command runs once
at install time, asks for those two values, and writes them to the config file that
``genesys.config`` reads (env var → this config file → generic default).

Design constraints:
  - Offline, stdlib only. No network, no LLM.
  - Testable: input/output streams and a non-interactive answer source are injectable,
    so the prompt loop can be exercised without a real TTY.
  - Idempotent: re-running simply rewrites the same config file (merging, preserving
    any unrelated keys).
"""

from __future__ import annotations

import argparse
import sys
from typing import Callable, TextIO

from genesys.config import (
    DEFAULT_ASSISTANT,
    DEFAULT_PRINCIPAL,
    get_assistant_name,
    get_principal,
    write_identity_config,
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

    out.write("Genesys setup — tell me who this memory is for.\n")
    out.write("(Press Enter to accept the default shown in brackets.)\n\n")

    principal = _prompt("Your name (the principal)", p_default, reader=reader, out=out)
    assistant = _prompt("Assistant name", a_default, reader=reader, out=out)

    config_path = write_identity_config(principal, assistant)

    out.write(
        f"\nSaved. Principal = {principal!r}, assistant = {assistant!r}.\n"
        f"Config written to {config_path}.\n"
    )
    return {
        "principal": principal,
        "assistant": assistant,
        "config_path": str(config_path),
    }


def main(argv: list[str] | None = None) -> int:
    """Console-script entry point for ``genesys-setup``."""
    parser = argparse.ArgumentParser(
        prog="genesys-setup",
        description="Configure the Genesys principal + assistant identity.",
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
