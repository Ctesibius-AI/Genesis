"""Configuration for the Step 0 security layer.

12-Factor: config comes from the environment, never hardcoded. The local Genesis
HMAC key used for DR-38 R4 tombstone hashing is read from ``GENESIS_LOCAL_HMAC_KEY``
and is *never* checked in.
"""

from __future__ import annotations

import os

# Env var carrying the local Genesis HMAC key (DR-38 R4). The key is what makes the
# tombstone hash a keyed proof-of-what-was-there for the owner, rather than a public
# dictionary oracle. It MUST NOT be committed or logged.
HMAC_KEY_ENV = "GENESIS_LOCAL_HMAC_KEY"


class ConfigError(RuntimeError):
    """Raised when required security configuration is missing."""


import warnings  # noqa: E402


def _getenv(name: str) -> str | None:
    """Read a ``GENESIS_*`` env var, falling back to the deprecated ``GENESYS_*`` name.

    Rename migration (D-GCW-20): the old ``GENESYS_*`` names are accepted for ONE release with a
    ``DeprecationWarning``. The new name always wins; the old is a compatibility fallback only.
    """
    val = os.environ.get(name)
    if val is not None:
        return val
    if name.startswith("GENESIS_"):
        old = "GENESYS_" + name[len("GENESIS_"):]
        val = os.environ.get(old)
        if val is not None:
            warnings.warn(
                f"{old} is deprecated (renamed to {name}); accepted this release only.",
                DeprecationWarning, stacklevel=2)
    return val


def get_local_hmac_key() -> bytes:
    """Return the local Genesis HMAC key as bytes.

    Read from the environment (``GENESIS_LOCAL_HMAC_KEY``). Raises ``ConfigError``
    if unset — DR-38 R4 requires a *keyed* HMAC, so there is no safe default: a
    missing key must be a loud failure, not a silent fall-back to an empty key or a
    plain digest (that would recreate the dictionary-oracle the rule forbids).
    """
    raw = _getenv(HMAC_KEY_ENV)
    if not raw:
        raise ConfigError(
            f"{HMAC_KEY_ENV} is not set. DR-38 R4 requires a keyed HMAC for "
            "redaction tombstones; refusing to hash without a local key."
        )
    return raw.encode("utf-8")


# --- Data root (P1) -------------------------------------------------------- #

from pathlib import Path  # noqa: E402  (kept next to its use for clarity)

DATA_ROOT_ENV = "GENESIS_DATA"


def get_data_root() -> Path:
    """Return the Genesis data root (owned files + ledger) from ``GENESIS_DATA``.

    No silent default: a memory of record must not scatter its files to an
    unexpected place because an env var was forgotten (12-Factor; loud failure).
    """
    raw = _getenv(DATA_ROOT_ENV)
    if not raw:
        raise ConfigError(
            f"{DATA_ROOT_ENV} is not set. Genesis needs an explicit data root "
            "for owned files + the ledger; refusing to guess a location."
        )
    return Path(raw)


# --- Per-workspace graph store (D-GCW-2: physical + logical isolation) ------ #
#
# Defense-in-depth per-workspace isolation: a dedicated graph file path (physical
# wall) and a unique group_id (logical wall). Both are env-pinned and fail-loud —
# an unset persistent path must NOT silently fall back to an ephemeral /tmp graph
# (the data-loss trap at graphiti_backend.build_graphiti_client). 12-Factor: env
# is the source; a missing value is a loud refusal, never a guess.

DB_PATH_ENV = "GENESIS_DB_PATH"
GROUP_ID_ENV = "GENESIS_GROUP_ID"


def get_db_path() -> Path:
    """Return the persistent graph store path from ``GENESIS_DB_PATH`` (D-GCW-2).

    No silent default: an unset path used to fall back to ``tempfile.mkdtemp`` — an
    ephemeral /tmp graph that vanishes, silently losing memory. Refuse instead.
    """
    raw = _getenv(DB_PATH_ENV)
    if not raw:
        raise ConfigError(
            f"{DB_PATH_ENV} is not set. Genesis refuses to open an ephemeral /tmp "
            "graph; set a persistent per-workspace graph store path."
        )
    return Path(raw)


def get_group_id() -> str:
    """Return the logical isolation group from ``GENESIS_GROUP_ID`` (D-GCW-2).

    The logical wall between workspaces sharing a backend. Env-pinned, fail-loud:
    an unset group_id must not silently pool this workspace into a default graph.
    """
    raw = _getenv(GROUP_ID_ENV)
    if not raw or not raw.strip():
        raise ConfigError(
            f"{GROUP_ID_ENV} is not set. Genesis refuses a default group_id; set an "
            "explicit per-workspace logical isolation group."
        )
    return raw.strip()


# --- Diary defaults (P2; ratified §26.0 / App E) --------------------------- #

DIARY_WINDOW_DAYS = 6
DIARY_TOKEN_BUDGET = 4000
RECENT_SESSIONS_DEPTH = 3


# --- Identity (principal + assistant) -------------------------------------- #
#
# The engine is owner-agnostic. Who the memory is *for* (the principal) and what
# the assistant persona is *called* are configuration, not code. Resolution order
# for each is: environment variable → config file (written by ``genesis-setup``) →
# a safe generic default. 12-Factor: env wins, but a persisted config file lets a
# one-time interactive setup answer stick without exporting a var every session.

import json  # noqa: E402  (kept next to its use for clarity)

PRINCIPAL_ENV = "GENESIS_PRINCIPAL"
ASSISTANT_ENV = "GENESIS_ASSISTANT"

# Generic, non-personal fallbacks. The principal default is a role word, not a
# name — the persona fence keys on "the principal" regardless of what it's called.
DEFAULT_PRINCIPAL = "Principal"
DEFAULT_ASSISTANT = "Daimon"

CONFIG_FILE_ENV = "GENESIS_CONFIG"


def _config_file_path() -> Path:
    """Location of the setup-written config file.

    Overridable with ``GENESIS_CONFIG`` (mainly for tests/isolation). Otherwise it
    lives beside the data root when one is configured, falling back to ``~/.genesis``.
    """
    override = _getenv(CONFIG_FILE_ENV)
    if override:
        return Path(override)
    root = _getenv(DATA_ROOT_ENV)
    if root:
        return Path(root) / "config.json"
    return Path.home() / ".genesis" / "config.json"


def _read_config_file() -> dict:
    """Read the setup-written config file, tolerating absence / corruption.

    Never raises for a missing or malformed file — identity has generic defaults,
    so a bad config file degrades to those rather than crashing the engine.
    """
    path = _config_file_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, IOError):
        return {}
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}
    return obj if isinstance(obj, dict) else {}


def get_principal() -> str:
    """Return the configured principal (who the memory is for).

    Resolution: ``GENESIS_PRINCIPAL`` → config file ``principal`` → ``"Principal"``.
    Always returns a non-empty string; never raises. The persona read-fence keys on
    the principal, so this must resolve to *something* even before setup runs.
    """
    env = _getenv(PRINCIPAL_ENV)
    if env and env.strip():
        return env.strip()
    val = _read_config_file().get("principal")
    if isinstance(val, str) and val.strip():
        return val.strip()
    return DEFAULT_PRINCIPAL


def get_assistant_name() -> str:
    """Return the configured assistant persona name (default ``Daimon``).

    Resolution: ``GENESIS_ASSISTANT`` → config file ``assistant`` → ``"Daimon"``.
    Always returns a non-empty string; never raises.
    """
    env = _getenv(ASSISTANT_ENV)
    if env and env.strip():
        return env.strip()
    val = _read_config_file().get("assistant")
    if isinstance(val, str) and val.strip():
        return val.strip()
    return DEFAULT_ASSISTANT


def write_identity_config(principal: str, assistant: str = DEFAULT_ASSISTANT) -> Path:
    """Persist principal + assistant to the config file; return its path.

    Written by ``genesis-setup``. Creates the parent directory as needed. Merges
    into any existing config so unrelated keys are preserved.
    """
    path = _config_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _read_config_file()
    data["principal"] = principal
    data["assistant"] = assistant
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
