"""The GitHub mining adapter (FR-CUR-2).

Reads pull requests (with their commits and reviews) matching the sampling
frame and emits :class:`NormalizedEvent` rows. Authorship is classified by
the versioned heuristic registry; every firing heuristic is collected so the
threats record can name it.

The adapter talks to a :class:`Fetcher` - either the offline
:class:`~curated.cassette.Cassette` (tests, demo, CI) or a live HTTP client.
It never imports a networking library directly, so the whole leg runs with
zero tokens and zero network against a committed cassette (Slice D).

Determinism (the idempotency guarantee, F1.2): given the same source data,
the adapter walks PRs in a fixed order and assigns ``seq`` from a *per-session*
counter, so re-mining produces the identical ``(session_id, source, seq)`` for
every event - the middleware's unique constraint then drops replays silently,
no new dedup machinery.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from curated.contract import (
    CoverageEstimate,
    Cursor,
    CursorCheckpoint,
    NormalizedEvent,
    RunItem,
    SamplingFrame,
)
from curated.heuristics import ActorSignal, classify, tokenize_slug
from curated.pseudonymize import pseudonym

SOURCE = "github"
#: Emit a checkpoint every N pull requests, so an interrupted job resumes
#: near where it stopped rather than restarting the page.
CHECKPOINT_EVERY = 5


class Fetcher(Protocol):
    """The minimal API the adapter needs. The cassette and a live client both
    satisfy it; a rate-limit is signalled by raising
    :class:`~curated.cassette.RateLimited`."""

    def get(self, method: str, path: str, params: dict | None = None) -> object: ...


class DroppedCounter:
    """Collects per-reason drop counts for the coverage record (why a
    candidate PR did not become data)."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def drop(self, reason: str) -> None:
        self.counts[reason] = self.counts.get(reason, 0) + 1


class GitHubAdapter:
    """Mines PRs/commits/reviews from GitHub (or a cassette)."""

    source = SOURCE

    def __init__(self, fetcher: Fetcher, salt: str) -> None:
        self._fetch = fetcher
        self._salt = salt
        #: Populated during ``run`` for the threats record.
        self.fired_heuristics: set[str] = set()
        self.dropped = DroppedCounter()
        self.retrieved = 0

    # ------------------------------------------------------------------ plan

    def plan(self, frame: SamplingFrame) -> CoverageEstimate:
        q = self._search_query(frame)
        body = self._fetch.get("GET", "/search/issues", {"q": q, "page": 1})
        total = int((body or {}).get("total_count", 0)) if isinstance(body, dict) else 0
        requested = min(total, frame.target_n) if frame.target_n else total
        return CoverageEstimate(
            requested=requested,
            note=f"{total} PRs match the frame; targeting {requested or total}.",
        )

    # ------------------------------------------------------------------- run

    def run(self, frame: SamplingFrame, cursor: Cursor | None) -> Iterator[RunItem]:
        q = self._search_query(frame)
        # The cursor pins an exact position: the page to fetch and how many
        # items on that page were already consumed. Resuming re-fetches the
        # page but skips the consumed prefix, so no unit is mined twice (F2.1).
        page = int(cursor.value.get("page", 1)) if cursor else 1
        skip = int(cursor.value.get("itemIndex", 0)) if cursor else 0
        seen = int(cursor.value.get("seen", 0)) if cursor else 0
        # Actors we've already emitted a snapshot for (persisted across resumes
        # so an actor first seen before the interruption isn't re-snapshotted).
        snapshotted: set[str] = set(
            cursor.value.get("snapshotted", []) if cursor else []
        )
        target = frame.target_n or 0

        while True:
            body = self._fetch.get("GET", "/search/issues", {"q": q, "page": page})
            items = (body or {}).get("items", []) if isinstance(body, dict) else []
            if not items:
                break
            for idx, item in enumerate(items):
                if idx < skip:
                    continue  # already consumed before the interruption
                if target and seen >= target:
                    return
                yield from self._mine_pr(frame, item, snapshotted)
                seen += 1
                self.retrieved += 1
                # Checkpoint pins the NEXT item to process (idx + 1).
                if seen % CHECKPOINT_EVERY == 0:
                    yield self._checkpoint(page, idx + 1, seen, snapshotted)
            page += 1
            skip = 0  # only the resume page has a consumed prefix
        # Final checkpoint at the end of the last page; resuming from it is a
        # clean no-op (the next page is empty).
        yield self._checkpoint(page, 0, seen, snapshotted)

    def _checkpoint(
        self, page: int, item_index: int, seen: int, snapshotted: set[str]
    ) -> CursorCheckpoint:
        return CursorCheckpoint(
            cursor=Cursor(
                {
                    "page": page,
                    "itemIndex": item_index,
                    "seen": seen,
                    "snapshotted": sorted(snapshotted),
                }
            ),
            retrieved=self.retrieved,
        )

    # -------------------------------------------------------------- internals

    def _search_query(self, frame: SamplingFrame) -> str:
        window = f"created:{frame.window_start}..{frame.window_end}"
        return f"{frame.query} type:pr {window}".strip()

    def _mine_pr(
        self, frame: SamplingFrame, item: dict, snapshotted: set[str]
    ) -> Iterator[NormalizedEvent]:
        repo = str(item.get("repo", "repo"))
        number = int(item.get("number", 0))
        session_id = f"pr-{repo}-{number}"
        seq = _SeqCounter()

        author_login = str(item.get("user", "unknown"))
        verdict = classify(self._signal(item))
        self.fired_heuristics.update(verdict.fired)
        condition = self._condition_for(frame, verdict.is_agent)
        pid = pseudonym(self._salt, author_login, prefix="actor")
        ts = str(item.get("createdAt", ""))

        if not self._included(frame, item):
            self.dropped.drop("excluded-by-inclusion-rule")
            return

        # The PR itself.
        yield NormalizedEvent(
            session_id=session_id,
            seq=seq.next(),
            participant_id=pid,
            condition=condition,
            type="mined_pull_request",
            ts=ts,
            source=SOURCE,
            mono=float(seq.value),
            payload={
                "repo": pseudonym(self._salt, repo, prefix="repo"),
                "changedFiles": int(item.get("changedFiles", 0)),
                "additions": int(item.get("additions", 0)),
                "deletions": int(item.get("deletions", 0)),
                "commits": int(item.get("commitCount", 0)),
                "reviewComments": int(item.get("reviewComments", 0)),
                "authorIsAgent": verdict.is_agent,
                "firedHeuristics": verdict.fired,
            },
        )

        # Its commits.
        for c in item.get("commits", []):
            cverdict = classify(self._signal(c))
            self.fired_heuristics.update(cverdict.fired)
            yield NormalizedEvent(
                session_id=session_id,
                seq=seq.next(),
                participant_id=pseudonym(
                    self._salt, str(c.get("author", author_login)), prefix="actor"
                ),
                condition=self._condition_for(frame, cverdict.is_agent),
                type="mined_commit",
                ts=str(c.get("committedAt", ts)),
                source=SOURCE,
                mono=float(seq.value),
                payload={
                    "additions": int(c.get("additions", 0)),
                    "deletions": int(c.get("deletions", 0)),
                    "changedFiles": int(c.get("changedFiles", 0)),
                    "authorIsAgent": cverdict.is_agent,
                },
            )

        # Its reviews.
        for r in item.get("reviews", []):
            rverdict = classify(self._signal(r))
            self.fired_heuristics.update(rverdict.fired)
            yield NormalizedEvent(
                session_id=session_id,
                seq=seq.next(),
                participant_id=pseudonym(
                    self._salt, str(r.get("author", "reviewer")), prefix="actor"
                ),
                condition=self._condition_for(frame, rverdict.is_agent),
                type="mined_review",
                ts=str(r.get("submittedAt", ts)),
                source=SOURCE,
                mono=float(seq.value),
                payload={
                    "state": str(r.get("state", "")),
                    "authorIsAgent": rverdict.is_agent,
                },
            )

        # One actor snapshot per distinct actor across the dataset.
        if pid not in snapshotted:
            snapshotted.add(pid)
            yield NormalizedEvent(
                session_id=session_id,
                seq=seq.next(),
                participant_id=pid,
                condition=condition,
                type="mined_actor_snapshot",
                ts=ts,
                source=SOURCE,
                mono=float(seq.value),
                payload={
                    "isAgent": verdict.is_agent,
                    "firedHeuristics": verdict.fired,
                },
            )

    def _signal(self, obj: dict) -> ActorSignal:
        login = str(obj.get("user") or obj.get("author") or "")
        app_slug = str(obj.get("appSlug", ""))
        return ActorSignal(
            login=login,
            is_bot_flagged=bool(obj.get("isBot", False)),
            coauthor_logins=tuple(str(c).lower() for c in obj.get("coauthors", [])),
            signature_tokens=tokenize_slug(app_slug) if app_slug else (),
        )

    def _condition_for(self, frame: SamplingFrame, is_agent: bool) -> str:
        # A two-arm frame maps authorship to (agent arm, human arm). With a
        # single or absent arm, everything lands in the one declared arm.
        arms = frame.conditions
        if len(arms) >= 2:
            return arms[0] if is_agent else arms[1]
        if arms:
            return arms[0]
        return "agent-pr" if is_agent else "human-pr"

    def _included(self, frame: SamplingFrame, item: dict) -> bool:
        # Exclusions are simple substring flags on structured fields (e.g.
        # "draft", "fork"); the frame lists them, the adapter honors them.
        flags = {str(f).lower() for f in item.get("flags", [])}
        return not (flags & {e.lower() for e in frame.exclusions})


class _SeqCounter:
    """A per-session monotonic ordinal (the ``seq`` join key)."""

    def __init__(self) -> None:
        self.value = 0

    def next(self) -> int:
        self.value += 1
        return self.value
