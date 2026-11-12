"""
Content-policy enforcement - the one choke point every ``content`` field passes through
before storage (FR-AGENT-5).
"""

from __future__ import annotations

import re

from protocol.capture import POLICY_DESCRIPTIONS

METADATA_ONLY = "metadata-only"
REDACTED = "redacted"
FULL = "full"
POLICIES = (METADATA_ONLY, REDACTED, FULL)

DEFAULT_POLICY = METADATA_ONLY
DEFAULT_MIN_TOKEN_LEN = 4

_STRING_LITERAL = re.compile(r"""(['"])(?:\\.|(?!\1)[\s\S])*?\1""")
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:password|passwd|pwd|token|secret|credential|authorization|"
    r"[a-z0-9_]*(?:password|passwd|token|secret|credential|api[_-]?key|"
    r"access[_-]?key|private[_-]?key)[a-z0-9_]*)\b\s*[:=]\s*)"
    r"(?:\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|"
    r"Bearer\s+[^\s,;]+|[^\s,;]+)"
)


def normalize_policy(policy: str | None) -> str:
    """
    Coerce to a known policy; unknown/blank collapses to the safe default
    (``metadata-only``) - a misconfiguration must never *widen* capture.
    """
    return policy if policy in POLICIES else DEFAULT_POLICY


def policy_description(policy: str | None) -> str:
    return POLICY_DESCRIPTIONS[normalize_policy(policy)]


def apply_policy(
    text: str | None, policy: str | None, *, min_token_len: int = DEFAULT_MIN_TOKEN_LEN
) -> str | None:
    """Return the storable form of ``text`` under ``policy``."""
    policy = normalize_policy(policy)
    if text is None or policy == METADATA_ONLY:
        return None
    if policy == FULL:
        return text
    return redact_text(text, min_token_len=min_token_len)


def redact_text(text: str, *, min_token_len: int = DEFAULT_MIN_TOKEN_LEN) -> str:
    """Mask string literals then long identifiers (the ``redacted`` level)."""
    # Scrub credential values before general literal/identifier masking. Long
    # identifiers alone do not protect digit-only values such as password=123456.
    masked = _SENSITIVE_ASSIGNMENT.sub(lambda m: m.group(1) + "***", text)
    masked = _STRING_LITERAL.sub(lambda m: m.group(1) + "***" + m.group(1), masked)

    def mask_ident(m: re.Match) -> str:
        tok = m.group(0)
        return "*" * len(tok) if len(tok) >= min_token_len else tok

    return _IDENTIFIER.sub(mask_ident, masked)
