"""DR-38 mechanism (1): scrub-at-capture (spec v1.5 §4.2b).

Deterministic secret detection — regex/patterns + high-entropy-string detection —
that runs *at mirror time, on both projections, before the first byte hits disk*.
Matches are replaced with a typed placeholder ``<redacted:secret kind=… hash=…>``.

Highest-risk surfaces called out by the spec (§4.2b.1):
  - ``Bash``: ``cat .env``, ``curl -H`` auth headers, ``export`` of secrets
  - ``Read``: dotfiles / key files / contracts
  - env echoes; known key-file *paths*

Design notes / fidelity:
  - Pure functions. No I/O, no network, no LLM on the hot path (§4.2b.1: "not LLM
    detection on the hot path" — an optional deeper LLM pass is a *slow-lane* concern
    out of scope for Step 0).
  - Deterministic detection is best-effort with false-negatives by design — that is
    exactly why the redaction verb (mechanism 2) exists as a backstop.
  - The placeholder ``hash`` here is a short *keyed* (HMAC, ``GENESIS_LOCAL_HMAC_KEY``)
    content fingerprint used only to correlate identical redactions within a stream
    (e.g. the same key appearing in two projections) — and it is OMITTED entirely when no
    key is set (D-FB-6). It is NOT the redaction-verb tombstone hash (also keyed, R4,
    ``redaction.py``). The former unkeyed ``sha256(secret)[:12]`` was retired: truncation
    stops it *identifying* an unknown secret but not *confirming a guessed one*. Never a
    proof-of-what-was-there.

R3 entropy allowlist (§4.2b.1): high-entropy detection MUST NOT flag known non-secret
high-entropy shapes — git SHAs (provenance), Genesis deterministic IDs, and the
tombstones' own hash values — or it corrupts the provenance the system runs on and
recursively eats its own tombstones. Implemented in ``_is_allowlisted``.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import re
from dataclasses import dataclass, field
from typing import List, Optional

from genesis.config import get_local_hmac_key_optional


# --------------------------------------------------------------------------- #
# Typed placeholder                                                           #
# --------------------------------------------------------------------------- #

def _fingerprint(secret: str) -> Optional[str]:
    """Keyed correlation fingerprint for the *placeholder* only, or None when unkeyed (D-FB-6).

    HMAC-SHA256 with the local key (``GENESIS_LOCAL_HMAC_KEY``) when set, truncated — it correlates
    identical redactions within/across projections for a keyed user. When NO key is set it returns
    None (the placeholder carries no hash): capture must never fail-loud on a missing key, and the
    former unkeyed ``sha256(secret)[:12]`` was a confirm-a-guess oracle (hash a candidate, compare
    the prefix) — retired. Still never a proof-of-what-was-there (that is the R4 tombstone).
    """
    key = get_local_hmac_key_optional()
    if key is None:
        return None
    return hmac.new(key, secret.encode("utf-8"), hashlib.sha256).hexdigest()[:12]


def make_placeholder(kind: str, secret: str) -> str:
    """Build the typed placeholder (§4.2b.1): ``<redacted:secret kind=… hash=…>`` when a local key is
    set, else ``<redacted:secret kind=…>`` (kind-only, no fingerprint) — D-FB-6."""
    fp = _fingerprint(secret)
    if fp is None:
        return f"<redacted:secret kind={kind}>"
    return f"<redacted:secret kind={kind} hash={fp}>"


# Recognizes an already-emitted placeholder (with OR without a hash — D-FB-6) so re-scrubbing is
# idempotent and the entropy pass never treats a placeholder's own fingerprint as a fresh secret.
_PLACEHOLDER_RE = re.compile(r"<redacted:secret kind=[^\s>]+(?: hash=[0-9a-f]+)?>")


# --------------------------------------------------------------------------- #
# Home-path masking (D-FB-5): the real username never reaches disk or the model #
# --------------------------------------------------------------------------- #

# /Users/<name> and /home/<name> → ~ (keeps the rest of the path). Applied at the capture door for
# both projections, BEFORE secret detection. Idempotent: masked text has no home prefix left. The
# (?<![\w]) boundary anchors to a real path start (space/quote/=/start), so a mid-path segment that
# happens to be named "Users" (e.g. /opt/data/Users/x) is NOT rewritten — masking a home prefix, not
# corrupting an unrelated path.
_HOME_PATH_RE = re.compile(r"(?<![\w])/(?:Users|home)/[^/\s]+")


def mask_home_paths(text: str) -> str:
    """Rewrite home-directory prefixes ``/Users/<name>`` / ``/home/<name>`` to ``~`` (D-FB-5).

    A pure normalization applied at capture so the local username never enters the store or reaches
    the model. Only the home *prefix* is rewritten; the trailing path is preserved
    (``/Users/alice/proj`` → ``~/proj``). Non-home paths are untouched.
    """
    if not text:
        return text
    return _HOME_PATH_RE.sub("~", text)


# --------------------------------------------------------------------------- #
# R3 entropy allowlist                                                         #
# --------------------------------------------------------------------------- #

# git SHA: 7..40 lowercase hex. Genesis deterministic IDs and tombstone hashes are
# matched by their own shapes below.
_GIT_SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b")

# Genesis deterministic episode ID: day + sequence (DR-24 "named by the deterministic
# episode ID (day + sequence)"). Shape: gen-YYYYMMDD-NNN (also accept an optional
# trailing token). Kept liberal but anchored to the ``gen-`` prefix so it can't be
# spoofed by an arbitrary high-entropy blob.
_GENESIS_ID_RE = re.compile(r"\bgen-\d{8}-\d{3,}\b")

# Tombstone hash values are hex HMAC-SHA256 digests (64 hex chars) that appear inside a
# tombstone context. We exempt a bare 64-char hex token so the entropy scrubber does not
# "recursively eat the tombstones it just wrote" (§4.2b.1 R3).
_TOMBSTONE_HASH_RE = re.compile(r"\b[0-9a-f]{64}\b")


def _is_allowlisted(token: str) -> bool:
    """R3: return True if ``token`` is a known non-secret high-entropy shape.

    Exempts git SHAs, Genesis deterministic IDs, and tombstone hash digests. Only
    consulted by the *entropy* pass — deterministic secret patterns (below) still win,
    so an actual key that happens to be all-hex is caught by pattern, not entropy.
    """
    return bool(
        _GENESIS_ID_RE.fullmatch(token)
        or _TOMBSTONE_HASH_RE.fullmatch(token)
        or _GIT_SHA_RE.fullmatch(token)
    )


# --------------------------------------------------------------------------- #
# Deterministic patterns (mechanism 1, first line)                            #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class _Pattern:
    kind: str
    regex: re.Pattern
    # If set, the capture group holding the secret value to replace (rest of the match
    # is context we keep, e.g. the ``Authorization:`` header name). If None, the whole
    # match is the secret.
    group: Optional[int] = None


# Ordered, most-specific first. Each targets a highest-risk surface from §4.2b.1.
_PATTERNS: List[_Pattern] = [
    # --- Known provider key formats (whole match is the secret) ---
    _Pattern("aws_access_key_id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    _Pattern("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    _Pattern("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    _Pattern("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    _Pattern("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    _Pattern("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    _Pattern(
        "private_key_block",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"
            r".*?-----END (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----",
            re.DOTALL,
        ),
    ),
    _Pattern(
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b"),
    ),
    # --- HTTP auth headers: curl -H "Authorization: Bearer …" (§4.2b.1 curl -H) ---
    # Keep the header name + scheme, redact the credential (group 2).
    _Pattern(
        "auth_header",
        re.compile(
            r"(Authorization\s*:\s*(?:Bearer|Basic|Token)\s+)([A-Za-z0-9._~+/=-]{8,})",
            re.IGNORECASE,
        ),
        group=2,
    ),
    _Pattern(
        "api_key_header",
        re.compile(
            r"((?:X-Api-Key|X-Auth-Token|Api-Key|apikey)\s*:\s*)([A-Za-z0-9._~+/=-]{8,})",
            re.IGNORECASE,
        ),
        group=2,
    ),
    # --- KEY=VALUE assignments: .env lines, `export`, env echoes (§4.2b.1) ---
    # Trigger on a secret-ish key name; keep the key, redact the value (group 3).
    _Pattern(
        "env_assignment",
        re.compile(
            # Leading identifier chars are OPTIONAL (`*`, not a mandatory first char):
            # keys that *start with* the secret word (DATABASE_URL, PASSWORD, TOKEN,
            # SECRET) must match too, not only keys where the word is a suffix
            # (AWS_SECRET_ACCESS_KEY). A mandatory leading `[A-Za-z_]` silently missed
            # word-initial keys — e.g. `DATABASE_URL=…` leaked its inline password.
            r"(?im)^(\s*(?:export\s+)?)"
            r"([A-Za-z0-9_]*"
            r"(?:SECRET|TOKEN|PASSWORD|PASSWD|API_?KEY|ACCESS_?KEY|PRIVATE_?KEY|"
            r"CLIENT_?SECRET|AUTH|CREDENTIAL|SESSION|DATABASE_URL|DB_PASS)"
            r"[A-Za-z0-9_]*)"
            r"\s*=\s*"
            r"(\"[^\"]*\"|'[^']*'|[^\s#]+)"
        ),
        group=3,
    ),
]


# --------------------------------------------------------------------------- #
# High-entropy detection (mechanism 1, second line)                           #
# --------------------------------------------------------------------------- #

# Candidate tokens for entropy scoring: long-ish contiguous runs of base64/hex/url-safe
# characters. Split on whitespace and common delimiters happens via the token regex.
_ENTROPY_TOKEN_RE = re.compile(r"[A-Za-z0-9+/=_-]{20,}")

# Shannon-entropy threshold (bits/char). ~4.0+ is characteristic of random secrets;
# English prose and code identifiers sit well below. Conservative to limit false
# positives; the redaction verb is the backstop for what slips through.
_ENTROPY_MIN_BITS_PER_CHAR = 4.0
_ENTROPY_MIN_LEN = 20


def shannon_entropy(s: str) -> float:
    """Shannon entropy in bits per character."""
    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


# --------------------------------------------------------------------------- #
# Result types                                                                #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ScrubMatch:
    """One redaction applied by the scrubber."""

    kind: str
    fingerprint: str  # short non-keyed correlation id (matches placeholder hash=)
    via: str  # "pattern" or "entropy"


@dataclass
class ScrubResult:
    """Outcome of scrubbing one string."""

    text: str
    matches: List[ScrubMatch] = field(default_factory=list)

    @property
    def redacted(self) -> bool:
        return bool(self.matches)


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #

def scrub_text(text: str) -> ScrubResult:
    """Scrub ``text`` deterministically: patterns first, then entropy (R3-filtered).

    Returns a ``ScrubResult`` with the redacted text and the list of matches. Pure and
    idempotent: re-scrubbing already-scrubbed text is a no-op (placeholders are skipped).
    """
    if text is None:
        return ScrubResult(text=text or "", matches=[])

    # D-FB-5: mask home-dir prefixes (/Users/<name>, /home/<name>) → ~ FIRST, at the capture door, so
    # the real username never reaches disk or the model — then run secret detection on the masked text.
    text = mask_home_paths(text)

    matches: List[ScrubMatch] = []

    # Protect already-emitted placeholders from both passes.
    placeholder_spans = [m.span() for m in _PLACEHOLDER_RE.finditer(text)]

    def _in_placeholder(start: int, end: int) -> bool:
        return any(ps <= start and end <= pe for ps, pe in placeholder_spans)

    # --- Pass 1: deterministic patterns -------------------------------------
    # We rebuild the string left-to-right, applying non-overlapping pattern matches.
    for pat in _PATTERNS:
        def _repl(m: re.Match, _pat=pat) -> str:
            # Guard on the span of the SECRET we would actually redact — the whole match
            # for group-less patterns, else just the secret group. Checking the whole
            # match instead let a context-keeping pattern (e.g. env_assignment) re-redact
            # a fragment of an already-emitted placeholder on re-scrub, breaking
            # idempotency: the placeholder's `<redacted:secret` head matched the value
            # group even though it sits inside a placeholder.
            _sec_start = m.start() if _pat.group is None else m.start(_pat.group)
            _sec_end = m.end() if _pat.group is None else m.end(_pat.group)
            if _in_placeholder(_sec_start, _sec_end):
                return m.group(0)
            if _pat.group is None:
                secret = m.group(0)
                placeholder = make_placeholder(_pat.kind, secret)
                matches.append(
                    ScrubMatch(_pat.kind, _fingerprint(secret) or "", "pattern")
                )
                return placeholder
            # Keep surrounding context groups; redact only the secret group.
            secret = m.group(_pat.group)
            # Strip surrounding quotes for a stable fingerprint but keep them in output.
            quote = ""
            inner = secret
            if len(secret) >= 2 and secret[0] in "\"'" and secret[-1] == secret[0]:
                quote = secret[0]
                inner = secret[1:-1]
            placeholder = make_placeholder(_pat.kind, inner)
            matches.append(ScrubMatch(_pat.kind, _fingerprint(inner) or "", "pattern"))
            # Reconstruct the whole match, replacing only the secret group's span
            # (offsets are relative to the start of the full match).
            full = m.group(0)
            base = m.start(0)
            gstart = m.start(_pat.group) - base
            gend = m.end(_pat.group) - base
            return full[:gstart] + f"{quote}{placeholder}{quote}" + full[gend:]

        text = pat.regex.sub(_repl, text)
        # Recompute placeholder spans after each substitution round.
        placeholder_spans = [m.span() for m in _PLACEHOLDER_RE.finditer(text)]

    # --- Pass 2: high-entropy detection (R3-filtered) -----------------------
    def _entropy_repl(m: re.Match) -> str:
        if _in_placeholder(m.start(), m.end()):
            return m.group(0)
        token = m.group(0)
        if len(token) < _ENTROPY_MIN_LEN:
            return token
        # R3 allowlist: never flag git SHAs / Genesis IDs / tombstone hashes.
        if _is_allowlisted(token):
            return token
        if shannon_entropy(token) < _ENTROPY_MIN_BITS_PER_CHAR:
            return token
        placeholder = make_placeholder("high_entropy", token)
        matches.append(ScrubMatch("high_entropy", _fingerprint(token) or "", "entropy"))
        return placeholder

    text = _ENTROPY_TOKEN_RE.sub(_entropy_repl, text)

    return ScrubResult(text=text, matches=matches)


# Known key-file / dotfile paths whose *contents* are high-risk (§4.2b.1: "scrub known
# key-file paths"). Used by the capture layer to decide when a Read/Bash surface is
# sensitive even before pattern matching. Substring match against a path.
SENSITIVE_PATH_MARKERS = (
    ".env",
    ".aws/credentials",
    ".ssh/id_",
    "id_rsa",
    "id_ed25519",
    ".npmrc",
    ".netrc",
    ".pgpass",
    "secrets",
    "credentials.json",
    "service-account",
    ".pem",
    ".key",
)


def path_is_sensitive(path: str) -> bool:
    """Return True if ``path`` looks like a known key/secret file (§4.2b.1)."""
    if not path:
        return False
    low = path.lower()
    return any(marker in low for marker in SENSITIVE_PATH_MARKERS)
