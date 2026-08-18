"""DR-38 mechanism (2): the redaction verb — tombstone-in-place (spec v1.5 §4.2b).

The "un-write" that files-as-truth (DR-24) was missing. Secrets that slip past
scrub-at-capture demand a way to *remove* the bytes from a truth file after the fact
while keeping the ledger append-honest.

Mechanism: the bytes are physically removed and replaced with a tombstone record:

    {redacted: true, at: <date>, reason, hash: HMAC(local-Genesys-key, removed-content),
     actor}

⚠ R4 — **keyed HMAC, NOT plain sha256.** A bare digest is a dictionary oracle for weak
secrets (short passwords); an HMAC with a local key keeps proof-of-what-was-there for
the *owner* while the public oracle dies. The key comes from config/env
(``genesys.config.get_local_hmac_key``) and is never hardcoded.

The removal is itself a logged event (the returned ``Tombstone`` is the log entry) —
append-honest: the fact that a redaction happened stays on the record, only the secret
bytes are gone.

⚠ Snapshot propagation and the R2 cascade to derived graph copies are NOT done here.
Snapshot propagation and cascade both need machinery that does not exist in Step 0
(snapshots, graph). See ``cascade.py`` for the stubbed cascade interface.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

from genesys.config import get_local_hmac_key


def tombstone_hash(removed_content: str, *, key: Optional[bytes] = None) -> str:
    """Compute the R4 keyed proof-of-what-was-there: HMAC-SHA256(local-key, content).

    Deliberately an HMAC, not a plain ``sha256`` — see module docstring / DR-38 R4. If
    ``key`` is None it is read from the environment via ``get_local_hmac_key`` (raises
    ``ConfigError`` when unset — no silent unkeyed fallback).
    """
    if key is None:
        key = get_local_hmac_key()
    return hmac.new(key, removed_content.encode("utf-8"), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class Tombstone:
    """An append-honest record that a span of content was redacted in place.

    ``hash`` is the keyed HMAC (R4), NOT a plain digest — it proves *what* was there to
    the owner (who holds the key) without revealing it or being a public oracle.
    """

    redacted: bool  # always True; present so the serialized shape matches the spec
    at: str  # ISO-8601 date the redaction happened (spec: `at: <date>`)
    reason: str
    hash: str  # HMAC(local-key, removed-content) — R4
    actor: str  # who performed the redaction

    def as_dict(self) -> dict:
        return {
            "redacted": self.redacted,
            "at": self.at,
            "reason": self.reason,
            "hash": self.hash,
            "actor": self.actor,
        }


# A visible marker left in the truth file where the bytes used to be. Carries the keyed
# hash so the tombstone in the file and the logged Tombstone record correlate.
def tombstone_marker(ts: Tombstone) -> str:
    return f"<tombstone redacted at={ts.at} reason={ts.reason!r} hash={ts.hash} actor={ts.actor}>"


def redact_in_place(
    content: str,
    secret: str,
    *,
    reason: str,
    actor: str,
    key: Optional[bytes] = None,
    at: Optional[date] = None,
) -> tuple[str, Tombstone]:
    """Redact ``secret`` out of ``content`` in place, returning (new_content, tombstone).

    The secret's bytes are physically removed and replaced with a tombstone marker; the
    returned ``Tombstone`` is the append-honest log entry (keyed hash = R4). The caller
    is responsible for persisting both the rewritten content and the tombstone record,
    and — once those layers exist — for propagating to snapshots and running the R2
    cascade (see ``cascade.py``).

    Raises ``ValueError`` if ``secret`` does not occur in ``content`` (redacting nothing
    would produce a dishonest tombstone).
    """
    if secret not in content:
        raise ValueError("secret not found in content; refusing to write an empty tombstone")

    when = at or datetime.now(timezone.utc).date()
    h = tombstone_hash(secret, key=key)
    ts = Tombstone(
        redacted=True,
        at=when.isoformat(),
        reason=reason,
        hash=h,
        actor=actor,
    )
    new_content = content.replace(secret, tombstone_marker(ts))
    return new_content, ts
