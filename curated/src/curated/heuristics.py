"""Agent-authorship heuristics as a versioned registry (FR-CUR-2).

Identifying which mined activity was authored by an AI agent is *inference*,
not fact - so it is never inline cleverness buried in the adapter. Each
heuristic is a named, versioned, cited entry with its known failure modes,
and every heuristic that fires on a dataset is recorded (id + version) in
that dataset's validity-threats record. A reader of the resulting paper can
see exactly how "agent-authored" was decided and where it might be wrong.

Grounding: the heuristics catalogue in `mining-coding-agent-activity` and
`aidev-ai-coding-agents-github` (bot flags, co-author trailers,
agent-signature patterns).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ActorSignal:
    """What a heuristic inspects: the surface features of a mined actor /
    authorship record, content-free (a login shape, trailer flags, a bot
    flag), never raw message bodies."""

    login: str
    is_bot_flagged: bool = False
    #: Co-author trailers present on the commit (values already shape-only:
    #: the login part, lowercased; never full free-text).
    coauthor_logins: tuple[str, ...] = ()
    #: Named agent-signature tokens the fetch layer already extracted from
    #: structured fields (e.g. a PR app slug), never scraped from prose.
    signature_tokens: tuple[str, ...] = ()


@dataclass(frozen=True)
class Heuristic:
    """One versioned authorship heuristic."""

    id: str
    version: int
    cite: str
    known_failure_modes: tuple[str, ...]
    fn: Callable[[ActorSignal], bool]
    description: str = ""

    def matches(self, signal: ActorSignal) -> bool:
        return self.fn(signal)


# Known agent app/bot slugs seen in the mining literature. Kept as a small,
# explicit, versioned set - extending it bumps the heuristic version so the
# threats record stays honest about which rule ran.
_KNOWN_BOT_SUFFIXES = ("[bot]", "-bot", "-ai")
_KNOWN_AGENT_TOKENS = frozenset(
    {"copilot", "cursor", "devin", "sweep", "claude", "codegen", "aider"}
)


def _bot_suffix(sig: ActorSignal) -> bool:
    login = sig.login.lower()
    return sig.is_bot_flagged or any(login.endswith(s) for s in _KNOWN_BOT_SUFFIXES)


def _coauthor_trailer(sig: ActorSignal) -> bool:
    return any(
        any(tok in co for tok in _KNOWN_AGENT_TOKENS) for co in sig.coauthor_logins
    )


def _agent_signature(sig: ActorSignal) -> bool:
    return any(
        tok.lower() in _KNOWN_AGENT_TOKENS for tok in sig.signature_tokens
    ) or any(tok in sig.login.lower() for tok in _KNOWN_AGENT_TOKENS)


#: The registry. The three named heuristics the spec requires as a minimum;
#: add more freely, each with id/version/cite/failure-modes.
HEURISTICS: tuple[Heuristic, ...] = (
    Heuristic(
        id="bot-suffix",
        version=1,
        cite="aidev-ai-coding-agents-github",
        known_failure_modes=(
            "a human renames their bot account without the suffix",
            "a non-agent CI bot is counted as agent authorship",
        ),
        fn=_bot_suffix,
        description="GitHub bot flag, or a login ending in a known bot suffix.",
    ),
    Heuristic(
        id="coauthor-trailer",
        version=1,
        cite="mining-coding-agent-activity",
        known_failure_modes=(
            "the trailer is copied forward by a human across unrelated commits",
            "an agent that omits the trailer is missed",
        ),
        fn=_coauthor_trailer,
        description="A Co-authored-by trailer naming a known agent.",
    ),
    Heuristic(
        id="agent-signature",
        version=1,
        cite="mining-coding-agent-activity",
        known_failure_modes=(
            "a human embeds an agent token in their own login vanity string",
            "a new agent whose slug is not yet in the known set is missed",
        ),
        fn=_agent_signature,
        description="A known agent app slug in the PR app or the login.",
    ),
)


@dataclass
class AuthorshipVerdict:
    """The result of classifying an actor: whether it reads as agent-authored
    and which heuristic ids (with versions) decided it - the audit trail that
    lands in the threats record."""

    is_agent: bool
    fired: list[str] = field(default_factory=list)


def classify(
    signal: ActorSignal, heuristics: tuple[Heuristic, ...] = HEURISTICS
) -> AuthorshipVerdict:
    """Classify an actor; ``is_agent`` is true if any heuristic fires. Records
    every firing heuristic as ``id@version``."""
    fired = [f"{h.id}@{h.version}" for h in heuristics if h.matches(signal)]
    return AuthorshipVerdict(is_agent=bool(fired), fired=fired)


def heuristic_records(fired_ids: set[str]) -> list[dict]:
    """The threats-record entries for the heuristics that fired on a dataset
    (id, version, knownFailureModes, cite). ``fired_ids`` are ``id@version``
    strings collected across the run."""
    bare = {f.split("@", 1)[0] for f in fired_ids}
    return [
        {
            "id": h.id,
            "version": h.version,
            "knownFailureModes": list(h.known_failure_modes),
            "cite": h.cite,
        }
        for h in HEURISTICS
        if h.id in bare
    ]


# A parsing helper the adapter uses to keep the signature-token extraction in
# one place (structured fields only, never prose scraping).
_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")


def tokenize_slug(slug: str) -> tuple[str, ...]:
    """Split a structured slug (e.g. an app name) into lowercase tokens for
    signature matching."""
    return tuple(t for t in _TOKEN_SPLIT.split(slug.lower()) if t)
