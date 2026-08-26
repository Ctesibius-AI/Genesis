"""Tests for the DR-38 scrub-at-capture layer (spec v1.5 §4.2b.1)."""

from __future__ import annotations

import pytest

from genesis.scrub.scrubber import (
    make_placeholder,
    mask_home_paths,
    path_is_sensitive,
    scrub_text,
    shannon_entropy,
)


# --------------------------------------------------------------------------- #
# D-FB-5: home-path masking at the capture door (username never reaches disk)  #
# --------------------------------------------------------------------------- #

def test_mask_home_paths_users_and_home():
    assert mask_home_paths("/Users/alice/proj/x.py") == "~/proj/x.py"
    assert mask_home_paths("/home/bob/.ssh/id_rsa") == "~/.ssh/id_rsa"
    assert mask_home_paths("/Users/alice") == "~"                 # bare home dir


def test_mask_home_paths_leaves_non_home_untouched_and_is_idempotent():
    assert mask_home_paths("/usr/local/bin") == "/usr/local/bin"
    # A mid-path segment literally named "Users" is NOT a home prefix → left intact (no corruption).
    assert mask_home_paths("/opt/data/Users/notauser") == "/opt/data/Users/notauser"
    once = mask_home_paths("/Users/alice/x")
    assert mask_home_paths(once) == once                          # idempotent


def test_scrub_text_masks_username_at_the_door(monkeypatch):
    monkeypatch.delenv("GENESIS_LOCAL_HMAC_KEY", raising=False)
    res = scrub_text("error at /Users/realname/secret-project/app.py line 4")
    assert "realname" not in res.text          # the username never survives capture
    assert "~/secret-project/app.py" in res.text


# --------------------------------------------------------------------------- #
# D-FB-6: keyed-or-absent fingerprint; capture never fail-louds on a missing key #
# --------------------------------------------------------------------------- #

def test_scrub_without_key_emits_kindonly_placeholder_and_does_not_raise(monkeypatch):
    monkeypatch.delenv("GENESIS_LOCAL_HMAC_KEY", raising=False)
    monkeypatch.delenv("GENESYS_LOCAL_HMAC_KEY", raising=False)
    res = scrub_text("export API_KEY=sk-abcdef0123456789abcdef0123")   # must not raise (capture)
    assert "<redacted:secret kind=" in res.text
    assert "hash=" not in res.text                                     # no fingerprint when unkeyed


def test_scrub_is_idempotent_across_keyed_and_unkeyed(monkeypatch):
    text = "export API_KEY=sk-abcdef0123456789abcdef0123"
    monkeypatch.setenv("GENESIS_LOCAL_HMAC_KEY", "k")
    once = scrub_text(text).text                                       # keyed placeholder (has hash)
    assert scrub_text(once).text == once                              # re-scrub is a no-op
    monkeypatch.delenv("GENESIS_LOCAL_HMAC_KEY", raising=False)
    assert scrub_text(once).text == once   # the keyed placeholder survives re-scrub even without a key


# --------------------------------------------------------------------------- #
# Highest-risk surfaces (§4.2b.1: Bash cat .env / curl -H / export; Read dotfiles) #
# --------------------------------------------------------------------------- #

def test_env_file_secret_assignment_is_scrubbed():
    text = "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    res = scrub_text(text)
    assert res.redacted
    assert "wJalrXUtnFEMI" not in res.text
    assert "AWS_SECRET_ACCESS_KEY=" in res.text  # key name kept, value redacted
    assert "<redacted:secret" in res.text


def test_export_of_secret_is_scrubbed():
    text = "export API_KEY=sk-abcdef0123456789abcdef0123"
    res = scrub_text(text)
    assert res.redacted
    assert "sk-abcdef0123456789abcdef0123" not in res.text
    assert res.text.startswith("export API_KEY=")


def test_curl_authorization_header_bearer_is_scrubbed():
    text = 'curl -H "Authorization: Bearer abcdef0123456789ABCDEF0123456789" https://api'
    res = scrub_text(text)
    assert res.redacted
    assert "abcdef0123456789ABCDEF0123456789" not in res.text
    assert "Authorization: Bearer" in res.text  # header/scheme kept


def test_x_api_key_header_is_scrubbed():
    text = "X-Api-Key: 9f8e7d6c5b4a39281706abcdef012345"
    res = scrub_text(text)
    assert res.redacted
    assert "9f8e7d6c5b4a39281706abcdef012345" not in res.text


def test_aws_access_key_id_pattern():
    res = scrub_text("id is AKIAIOSFODNN7EXAMPLE here")
    assert res.redacted
    assert "AKIAIOSFODNN7EXAMPLE" not in res.text


def test_github_token_pattern():
    res = scrub_text("token ghp_" + "A" * 40)
    assert res.redacted
    assert "ghp_" + "A" * 40 not in res.text


def test_private_key_block_pattern():
    text = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEmicroblahblahblah\n"
        "-----END RSA PRIVATE KEY-----"
    )
    res = scrub_text(text)
    assert res.redacted
    assert "MIIEmicroblahblahblah" not in res.text


def test_database_url_with_inline_password_is_scrubbed():
    text = "DATABASE_URL=postgres://user:hunter2pass@db:5432/app"
    res = scrub_text(text)
    assert res.redacted
    assert "hunter2pass" not in res.text


# --------------------------------------------------------------------------- #
# High-entropy detection                                                       #
# --------------------------------------------------------------------------- #

def test_high_entropy_blob_is_scrubbed():
    blob = "Zx9Kq2Lm8Pv4Nw7Rt3Yb6Hs1Dc5Fg0Aj"  # random-looking, high entropy
    res = scrub_text(f"leaked secret {blob} end")
    assert res.redacted
    assert blob not in res.text
    assert any(m.via == "entropy" for m in res.matches)


def test_low_entropy_prose_not_scrubbed():
    text = "this is a perfectly ordinary sentence about deploying the application today"
    res = scrub_text(text)
    assert not res.redacted
    assert res.text == text


def test_shannon_entropy_monotonic():
    assert shannon_entropy("aaaaaaaa") < shannon_entropy("aB3xZ9qP")


# --------------------------------------------------------------------------- #
# R3 entropy allowlist — must NOT redact git SHAs / Genesis IDs / tombstone hashes #
# --------------------------------------------------------------------------- #

def test_r3_git_sha_not_redacted():
    # A 40-char git SHA is high-entropy hex but is provenance, not a secret.
    sha = "6c10e04f4c38fb35bb838cc8f01ae4f45fabcdef"
    res = scrub_text(f"see commit {sha} for details")
    assert not res.redacted, res.matches
    assert sha in res.text


def test_r3_genesis_deterministic_id_not_redacted():
    gid = "gen-20260815-001"
    res = scrub_text(f"episode {gid} was captured")
    assert not res.redacted
    assert gid in res.text


def test_r3_tombstone_hash_not_redacted():
    # 64-char hex HMAC digest — the tombstone's own hash. Must survive so the entropy
    # scrubber does not recursively eat the tombstones it wrote.
    digest = "a" * 64
    res = scrub_text(f"redacted hash={digest}")
    assert not res.redacted
    assert digest in res.text


def test_r3_does_not_shield_a_real_key_that_matches_a_pattern():
    # A real provider key must still be caught by pattern even if hex-ish. The AWS id
    # pattern wins over the entropy allowlist.
    res = scrub_text("AKIAIOSFODNN7EXAMPLE")
    assert res.redacted


# --------------------------------------------------------------------------- #
# Placeholder shape + idempotency                                              #
# --------------------------------------------------------------------------- #

def test_placeholder_shape_keyed_and_unkeyed(monkeypatch):
    # D-FB-6: no key set → kind-only placeholder (no hash → no confirm-a-guess oracle).
    monkeypatch.delenv("GENESIS_LOCAL_HMAC_KEY", raising=False)
    monkeypatch.delenv("GENESYS_LOCAL_HMAC_KEY", raising=False)
    assert make_placeholder("aws_access_key_id", "AKIAIOSFODNN7EXAMPLE") == \
        "<redacted:secret kind=aws_access_key_id>"

    # Key set → keyed HMAC fingerprint present, and it is NOT the retired raw sha256 prefix.
    import hashlib
    monkeypatch.setenv("GENESIS_LOCAL_HMAC_KEY", "test-key")
    ph = make_placeholder("aws_access_key_id", "AKIAIOSFODNN7EXAMPLE")
    assert ph.startswith("<redacted:secret kind=aws_access_key_id hash=") and ph.endswith(">")
    unkeyed = hashlib.sha256(b"AKIAIOSFODNN7EXAMPLE").hexdigest()[:12]
    assert f"hash={unkeyed}>" not in ph


def test_scrub_is_idempotent():
    text = "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    once = scrub_text(text).text
    twice = scrub_text(once).text
    assert once == twice


# --------------------------------------------------------------------------- #
# Sensitive path markers                                                        #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "path",
    ["/app/.env", "~/.aws/credentials", "/home/u/.ssh/id_rsa", "svc/service-account.json"],
)
def test_sensitive_paths_detected(path):
    assert path_is_sensitive(path)


def test_ordinary_path_not_sensitive():
    assert not path_is_sensitive("/app/src/main.py")
