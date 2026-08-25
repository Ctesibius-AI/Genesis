"""Tests for the DR-38 redaction verb / tombstone (spec v1.5 §4.2b.2, R4)."""

from __future__ import annotations

import hashlib
import hmac

import pytest

from genesis.config import ConfigError, HMAC_KEY_ENV
from genesis.scrub.cascade import (
    CascadeNotImplementedError,
    CascadeRequest,
    CascadeStub,
)
from genesis.scrub.redaction import redact_in_place, tombstone_hash


LOCAL_KEY = b"test-local-genesis-key"


# --------------------------------------------------------------------------- #
# R4 — keyed HMAC, NOT plain sha256                                            #
# --------------------------------------------------------------------------- #

def test_tombstone_hash_is_keyed_hmac_not_plain_sha256():
    secret = "hunter2"
    h = tombstone_hash(secret, key=LOCAL_KEY)
    expected = hmac.new(LOCAL_KEY, secret.encode(), hashlib.sha256).hexdigest()
    assert h == expected
    # And it must NOT equal a bare sha256 digest (that would be the dictionary oracle).
    assert h != hashlib.sha256(secret.encode()).hexdigest()


def test_tombstone_hash_depends_on_key():
    secret = "hunter2"
    h1 = tombstone_hash(secret, key=b"key-one")
    h2 = tombstone_hash(secret, key=b"key-two")
    assert h1 != h2


def test_tombstone_hash_reads_key_from_env_when_not_passed(monkeypatch):
    monkeypatch.setenv(HMAC_KEY_ENV, "env-key")
    h = tombstone_hash("s")
    expected = hmac.new(b"env-key", b"s", hashlib.sha256).hexdigest()
    assert h == expected


def test_tombstone_hash_refuses_without_key(monkeypatch):
    monkeypatch.delenv(HMAC_KEY_ENV, raising=False)
    with pytest.raises(ConfigError):
        tombstone_hash("s")


# --------------------------------------------------------------------------- #
# Tombstone-in-place: bytes removed, append-honest record                      #
# --------------------------------------------------------------------------- #

def test_redact_in_place_removes_bytes_and_returns_tombstone():
    content = "the deploy key is hunter2pass and it works"
    new_content, ts = redact_in_place(
        content, "hunter2pass", reason="leaked in dialogue", actor="principal", key=LOCAL_KEY
    )
    assert "hunter2pass" not in new_content
    assert "tombstone" in new_content
    assert ts.redacted is True
    assert ts.reason == "leaked in dialogue"
    assert ts.actor == "principal"
    # The tombstone hash is the keyed HMAC of the removed content.
    assert ts.hash == hmac.new(LOCAL_KEY, b"hunter2pass", hashlib.sha256).hexdigest()


def test_redact_in_place_tombstone_hash_is_not_plain_digest():
    _, ts = redact_in_place(
        "x secret_val y", "secret_val", reason="r", actor="a", key=LOCAL_KEY
    )
    assert ts.hash != hashlib.sha256(b"secret_val").hexdigest()


def test_redact_in_place_raises_if_secret_absent():
    with pytest.raises(ValueError):
        redact_in_place("no secret here", "missing", reason="r", actor="a", key=LOCAL_KEY)


def test_tombstone_serializes_to_spec_shape():
    _, ts = redact_in_place("a b c", "b", reason="r", actor="a", key=LOCAL_KEY)
    d = ts.as_dict()
    assert set(d) == {"redacted", "at", "reason", "hash", "actor"}


# --------------------------------------------------------------------------- #
# R2 cascade — stubbed, must NOT fake success                                  #
# --------------------------------------------------------------------------- #

def test_cascade_stub_raises_not_implemented():
    stub = CascadeStub()
    req = CascadeRequest(
        episode_id="gen-20260815-001",
        tombstone_hash="deadbeef",
        reason="r",
        actor="a",
    )
    with pytest.raises(CascadeNotImplementedError):
        stub.cascade(req)
