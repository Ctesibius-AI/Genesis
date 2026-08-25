"""Genesis interactive setup — the install-time identity prompt.

Exposes ``genesis-setup`` (see pyproject.toml [project.scripts]). It asks who the
memory is *for* (the principal) and what the assistant persona is *called* (default
``Daimon``), then persists both to the config file that ``genesis.config`` reads.
Offline, stdlib-only, and testable (prompt/output streams are injectable).
"""
