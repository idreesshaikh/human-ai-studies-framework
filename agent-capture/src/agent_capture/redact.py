"""Content-policy enforcement - the one choke point every ``content`` field
passes through before storage (FR-AGENT-5).

The active policy is protocol-declared (``instruments.agentCapture.
contentPolicy``) and consent-matched: the consent form the study ships
states the active policy's plain-language description verbatim (MP-08 study
kit), so what is captured is exactly what the participant agreed to.

Three levels, tightest first:

- ``metadata-only`` (the pilot default): text is stripped entirely -
  :func:`apply_policy` returns ``None`` and no ``content`` field is emitted.
  Only sizes, counts, and timings survive. This is the level the
  grep-the-output test asserts against (same discipline as FR-ETH-4).
- ``redacted``: string literals and identifiers of >= ``min_token_len``
  characters are masked, so conversation *shape* survives without leaking
  code content or secrets.
- ``full``: passthrough (only under an explicit consent clause).
"""

from __future__ import annotations

import re

METADATA_ONLY = "metadata-only"
REDACTED = "redacted"
FULL = "full"
POLICIES = (METADATA_ONLY, REDACTED, FULL)

DEFAULT_POLICY = METADATA_ONLY
DEFAULT_MIN_TOKEN_LEN = 4

#: Plain-language descriptions the consent-form generator interpolates
#: verbatim (FR-AGENT-5). Keep these readable by a study participant, not an
#: engineer - they are the text a person consents to.
POLICY_DESCRIPTIONS = {
    METADATA_ONLY: (
        "Only the shape of your conversation with the AI assistant is "
        "recorded: how many messages, how long they were, when they were "
        "sent, and which tools the assistant used. The words of the "
        "conversation - your prompts and the assistant's replies - are "
        "never stored."
    ),
    REDACTED: (
        "The text of your conversation with the AI assistant is recorded "
        "with identifiers, string literals, and long words masked, so the "
        "structure of the exchange is kept but code content and any secrets "
        "you typed are removed before storage."
    ),
    FULL: (
        "The full text of your conversation with the AI assistant - your "
        "prompts and the assistant's replies - is recorded and stored for "
        "analysis."
    ),
}

# A string literal in single or double quotes (kept simple - shape, not a
# parser); and a run of identifier-ish characters.
_STRING_LITERAL = re.compile(r"""(['"]).*?\1""", re.DOTALL)
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def normalize_policy(policy: str | None) -> str:
    """Coerce to a known policy; unknown/blank collapses to the safe default
    (``metadata-only``) - a misconfiguration must never *widen* capture."""
    return policy if policy in POLICIES else DEFAULT_POLICY


def policy_description(policy: str | None) -> str:
    return POLICY_DESCRIPTIONS[normalize_policy(policy)]


def apply_policy(
    text: str | None,
    policy: str | None,
    *,
    min_token_len: int = DEFAULT_MIN_TOKEN_LEN,
) -> str | None:
    """Return the storable form of ``text`` under ``policy``.

    ``None`` means *emit no content field at all* (metadata-only, or no text
    to begin with). This is the single function the transcript normalizer
    routes every prompt/response string through.
    """
    policy = normalize_policy(policy)
    if text is None or policy == METADATA_ONLY:
        return None
    if policy == FULL:
        return text
    return redact_text(text, min_token_len=min_token_len)


def redact_text(text: str, *, min_token_len: int = DEFAULT_MIN_TOKEN_LEN) -> str:
    """Mask string literals then long identifiers (the ``redacted`` level)."""
    masked = _STRING_LITERAL.sub(lambda m: m.group(1) + "***" + m.group(1), text)

    def mask_ident(m: re.Match) -> str:
        tok = m.group(0)
        return "*" * len(tok) if len(tok) >= min_token_len else tok

    return _IDENTIFIER.sub(mask_ident, masked)
