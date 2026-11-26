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

from middleware import corpus_fetchers, corpus_scoring, paper_index, semantic_scholar
from middleware.corpus_importer import _upsert_corpus_paper
from middleware.corpus_sources import (
    SourceFormatError,
    canonical_ref,
    is_known,
    merge_sources,
    parse_arxiv_atom,
    parse_s2_bulk,
    parse_s2_papers,
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
    """
    Bulk-search pages until ``max_per_query`` papers. The endpoint has no page-size
    parameter (each page holds up to 1,000, newest first), so the cut is ours.
    """
    out: list[dict] = []
    token = None
    seen = set()
    while len(out) < max_per_query:
        payload = fetch(query, since, until, token)
        out.extend(parse_s2_bulk(payload))
        token = payload.get("token") if isinstance(payload, dict) else None
        if not token:
            break
        if token in seen:
            raise SourceFormatError("Semantic Scholar repeated a pagination token")
        seen.add(token)
    return out[:max_per_query]


def _collect_citations(fetch, ids, since, until, per_paper) -> list[dict]:
    """
    Forward snowballing: papers published in the window that cite an example. A
    failing example is logged and skipped; the job fails only if every one does.
    """
    out: list[dict] = []
    failures = 0
    for paper_id in ids:
        try:
            out.extend(
                parse_s2_papers(
                    fetch(paper_id, since, until, per_paper), source="s2-cites"
                )
            )
        except Exception as exc:  # noqa: BLE001 - one example must not stop the rest
            failures += 1
            log.warning("citations of %s unavailable: %s", paper_id, exc)
    if ids and failures == len(ids):
        raise SourceFormatError(f"citations unavailable for all {len(ids)} examples")
    return out


def known_keys(s: Session) -> tuple[set[str], set[str]]:
    """
    Refs and normalised titles already in the corpus or the candidate pool. A corpus
    row is known by its ref and by the ``arxiv:``/``doi:`` refs its identifiers imply,
    so a seed stored as ``corpus:<slug>`` is not fetched again as ``arxiv:<id>``.
    """
    refs: set[str] = set()
    titles: set[str] = set()
    for ref, title, arxiv_id, doi in s.execute(
        select(Paper.paper_ref, Paper.title, Paper.arxiv_id, Paper.doi).where(
            Paper.study_id == CORPUS_STUDY_ID
        )
    ):
        refs.add(ref)
        alias = canonical_ref(arxiv_id=arxiv_id or None, doi=doi or None, s2_id=None)
        if alias:
            refs.add(alias)
        titles.add(title_key(title or ""))
    for ref, title in s.execute(select(CorpusCandidate.ref, CorpusCandidate.title)):
        refs.add(ref)
        titles.add(title_key(title or ""))
    titles.discard("")
    return refs, titles


def refresh(
    session_factory,
    *,
    config: dict,
    since: str,
    until: str,
    fetch_arxiv: Callable[[str, str, str, int, int], bytes],
    fetch_s2: Callable[[str, str, str, str | None], dict],
    score_fn: Callable[[dict], float | None],
    now: Callable[[], str],
    dry_run: bool = False,
    fetch_recs: Callable[[list[str], list[str], int], list[dict]] | None = None,
    fetch_citations: Callable[[str, str, str, int], list[dict]] | None = None,
) -> dict:
    """
    Fetch new papers from each configured source and store the unseen ones as
    candidates. Besides the keyword queries, ``recommendations`` asks Semantic
    Scholar for papers like the human-chosen examples and unlike the rejected
    ones, and ``citations`` collects papers published in the window that cite
    the examples, so discovery follows the field even when its vocabulary moves.
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
        known_refs, known_titles = known_keys(s)

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
        rec_limit = int(config.get("recommendations", 0) or 0)
        cite_examples = int(config.get("citations", 0) or 0)
        positive, negative = (
            example_s2_ids(s)
            if (rec_limit and fetch_recs) or (cite_examples and fetch_citations)
            else ([], [])
        )
        if cite_examples and fetch_citations is not None and positive:
            chosen = positive[:cite_examples]
            jobs.append(
                (
                    "s2-cites",
                    f"new citations of {len(chosen)} examples",
                    lambda: _collect_citations(
                        fetch_citations, chosen, since, until, max_per_query
                    ),
                )
            )
        if rec_limit and fetch_recs is not None and positive:
            jobs.append(
                (
                    "s2-recs",
                    f"{len(positive)} examples, {len(negative)} counter-examples",
                    lambda: parse_s2_papers(
                        fetch_recs(positive, negative, rec_limit), source="s2-recs"
                    ),
                )
            )
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


DEFAULT_INTERVAL_HOURS = 24.0
# A run that failed outright (every source down) is retried sooner than the
# regular cadence, but not so soon that an outage turns into a request loop.
FAILED_RETRY_HOURS = 2.0


def seconds_until_due(
    session_factory, *, interval_s: float, now: Callable[[], datetime] | None = None
) -> float:
    """
    Seconds until the next refresh is due, from the newest finished run in the
    database: a restart resumes the cadence instead of refreshing on every boot.
    """
    current = (now or (lambda: datetime.now(UTC)))()
    with session_factory() as s:
        return due_in_session(s, interval_s=interval_s, now=current)


def due_in_session(s: Session, *, interval_s: float, now: datetime) -> float:
    run = s.scalar(
        select(CorpusRefreshRun)
        .where(CorpusRefreshRun.finished_at.is_not(None))
        .order_by(CorpusRefreshRun.id.desc())
        .limit(1)
    )
    current = now if now.tzinfo else now.replace(tzinfo=UTC)
    if run is None:
        return 0.0
    try:
        finished = datetime.fromisoformat(run.finished_at.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    if finished.tzinfo is None:
        finished = finished.replace(tzinfo=UTC)
    wait = interval_s
    if run.status == "failed":
        wait = min(interval_s, FAILED_RETRY_HOURS * 3600.0)
    return max(0.0, (finished - current).total_seconds() + wait)


def run_scheduler(
    stop: threading.Event,
    *,
    interval_s: float,
    run: Callable[[], object],
    first_delay_s: float = 60.0,
    due_in: Callable[[], float] | None = None,
) -> None:
    """
    Call ``run`` every ``interval_s`` until ``stop`` is set; a failing run never
    ends the loop. With ``due_in`` (seconds until the next run is due, read from
    the run history) a run happens only once it is due, so restarts keep the
    cadence.
    """
    retry_s = min(interval_s, FAILED_RETRY_HOURS * 3600.0)
    delay = first_delay_s
    while not stop.wait(delay):
        if due_in is not None:
            try:
                wait = due_in()
            except Exception:
                log.exception("could not read the refresh history; running now")
                wait = 0.0
            if wait > 0:
                delay = min(wait, interval_s)
                log.info("next corpus refresh in %.1f h", delay / 3600.0)
                continue
        try:
            run()
        except Exception:
            log.exception("scheduled corpus refresh failed")
        # A recorded failure can be due before the regular interval. Check the
        # run history by then even if the process stays up between attempts.
        delay = retry_s if due_in is not None else interval_s


def start_scheduler(
    *,
    interval_hours: float,
    run: Callable[[], object],
    first_delay_s: float = 60.0,
    due_in: Callable[[], float] | None = None,
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
            "due_in": due_in,
        },
        name="phoenix-corpus-refresh",
        daemon=True,
    )
    thread.start()
    return thread, stop


def schedule_status(s: Session, *, now: datetime, hours: float | None) -> dict:
    """Whether this server refreshes on a schedule, how often, and when next."""
    if hours is None:
        return {"enabled": False, "intervalHours": None, "nextRunInHours": None}
    due = due_in_session(s, interval_s=hours * 3600.0, now=now)
    return {
        "enabled": True,
        "intervalHours": hours,
        "nextRunInHours": round(due / 3600.0, 2),
    }


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
    recommendations = data.get("recommendations", 0)
    if not isinstance(recommendations, int) or not 0 <= recommendations <= 500:
        raise ValueError("recommendations must be an integer from 0 (off) to 500")
    citations = data.get("citations", 0)
    if not isinstance(citations, int) or not 0 <= citations <= 100:
        raise ValueError("citations must be an integer from 0 (off) to 100")
    return {
        "arxiv": arxiv,
        "semanticScholar": s2,
        "maxPerQuery": max_per_query,
        "recommendations": recommendations,
        "citations": citations,
        "curation": curation_config(data.get("curation", {})),
    }


CURATION_DEFAULTS = {
    # Re-check a corpus row's Semantic Scholar metadata after this many days.
    "staleDays": 90,
    # Relevance = mean similarity to this many nearest example papers.
    "neighbours": 3,
    # Keep cutoff: this percentile of the examples' own leave-one-out relevance.
    "keepPercentile": 10,
    # Hide cutoff: this far below the keep cutoff.
    "hideMargin": 0.05,
    # Fixed cutoffs, overriding the calibration when both are set.
    "keepAt": None,
    "hideBelow": None,
}


def curation_config(raw: object) -> dict:
    """The ``curation`` section with defaults filled in; ValueError names a problem."""
    if not isinstance(raw, dict):
        raise ValueError("curation must be a JSON object")
    unknown = set(raw) - set(CURATION_DEFAULTS)
    if unknown:
        raise ValueError(f"curation has unknown keys: {sorted(unknown)}")
    cfg = {**CURATION_DEFAULTS, **raw}
    for key, low, high in (("staleDays", 1, 3650), ("neighbours", 1, 20)):
        if not isinstance(cfg[key], int) or not low <= cfg[key] <= high:
            raise ValueError(f"curation.{key} must be an integer from {low} to {high}")
    for key, low, high in (("keepPercentile", 0, 100), ("hideMargin", 0, 1)):
        if not isinstance(cfg[key], int | float) or not low <= cfg[key] <= high:
            raise ValueError(f"curation.{key} must be a number from {low} to {high}")
    fixed = [cfg["keepAt"], cfg["hideBelow"]]
    if any(v is not None for v in fixed):
        if not all(isinstance(v, int | float) and -1 <= v <= 1 for v in fixed):
            raise ValueError("curation.keepAt and hideBelow must both be set, -1..1")
        if cfg["hideBelow"] > cfg["keepAt"]:
            raise ValueError("curation.hideBelow must not exceed keepAt")
    return cfg


HUMAN = "human:"


def human_examples(s: Session) -> tuple[list[str], list[str]]:
    """
    Refs a person chose (the README seeds and anything accepted or kept by
    hand) and refs a person turned down. Automatic decisions are never
    examples, so curation cannot drift by learning from itself.
    """
    corpus = Paper.study_id == CORPUS_STUDY_ID
    positive = list(
        s.scalars(
            select(Paper.paper_ref)
            .where(corpus)
            .where(
                (Paper.tier == "A")
                | ((Paper.curation == "keep") & Paper.curation_by.startswith(HUMAN))
            )
            .order_by(Paper.year.desc().nulls_last(), Paper.paper_ref)
        )
    )
    negative = list(
        s.scalars(
            select(Paper.paper_ref).where(
                corpus,
                Paper.curation == "hidden",
                Paper.curation_by.startswith(HUMAN),
            )
        )
    )
    negative += list(
        s.scalars(
            select(CorpusCandidate.ref).where(
                CorpusCandidate.status == "rejected",
                ~func.coalesce(CorpusCandidate.decided_by, "").startswith("auto:"),
            )
        )
    )
    return positive, negative


def example_s2_ids(s: Session, *, cap: int = 100) -> tuple[list[str], list[str]]:
    """
    Ids Semantic Scholar resolves the human examples by, newest first, capped: the
    stored S2 id, else the ``ARXIV:``/``DOI:`` form, so a corpus that no curation run
    has re-checked yet still has examples to recommend and snowball from.
    """
    positive, negative = human_examples(s)

    def ids(refs: list[str]) -> list[str]:
        if not refs:
            return []
        found: dict[str, str] = {}
        for ref, s2_id, doi, arxiv_id in s.execute(
            select(Paper.paper_ref, Paper.s2_id, Paper.doi, Paper.arxiv_id).where(
                Paper.study_id == CORPUS_STUDY_ID, Paper.paper_ref.in_(refs)
            )
        ):
            found[ref] = semantic_scholar.lookup_id(s2_id, doi, arxiv_id)
        for ref, s2_id, doi, arxiv_id in s.execute(
            select(
                CorpusCandidate.ref,
                CorpusCandidate.s2_id,
                CorpusCandidate.doi,
                CorpusCandidate.arxiv_id,
            ).where(CorpusCandidate.ref.in_(refs))
        ):
            if not found.get(ref):
                found[ref] = semantic_scholar.lookup_id(s2_id, doi, arxiv_id)
        for ref in refs:
            if not found.get(ref) and ref.startswith(("arxiv:", "doi:", "s2:")):
                found[ref] = semantic_scholar.s2_id_for_ref(ref)
        return list(dict.fromkeys(found[r] for r in refs if found.get(r)))[:cap]

    return ids(positive), ids(negative)


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
        fetch_recs=lambda pos, neg, n: semantic_scholar.fetch_recommendations(
            pos, neg, fields=corpus_fetchers.S2_FIELDS, limit=n
        ),
        fetch_citations=lambda paper_id, since, until, n: (
            semantic_scholar.fetch_citations(
                paper_id, since=since, until=until, limit=n
            )
        ),
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
    outcome = dict.fromkeys(CANDIDATE_STATUSES, 0)
    for status, n in s.execute(
        select(CorpusCandidate.status, func.count())
        .where(CorpusCandidate.run_id == run.id)
        .group_by(CorpusCandidate.status)
    ):
        outcome[status] = n
    added = [
        {"ref": ref, "title": title, "status": status}
        for ref, title, status in s.execute(
            select(CorpusCandidate.ref, CorpusCandidate.title, CorpusCandidate.status)
            .where(CorpusCandidate.run_id == run.id)
            .order_by(
                CorpusCandidate.relevance.desc().nulls_last(),
                CorpusCandidate.score.desc().nulls_last(),
                CorpusCandidate.id,
            )
            .limit(10)
        )
    ]
    return {
        "startedAt": run.started_at,
        "finishedAt": run.finished_at,
        "ageDays": (today - finished).days,
        "status": run.status,
        "since": run.since,
        "until": run.until,
        "fetched": run.fetched,
        "duplicates": run.duplicates,
        "newCandidates": run.new_candidates,
        # What became of this run's candidates since: admitted to the corpus,
        # waiting for review, dismissed or turned down.
        "admitted": outcome["accepted"],
        "waiting": outcome["new"],
        "dismissed": outcome["dismissed"] + outcome["rejected"],
        "added": added,
        "errors": len(run.errors or []),
        "errorSources": sorted({e.get("source", "") for e in run.errors or []}),
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
    row = s.scalar(
        select(Paper).where(
            Paper.study_id == CORPUS_STUDY_ID, Paper.paper_ref == cand.ref
        )
    )
    automatic = decided_by.startswith("auto:")
    row.curation = "keep"
    row.curation_by = "auto" if automatic else f"{HUMAN}{decided_by}"
    row.curation_reason = note or ("accepted by hand" if not automatic else "")
    row.relevance = cand.relevance
    if automatic:
        row.added_via = "refresh-auto"
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


# "dismissed" is an automatic, reversible rejection (off-topic or weak); a
# person can still accept or reject a dismissed candidate.
CANDIDATE_STATUSES = ("new", "accepted", "rejected", "dismissed")


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
        .order_by(
            CorpusCandidate.relevance.desc().nulls_last(),
            CorpusCandidate.score.desc().nulls_last(),
            CorpusCandidate.id,
        )
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
            "relevance": c.relevance,
            "reason": c.triage_reason or "",
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
