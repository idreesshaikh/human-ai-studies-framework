"""
Live Semantic Scholar search for the design chat, used when the local corpus has
little to offer (``matching.match_papers(..., live=True)``).

* The caller waits at most :data:`LIVE_BUDGET_S` end to end. A slow answer is
  abandoned, not awaited; when it does arrive it still warms the corpus for the
  next message.
* After a 429, a 5xx, a timeout or a dropped connection, live search is off for a
  cool-down and returns ``[]`` at once, so an outage costs one wait, not one per
  message.
* What it finds is stored in the corpus (tier C, ``added_via="live-search"``) by a
  background thread in its own short transaction. The request session stays
  read-only: the conversation route deliberately opens no write transaction
  before the model call, and rolls the session back before saving the turn.
  Curation triages these rows like any other automatic addition.
* Papers a person hid or rejected are never brought back.
"""

from __future__ import annotations

import contextlib
import logging
import os
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from middleware import corpus_scoring, paper_index, semantic_scholar
from middleware.corpus_sources import canonical_ref, parse_s2_papers
from middleware.db import CORPUS_STUDY_ID, CorpusCandidate, Paper

log = logging.getLogger(__name__)

LIVE_BUDGET_S = 2.5
# A late answer may still land and warm the corpus for the next message.
LATE_GRACE_S = 5.0
FETCH_LIMIT = 20
CACHE_DAYS = 7.0
COOLDOWN_RATE_LIMITED_S = 120.0
COOLDOWN_FAILED_S = 60.0
ADDED_VIA = "live-search"
_RECENT_MAX = 256

_clock = time.monotonic
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="s2-live")
_lock = threading.Lock()
_cooldown_until = 0.0
_last_error = ""
_recent: OrderedDict[str, dict] = OrderedDict()
_pending: set[Future] = set()


def enabled() -> bool:
    """Whether live search may run. ``MIDDLEWARE_LIVE_SEARCH=0`` turns it off,
    for a server that must not send query keywords to Semantic Scholar."""
    return os.environ.get("MIDDLEWARE_LIVE_SEARCH", "1").strip().lower() not in {
        "0",
        "false",
        "off",
        "no",
    }


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- circuit breaker


def cooling_down() -> bool:
    with _lock:
        return _clock() < _cooldown_until


def _trip(exc: Exception) -> None:
    global _cooldown_until, _last_error
    status = getattr(exc, "status", None)
    after = getattr(exc, "retry_after", None)
    if status == 429:
        wait = max(after or 0.0, COOLDOWN_RATE_LIMITED_S)
    elif status is not None and status < 500:
        return  # a 4xx other than 429 says nothing about S2's health
    else:
        wait = COOLDOWN_FAILED_S
    # The error's own message carries the request URL, and so one study's search
    # keywords; /corpus/status is shown to every user, so keep only the cause.
    cause = f"HTTP {status}" if status is not None else "no usable answer"
    with _lock:
        _cooldown_until = max(_cooldown_until, _clock() + wait)
        _last_error = cause
    log.warning("live S2 search paused for %.0fs: %s", wait, cause)


def reset() -> None:
    """Forget the cool-down and recent records (tests and operators)."""
    global _cooldown_until, _last_error
    with _lock:
        _cooldown_until = 0.0
        _last_error = ""
        _recent.clear()


def status() -> dict:
    """For ``/corpus/status``: whether live search is paused, and why."""
    with _lock:
        remaining = max(0.0, _cooldown_until - _clock())
        return {
            "paused": remaining > 0,
            "resumesInS": round(remaining),
            "lastError": _last_error if remaining > 0 else "",
        }


# --- recent records (visible before the background write lands)


def _remember(records: list[dict]) -> None:
    with _lock:
        for rec in records:
            _recent[rec["ref"]] = rec
            _recent.move_to_end(rec["ref"])
        while len(_recent) > _RECENT_MAX:
            _recent.popitem(last=False)


def recent(ref: str) -> dict | None:
    """A record live search returned recently, by ref (None if unknown)."""
    with _lock:
        return _recent.get(ref)


def drain(timeout: float = 10.0) -> None:
    """Wait for background stores to finish (tests, shutdown)."""
    with _lock:
        pending = list(_pending)
    for fut in pending:
        with contextlib.suppress(Exception):  # the worker already logged it
            fut.result(timeout=timeout)


# --- storage


def _resolve(s: Session, records: list[dict]) -> list[dict]:
    """
    Map records onto corpus rows that already hold the same paper (by ref, by the
    ref its identifiers imply, or by title), and drop papers a person hid or
    turned down.
    """
    if not records:
        return []
    refs = {r["ref"] for r in records}
    titles = {r["title"].strip().lower() for r in records}
    rows = s.execute(
        select(
            Paper.paper_ref, Paper.title, Paper.arxiv_id, Paper.doi, Paper.curation
        ).where(
            Paper.study_id == CORPUS_STUDY_ID,
            or_(
                Paper.paper_ref.in_(refs),
                Paper.arxiv_id.in_([r["arxivId"] for r in records if r["arxivId"]]),
                Paper.doi.in_([r["doi"] for r in records if r["doi"]]),
                func.lower(Paper.title).in_(titles),
            ),
        )
    ).all()
    by_key: dict[str, tuple[str, str]] = {}
    for ref, title, arxiv_id, doi, curation in rows:
        for key in (
            ref,
            canonical_ref(arxiv_id=arxiv_id or None, doi=doi or None, s2_id=None),
            "title:" + (title or "").strip().lower(),
        ):
            if key:
                by_key[key] = (ref, curation or "")
    rejected = set(
        s.scalars(
            select(CorpusCandidate.ref).where(
                CorpusCandidate.ref.in_(refs), CorpusCandidate.status == "rejected"
            )
        )
    )
    out, seen = [], set()
    for rec in records:
        if rec["ref"] in rejected:
            continue
        match = by_key.get(rec["ref"]) or by_key.get(
            "title:" + rec["title"].strip().lower()
        )
        if match is not None:
            ref, curation = match
            if curation == "hidden":
                continue
            rec = {**rec, "ref": ref, "inCorpus": True}
        if rec["ref"] not in seen:
            seen.add(rec["ref"])
            out.append(rec)
    return out


def _insert_ignore(s: Session, values: dict) -> bool:
    engine = s.get_bind()
    if engine.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    stmt = (
        insert(Paper)
        .values([values])
        .on_conflict_do_nothing(index_elements=["study_id", "paper_ref"])
    )
    return bool(s.execute(stmt).rowcount)


def store(s: Session, records: list[dict], *, now: str, this_year: int) -> int:
    """Add records the corpus does not hold yet as searchable tier-C rows."""
    added = 0
    for rec in records:
        if rec.get("inCorpus"):
            continue
        values = {
            "study_id": CORPUS_STUDY_ID,
            "paper_ref": rec["ref"],
            "title": rec["title"],
            "authors": rec.get("authors") or [],
            "year": rec.get("year"),
            "venue": rec.get("venue") or "",
            "abstract": rec.get("abstract") or "",
            "doi": rec.get("doi") or "",
            "arxiv_id": rec.get("arxivId") or "",
            "s2_id": rec.get("s2Id") or "",
            "url": rec.get("url") or "",
            "item_type": "paper",
            "citation_count": rec.get("citationCount"),
            "score": corpus_scoring.candidate_score(rec, this_year),
            "tier": "C",
            "source": f"s2-live:{now[:10]}",
            "added_via": ADDED_VIA,
            "added_at": now,
        }
        if _insert_ignore(s, values):
            body = "\n\n".join(p for p in (rec.get("venue"), rec.get("abstract")) if p)
            paper_index.index_paper(s, rec["ref"], rec["title"], body)
            added += 1
    return added


def added_count(s: Session) -> int:
    """Corpus rows live search has added so far."""
    return (
        s.scalar(
            select(func.count())
            .select_from(Paper)
            .where(Paper.study_id == CORPUS_STUDY_ID, Paper.added_via == ADDED_VIA)
        )
        or 0
    )


# --- the search


def search(
    bind,
    keywords: str,
    *,
    budget_s: float = LIVE_BUDGET_S,
    limit: int = FETCH_LIMIT,
    keep: Callable[[dict], bool] | None = None,
    now: Callable[[], str] = utc_now,
) -> list[dict]:
    """
    Papers S2 ranks relevant to ``keywords`` that pass ``keep`` (candidate-record
    shape from :func:`corpus_sources.parse_s2_papers`, plus ``inCorpus``), or
    ``[]`` when live search is cooling down, slow, rate-limited or failing. Only
    kept records are stored. Never raises.
    """
    if not keywords.strip() or cooling_down() or not enabled():
        return []
    started = _clock()
    answer: Future = Future()

    def work() -> None:
        stamp = now()
        if not enabled():
            # Switched off while this search waited in the queue.
            answer.set_result([])
            return
        try:
            remaining = started + budget_s + LATE_GRACE_S - _clock()
            with Session(bind=bind) as ws, semantic_scholar.budget(remaining):
                papers = semantic_scholar.search(
                    keywords,
                    limit=limit,
                    fetch=lambda url: semantic_scholar.cached_get(
                        ws, url, now=stamp, max_age_days=CACHE_DAYS
                    ),
                )
                # Read without flushing the new cache row: the write transaction
                # starts at the store below and lasts only as long as it does.
                with ws.no_autoflush:
                    records = _resolve(ws, parse_s2_papers(papers, source="s2-live"))
                records = [r for r in records if keep is None or keep(r)]
                _remember(records)
                answer.set_result(records)
                store(ws, records, now=stamp, this_year=int(stamp[:4]))
                ws.commit()
        except semantic_scholar.SemanticScholarError as exc:
            _trip(exc)
            if not answer.done():
                answer.set_exception(exc)
        except Exception as exc:  # live search must never break the chat
            log.exception("live S2 search failed")
            if not answer.done():
                answer.set_exception(exc)

    fut = _executor.submit(work)
    with _lock:
        _pending.add(fut)
    fut.add_done_callback(lambda f: _discard(f))
    try:
        return answer.result(timeout=max(0.0, started + budget_s - _clock()))
    except FutureTimeout:
        log.info("live S2 search exceeded %.1fs; using local results", budget_s)
        return []
    except Exception:  # noqa: BLE001 - the worker logged it
        return []


def _discard(fut: Future) -> None:
    with _lock:
        _pending.discard(fut)
