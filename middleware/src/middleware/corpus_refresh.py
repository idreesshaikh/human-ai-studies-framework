"""
Scheduled evidence refresh: fetch new papers and store the unseen ones as
candidates.
"""

from __future__ import annotations

import json
import logging
import math
import threading
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from middleware import corpus_fetchers, corpus_scoring, paper_index
from middleware.corpus_importer import _upsert_corpus_paper
from middleware.corpus_sources import (
    SourceFormatError,
    is_known,
    merge_sources,
    parse_arxiv_atom,
    parse_s2_bulk,
    title_key,
)
from middleware.db import CORPUS_STUDY_ID, CorpusCandidate, CorpusRefreshRun, Paper

log = logging.getLogger(__name__)
PAGE = 100


def last_until(s: Session) -> str | None:
    """The end of the newest fully successful run, else None."""
    return s.scalar(
        select(CorpusRefreshRun.until)
        .where(CorpusRefreshRun.status == "ok")
        .order_by(CorpusRefreshRun.id.desc())
        .limit(1)
    )


def window(
    s: Session, *, today: date, default_days: int, since: str | None
) -> tuple[str, str]:
    """
    (since, until) as ISO dates; an explicit ``since`` wins, else resume with 1
    day overlap.
    """
    until = today.isoformat()
    if since:
        return since, until
    previous = last_until(s)
    start = (
        date.fromisoformat(previous) - timedelta(days=1)
        if previous
        else today - timedelta(days=default_days)
    )
    return start.isoformat(), until


def arxiv_query(terms: list[str], categories: list[str]) -> str:
    """
    ``(cat:cs.SE OR cat:cs.HC) AND (all:"x" OR all:"y")``; quotes inside terms
    are removed.
    """
    cats = " OR ".join(f"cat:{c}" for c in categories)
    quote = chr(34)
    words = " OR ".join(
        f'all:"{t.replace(quote, " ").strip()}"' for t in terms if t.strip()
    )
    if not cats or not words:
        raise ValueError("arXiv queries need at least one category and one term")
    return f"({cats}) AND ({words})"


def _collect_arxiv(fetch, spec, since, until, max_per_query) -> list[dict]:
    query = arxiv_query(spec["terms"], spec["categories"])
    out: list[dict] = []
    start = 0
    while len(out) < max_per_query:
        size = min(PAGE, max_per_query - len(out))
        page = parse_arxiv_atom(fetch(query, since, until, start, size))
        out.extend(page)
        if len(page) < size:
            break
        start += size
    return out


def _collect_s2(fetch, query, since, until, max_per_query) -> list[dict]:
    out: list[dict] = []
    token = None
    seen = set()
    while len(out) < max_per_query:
        payload = fetch(query, since, until, token, min(PAGE, max_per_query - len(out)))
        out.extend(parse_s2_bulk(payload))
        token = payload.get("token") if isinstance(payload, dict) else None
        if not token:
            break
        if token in seen:
            raise SourceFormatError("Semantic Scholar repeated a pagination token")
        seen.add(token)
    return out[:max_per_query]


def refresh(
    session_factory,
    *,
    config: dict,
    since: str,
    until: str,
    fetch_arxiv: Callable[[str, str, str, int, int], bytes],
    fetch_s2: Callable[[str, str, str, str | None, int], dict],
    score_fn: Callable[[dict], float | None],
    now: Callable[[], str],
    dry_run: bool = False,
) -> dict:
    """
    Fetch new papers from each configured source and store the unseen ones as
    candidates.
    """
    max_per_query = int(config.get("maxPerQuery", 100))
    with session_factory() as s:
        run = CorpusRefreshRun(
            started_at=now(), since=since, until=until, status="running"
        )
        if not dry_run:
            ensure_not_running(s, now_iso=run.started_at)
            s.add(run)
            try:
                s.commit()
            except IntegrityError as exc:
                s.rollback()
                raise RefreshInProgress("another refresh claimed the run lock") from exc
        known_refs = {
            r
            for (r,) in s.execute(
                select(Paper.paper_ref).where(Paper.study_id == CORPUS_STUDY_ID)
            )
        }
        known_refs |= {r for (r,) in s.execute(select(CorpusCandidate.ref))}
        known_titles = {
            title_key(t)
            for (t,) in s.execute(
                select(Paper.title).where(Paper.study_id == CORPUS_STUDY_ID)
            )
        } | {title_key(t) for (t,) in s.execute(select(CorpusCandidate.title))}

        fetched: list[dict] = []
        errors: list[dict] = []
        sources_ok = 0
        jobs = [
            (
                "arxiv",
                spec["terms"][0],
                lambda spec=spec: _collect_arxiv(
                    fetch_arxiv, spec, since, until, max_per_query
                ),
            )
            for spec in config.get("arxiv", [])
        ]
        jobs += [
            ("s2", q, lambda q=q: _collect_s2(fetch_s2, q, since, until, max_per_query))
            for q in config.get("semanticScholar", [])
        ]
        for source, label, job in jobs:
            try:
                fetched.extend(job())
                sources_ok += 1
            except Exception as exc:  # noqa: BLE001 - preserve other sources
                log.warning("refresh source %s (%s) failed: %s", source, label, exc)
                errors.append(
                    {"source": source, "query": label, "message": str(exc)[:300]}
                )

        merged = merge_sources(fetched)
        new, duplicates = [], 0
        for cand in merged:
            if is_known(cand, known_refs, known_titles):
                duplicates += 1
                continue
            known_refs.add(cand["ref"])
            known_titles.add(title_key(cand["title"]))
            new.append(cand)

        if not dry_run:
            for cand in new:
                s.add(
                    CorpusCandidate(
                        ref=cand["ref"],
                        arxiv_id=cand["arxivId"],
                        doi=cand["doi"],
                        s2_id=cand["s2Id"],
                        title=cand["title"],
                        abstract=cand["abstract"],
                        year=cand["year"],
                        published_at=cand["publishedAt"],
                        venue=cand["venue"],
                        authors=cand["authors"],
                        citation_count=cand["citationCount"],
                        source=cand["source"],
                        url=cand["url"],
                        score=score_fn(cand),
                        run_id=run.id,
                        first_seen_at=now(),
                    )
                )
            run.fetched, run.new_candidates, run.duplicates = (
                len(merged),
                len(new),
                duplicates,
            )
            run.errors = errors
            run.status = (
                "failed"
                if jobs and sources_ok == 0
                else ("partial" if errors else "ok")
            )
            run.finished_at = now()
            s.commit()
        return {
            "status": "dry-run" if dry_run else run.status,
            "since": since,
            "until": until,
            "fetched": len(merged),
            "newCandidates": len(new),
            "duplicates": duplicates,
            "errors": errors,
            "candidates": [c["ref"] for c in new],
        }


class RefreshInProgress(RuntimeError):
    """Another refresh started recently and has not finished."""


def ensure_not_running(
    s: Session, *, now_iso: str, stale_after_hours: float = 6.0
) -> None:
    """
    Refuse to start while a recent run is still marked running; stale ones are
    ignored.
    """
    cutoff = (
        (
            datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
            - timedelta(hours=stale_after_hours)
        )
        .isoformat()
        .replace("+00:00", "Z")
    )
    for expired in s.scalars(
        select(CorpusRefreshRun).where(
            CorpusRefreshRun.status == "running",
            CorpusRefreshRun.started_at <= cutoff,
        )
    ):
        expired.status = "failed"
        expired.finished_at = now_iso
        expired.errors = [
            *(expired.errors or []),
            {
                "source": "lock",
                "query": "",
                "message": "stale refresh lease expired",
            },
        ]
    s.flush()
    busy = s.scalar(
        select(CorpusRefreshRun.id)
        .where(
            CorpusRefreshRun.status == "running", CorpusRefreshRun.started_at > cutoff
        )
        .limit(1)
    )
    if busy is not None:
        raise RefreshInProgress(f"refresh run {busy} is still running")


def run_scheduler(
    stop: threading.Event,
    *,
    interval_s: float,
    run: Callable[[], object],
    first_delay_s: float = 60.0,
) -> None:
    """
    Call ``run`` every ``interval_s`` until ``stop`` is set; a failing run never
    ends the loop.
    """
    if stop.wait(first_delay_s):
        return
    while not stop.is_set():
        try:
            run()
        except Exception:
            log.exception("scheduled corpus refresh failed")
        if stop.wait(interval_s):
            return


def start_scheduler(
    *, interval_hours: float, run: Callable[[], object], first_delay_s: float = 60.0
):
    """Start the daemon thread; returns (thread, stop_event)."""
    if not math.isfinite(interval_hours) or interval_hours <= 0:
        raise ValueError("interval_hours must be positive")
    stop = threading.Event()
    thread = threading.Thread(
        target=run_scheduler,
        kwargs={
            "stop": stop,
            "interval_s": interval_hours * 3600.0,
            "run": run,
            "first_delay_s": first_delay_s,
        },
        name="phoenix-corpus-refresh",
        daemon=True,
    )
    thread.start()
    return thread, stop


DEFAULT_DAYS = 30
DEFAULT_QUERIES = (
    Path(__file__).resolve().parents[3] / "docs" / "papers" / "refresh-queries.json"
)


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_config(path: Path) -> dict:
    """
    The refresh queries, validated. Raises ValueError with a message naming the
    problem.
    """
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read refresh queries from {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("refresh queries must be a JSON object")
    arxiv, s2 = data.get("arxiv", []), data.get("semanticScholar", [])
    for spec in arxiv:
        terms, cats = (
            spec.get("terms") if isinstance(spec, dict) else None,
            spec.get("categories") if isinstance(spec, dict) else None,
        )
        if not (
            isinstance(terms, list)
            and terms
            and all(isinstance(t, str) and t.strip() for t in terms)
        ):
            raise ValueError("each arxiv entry needs a non-empty list of text 'terms'")
        if not (
            isinstance(cats, list)
            and cats
            and all(isinstance(c, str) and c.strip() for c in cats)
        ):
            raise ValueError("each arxiv entry needs a non-empty list of 'categories'")
    if not all(isinstance(q, str) and q.strip() for q in s2):
        raise ValueError("semanticScholar must be a list of non-empty query strings")
    if not arxiv and not s2:
        raise ValueError("refresh queries define no sources")
    max_per_query = data.get("maxPerQuery", 100)
    if not isinstance(max_per_query, int) or not 1 <= max_per_query <= 1000:
        raise ValueError("maxPerQuery must be an integer from 1 to 1000")
    return {"arxiv": arxiv, "semanticScholar": s2, "maxPerQuery": max_per_query}


def run_once(
    session_factory,
    *,
    config_path: Path | None = None,
    since: str | None = None,
    dry_run: bool = False,
    today: date | None = None,
    now: Callable[[], str] = utc_now,
    default_days: int = DEFAULT_DAYS,
) -> dict:
    """
    One full refresh: config, window, run lock, fetch, store. Shared by the CLI
    and scheduler.
    """
    config = load_config(config_path or DEFAULT_QUERIES)
    today = today or datetime.now(UTC).date()
    with session_factory() as s:
        if not dry_run:
            ensure_not_running(s, now_iso=now())
        start, until = window(s, today=today, default_days=default_days, since=since)
    return refresh(
        session_factory,
        config=config,
        since=start,
        until=until,
        # Looked up at call time so tests (and the CLI tests) can substitute them.
        fetch_arxiv=lambda *a: corpus_fetchers.fetch_arxiv(*a),
        fetch_s2=lambda *a: corpus_fetchers.fetch_s2(*a),
        score_fn=lambda cand: corpus_scoring.candidate_score(cand, today.year),
        now=now,
        dry_run=dry_run,
    )


def last_run_summary(s: Session, *, today: date) -> dict | None:
    """Newest finished run, for the status line ('last refreshed N days ago')."""
    run = s.scalar(
        select(CorpusRefreshRun)
        .where(CorpusRefreshRun.finished_at.is_not(None))
        .order_by(CorpusRefreshRun.id.desc())
        .limit(1)
    )
    if run is None:
        return None
    finished = datetime.fromisoformat(run.finished_at.replace("Z", "+00:00")).date()
    return {
        "finishedAt": run.finished_at,
        "ageDays": (today - finished).days,
        "status": run.status,
        "newCandidates": run.new_candidates,
        "errors": len(run.errors or []),
    }


def promote(s: Session, ref: str, *, decided_by: str, now: str, note: str = "") -> dict:
    """
    Accept a candidate: it becomes a searchable corpus paper (tier C), by
    explicit decision.
    """
    cand = s.scalar(select(CorpusCandidate).where(CorpusCandidate.ref == ref))
    if cand is None:
        raise KeyError(ref)
    if cand.status == "rejected":
        raise ValueError(
            f"{ref} was rejected; reject decisions are not silently reversed"
        )
    if cand.status == "accepted":
        return {"ref": ref, "status": "accepted", "alreadyAccepted": True}
    _upsert_corpus_paper(
        s,
        {
            "paper_ref": cand.ref,
            "title": cand.title,
            "authors": cand.authors or [],
            "year": cand.year,
            # papers.* text columns are NOT NULL; a missing identifier is the empty
            # string.
            "venue": cand.venue or "",
            "abstract": cand.abstract or "",
            "doi": cand.doi or "",
            "arxiv_id": cand.arxiv_id or "",
            "s2_id": cand.s2_id or "",
            "url": cand.url or "",
            "citation_count": cand.citation_count,
            "score": cand.score,
            "tier": "C",
            "source": f"refresh:{cand.run_id}:{cand.source}",
            "added_via": "refresh",
        },
    )
    body = "\n\n".join(part for part in (cand.venue, cand.abstract) if part)
    paper_index.index_paper(s, cand.ref, cand.title, body)
    cand.status, cand.decided_at, cand.decided_by, cand.note = (
        "accepted",
        now,
        decided_by,
        note,
    )
    s.flush()
    return {"ref": ref, "status": "accepted", "alreadyAccepted": False}


def reject(s: Session, ref: str, *, decided_by: str, now: str, note: str = "") -> dict:
    cand = s.scalar(select(CorpusCandidate).where(CorpusCandidate.ref == ref))
    if cand is None:
        raise KeyError(ref)
    if cand.status == "accepted":
        raise ValueError(
            f"{ref} was accepted into the corpus; remove it deliberately, not here"
        )
    cand.status, cand.decided_at, cand.decided_by, cand.note = (
        "rejected",
        now,
        decided_by,
        note,
    )
    s.flush()
    return {"ref": ref, "status": "rejected"}


CANDIDATE_STATUSES = ("new", "accepted", "rejected")


def candidate_counts(s: Session) -> dict[str, int]:
    """How many candidates are waiting, accepted and rejected."""
    counts = dict.fromkeys(CANDIDATE_STATUSES, 0)
    for status, n in s.execute(
        select(CorpusCandidate.status, func.count()).group_by(CorpusCandidate.status)
    ):
        if status in counts:
            counts[status] = n
    return counts


def list_candidates(s: Session, *, status: str = "new", limit: int = 50) -> list[dict]:
    """
    Candidates by status, highest score first; abstracts are shortened for
    listing.
    """
    if status not in CANDIDATE_STATUSES:
        raise ValueError(f"status must be one of {CANDIDATE_STATUSES}")
    rows = s.scalars(
        select(CorpusCandidate)
        .where(CorpusCandidate.status == status)
        .order_by(CorpusCandidate.score.desc().nulls_last(), CorpusCandidate.id)
        .limit(max(1, min(limit, 200)))
    )
    return [
        {
            "ref": c.ref,
            "title": c.title,
            "abstract": (c.abstract or "")[:500],
            "year": c.year,
            "venue": c.venue,
            "source": c.source,
            "url": c.url,
            "score": c.score,
            "firstSeenAt": c.first_seen_at,
        }
        for c in rows
    ]


def format_summary(result: dict) -> str:
    """The text the CLI prints after a refresh."""
    lines = [
        f"corpus refresh {result['status']}: {result['since']} to {result['until']}",
        f"  {result['fetched']} papers fetched, "
        f"{result['newCandidates']} new candidates, "
        f"{result['duplicates']} already known",
    ]
    for err in result["errors"]:
        lines.append(f"  ! {err['source']} ({err['query']}): {err['message']}")
    return "\n".join(lines)
