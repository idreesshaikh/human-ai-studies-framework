"""
The scheduled refresh: fetch new candidates, then screen them.

Screening judges only the candidates a refresh found, never existing corpus rows
(changing what is already searchable stays an explicit ``corpus-curate`` run).
Each candidate's topical relevance to the human-chosen examples is measured with
cutoffs calibrated on those examples (:func:`corpus_curate.judge`), then

``keep``    admits it to the corpus (tier C, decided ``auto:curate``),
``hidden``  dismisses it (automatic and reversible),
``review``  leaves it waiting for a person.

Vectors come from SPECTER2 first: Semantic Scholar's batch endpoint returns them
for candidates it has embedded, judged against the example embeddings a curation
run stored. The newest preprints often have no SPECTER2 vector yet; those are
embedded with ``mistral-embed`` together with the examples, and judged against
cutoffs calibrated in that space. A candidate is always judged in one space.

``mistral-embed`` has its own request quota, separate from chat completions
(2026-11-23 response headers: ``x-ratelimit-limit-req-minute: 60`` for
mistral-embed against 2 for the chat models), so screening never competes with
the design chat. The client reads the headers on every response and leaves at
least half of each minute's requests unused.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from middleware import corpus_curate, corpus_refresh, semantic_scholar
from middleware.db import CORPUS_STUDY_ID, CorpusCandidate, Paper

log = logging.getLogger(__name__)

MISTRAL_HOST = "api.mistral.ai"
EMBED_URL = "https://api.mistral.ai/v1/embeddings"
EMBED_MODEL = "mistral-embed"
EMBED_BATCH = 16
EMBED_TEXT_CHARS = 1500
EMBED_RESERVE = 0.5  # leave this share of each minute's requests unused
SCREEN_LIMIT = 500

_urlopen = urllib.request.urlopen
_sleep = time.sleep

Embedder = Callable[[list[str]], list[list[float]]]


class EmbedError(RuntimeError):
    """mistral-embed could not embed a batch."""


# --- mistral-embed


def _quota_wait(headers, *, reserve: float = EMBED_RESERVE) -> float:
    """Seconds to pause so at least ``reserve`` of the minute's quota stays free."""
    try:
        limit = int(headers.get("x-ratelimit-limit-req-minute", ""))
        remaining = int(headers.get("x-ratelimit-remaining-req-minute", ""))
    except (TypeError, ValueError):
        return 0.0
    return 60.0 if remaining <= math.floor(limit * reserve) else 0.0


def embed_texts(
    texts: list[str],
    *,
    api_key: str,
    observed: dict | None = None,
    retries: int = 2,
) -> list[list[float]]:
    """``mistral-embed`` vectors for ``texts``, in order, in paced batches."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH):
        batch = [
            t[:EMBED_TEXT_CHARS] or " " for t in texts[start : start + EMBED_BATCH]
        ]
        body = json.dumps({"model": EMBED_MODEL, "input": batch}).encode()
        for attempt in range(retries + 1):
            req = urllib.request.Request(
                EMBED_URL,
                data=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with _urlopen(req, timeout=30) as res:
                    headers, payload = res.headers, json.loads(res.read())
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt < retries:
                    wait = semantic_scholar.retry_after_seconds(exc.headers)
                    _sleep(min(wait if wait is not None else 30.0, 60.0))
                    continue
                raise EmbedError(f"mistral-embed -> HTTP {exc.code}") from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raise EmbedError(f"mistral-embed failed: {exc}") from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or len(data) != len(batch):
            raise EmbedError("mistral-embed returned an unexpected shape")
        vectors.extend(item.get("embedding") or [] for item in data)
        if observed is not None:
            observed.update(
                limitPerMinute=headers.get("x-ratelimit-limit-req-minute"),
                remaining=headers.get("x-ratelimit-remaining-req-minute"),
            )
        pause = _quota_wait(headers)
        if pause and start + EMBED_BATCH < len(texts):
            log.info("mistral-embed quota half spent; pausing %.0fs", pause)
            _sleep(pause)
    return vectors


def mistral_embedder(observed: dict | None = None) -> Embedder | None:
    """
    An embedder over Mistral's API when the configured model route is Mistral's
    (``LLM_API_KEY`` with the default or a Mistral ``LLM_BASE_URL``), else None.
    """
    key = os.environ.get("LLM_API_KEY", "").strip()
    base = os.environ.get("LLM_BASE_URL", "").strip()
    if not key or (base and urlparse(base).hostname != MISTRAL_HOST):
        return None
    return lambda texts: embed_texts(texts, api_key=key, observed=observed)


# --- screening


def _text(title: str | None, abstract: str | None) -> str:
    return "\n\n".join(
        p for p in ((title or "").strip(), (abstract or "").strip()) if p
    )


def _example_texts(s: Session, refs: list[str]) -> dict[str, str]:
    """Title and abstract (or curator note) of the example papers."""
    out = {
        ref: _text(title, abstract or note)
        for ref, title, abstract, note in s.execute(
            select(
                Paper.paper_ref, Paper.title, Paper.abstract, Paper.curator_note
            ).where(Paper.study_id == CORPUS_STUDY_ID, Paper.paper_ref.in_(refs))
        )
    }
    for ref, title, abstract in s.execute(
        select(
            CorpusCandidate.ref, CorpusCandidate.title, CorpusCandidate.abstract
        ).where(CorpusCandidate.ref.in_(refs))
    ):
        out.setdefault(ref, _text(title, abstract))
    return {ref: text for ref, text in out.items() if text}


def _unscreened(s: Session, limit: int) -> list[CorpusCandidate]:
    return list(
        s.scalars(
            select(CorpusCandidate)
            .where(
                CorpusCandidate.status == "new",
                CorpusCandidate.relevance.is_(None),
                CorpusCandidate.triage_reason == "",
            )
            .order_by(CorpusCandidate.score.desc().nulls_last(), CorpusCandidate.id)
            .limit(limit)
        )
    )


def screen_candidates(
    session_factory,
    *,
    config: dict,
    post: Callable[[str, dict], object] | None = None,
    embed: Embedder | None = None,
    observed: dict | None = None,
    now: Callable[[], str] = corpus_refresh.utc_now,
    this_year: int | None = None,
    limit: int = SCREEN_LIMIT,
) -> dict:
    """
    Triage the candidates no run has judged yet; returns what happened. Without
    ``embed`` (see :func:`mistral_embedder`), candidates S2 has no SPECTER2 vector
    for wait for the next run or a person. ``observed`` collects the mistral-embed
    rate-limit headers the embedder saw.
    """
    cfg = config.get("curation") or corpus_refresh.CURATION_DEFAULTS
    this_year = this_year or datetime.now(UTC).year
    stamp = now()
    tally = {"keep": 0, "review": 0, "hidden": 0}
    out: dict = {"screened": 0, "bySpecter2": 0, "byMistralEmbed": 0, "errors": []}
    with session_factory() as s:
        cands = _unscreened(s, limit)
        if not cands:
            return {**out, "status": "nothing to screen"}
        positive, negative = corpus_refresh.human_examples(s)

        # SPECTER2: fetch vectors (and fresher metadata) for these candidates.
        fetched = {
            "checked": 0,
            "unresolved": 0,
            "embeddings": 0,
            "abstractsFromS2": 0,
            "venuesUpdated": 0,
            "errors": out["errors"],
        }
        corpus_curate.refresh_metadata(
            s,
            [],
            cands,
            post=post or semantic_scholar.post_json,
            now=stamp,
            stats=fetched,
        )
        vectors = corpus_curate.load_embeddings(s)
        rest = list(cands)
        try:
            measure, cutoffs, _, _ = corpus_curate.judge(
                vectors, positive, negative, cfg
            )
        except corpus_curate.CurationError as exc:
            out["errors"].append({"source": "specter2", "message": str(exc)})
        else:
            rest = []
            for cand in cands:
                if cand.ref not in vectors:
                    rest.append(cand)
                    continue
                decision = corpus_curate.decide_candidate(
                    s, cand, measure, cutoffs, this_year=this_year, now=stamp
                )
                tally[decision] += 1
                out["bySpecter2"] += 1
            s.commit()

        # mistral-embed for the candidates SPECTER2 could not judge.
        if rest and embed is not None:
            try:
                examples = _example_texts(s, [*positive, *negative])
                own = {c.ref: _text(c.title, c.abstract) for c in rest}
                refs = [*examples, *own]
                texts = [*examples.values(), *own.values()]
                space = {
                    ref: np.asarray(vec, dtype="<f4")
                    for ref, vec in zip(refs, embed(texts), strict=True)
                    if vec
                }
                # Fixed keepAt/hideBelow are SPECTER2 similarities; this space is
                # always calibrated on its own example vectors.
                measure, cutoffs, _, _ = corpus_curate.judge(
                    space,
                    positive,
                    negative,
                    {**cfg, "keepAt": None, "hideBelow": None},
                )
            except (EmbedError, corpus_curate.CurationError, ValueError) as exc:
                out["errors"].append({"source": "mistral-embed", "message": str(exc)})
            else:
                for cand in rest:
                    decision = corpus_curate.decide_candidate(
                        s,
                        cand,
                        measure,
                        cutoffs,
                        this_year=this_year,
                        now=stamp,
                        basis="mistral-embed",
                        # The dismissal margin was tuned on SPECTER2 similarities;
                        # in this space a weak match waits for a person instead.
                        may_hide=False,
                    )
                    tally[decision] += 1
                    out["byMistralEmbed"] += 1
                s.commit()
        if observed:
            out["mistralEmbedQuota"] = dict(observed)
    out["screened"] = out["bySpecter2"] + out["byMistralEmbed"]
    return {
        **out,
        "status": "partial" if out["errors"] else "ok",
        "admitted": tally["keep"],
        "review": tally["review"],
        "dismissed": tally["hidden"],
        "waiting": len(cands) - out["screened"],
    }


def scheduled_refresh(session_factory, *, config_path: Path | None = None) -> dict:
    """The scheduled job: fetch new candidates, then screen the unjudged ones."""
    out: dict = {}
    try:
        out["refresh"] = corpus_refresh.run_once(
            session_factory, config_path=config_path
        )
        config = corpus_refresh.load_config(
            config_path or corpus_refresh.DEFAULT_QUERIES
        )
    except (ValueError, corpus_refresh.RefreshInProgress) as exc:
        log.warning("scheduled refresh skipped: %s", exc)
        return {"refresh": {"status": "skipped", "message": str(exc)}}
    with session_factory() as s:
        out["searchCachePruned"] = semantic_scholar.prune_search_cache(
            s, now=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        s.commit()
    observed: dict = {}
    out["screening"] = screen_candidates(
        session_factory,
        config=config,
        embed=mistral_embedder(observed),
        observed=observed,
    )
    log.info("scheduled corpus refresh: %s", json.dumps(out, default=str)[:2000])
    return out
