"""Library API routes."""

import logging
from collections import defaultdict
from hashlib import sha256
from urllib.parse import quote as _urlquote

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    UploadFile,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from middleware import (
    assistant,
    corpus_enrich,
    corpus_importer,
    corpus_refresh,
    matching,
    paper_index,
    pdf,
    semantic_scholar,
    template_registry,
)
from middleware.db import (
    CORPUS_STUDY_ID,
    Paper,
    PaperEdge,
    PaperLink,
    S2Cache,
    get_engine,
)
from middleware.routes.deps import ApiDeps
from middleware.schemas import (
    FromGraphIn,
    FromMatchIn,
    MatchIn,
    PaperIngestIn,
    PaperLinksIn,
)

log = logging.getLogger("middleware.app")


def register(app: FastAPI, deps: ApiDeps):
    @app.get(
        "/studies/{study_id}/papers",
        dependencies=[Depends(deps.authz["require_project_for_study"]("view"))],
    )
    def list_papers(study_id: str, s: Session = Depends(deps.db)) -> list[dict]:
        """The study's paper set."""

        study_protocol = deps.resolve_study_protocol(s, study_id)
        proto_refs = {
            entry.get("paperRef")
            for entry in (study_protocol or {}).get("literature", [])
        }
        links_by_ref: dict[str, list[str]] = defaultdict(list)
        for ref, target in s.execute(
            select(PaperLink.paper_ref, PaperLink.target).where(
                PaperLink.study_id == study_id
            )
        ):
            links_by_ref[ref].append(target)
        return [
            {
                "paperRef": p.paper_ref,
                "title": p.title,
                "authors": p.authors,
                "year": p.year,
                "venue": p.venue,
                "abstract": p.abstract,
                "doi": p.doi,
                "arxivId": p.arxiv_id,
                "url": p.url,
                "itemType": p.item_type,
                "source": p.source,
                "citationCount": p.citation_count,
                "hasFullText": bool(p.full_text),
                "links": sorted(links_by_ref.get(p.paper_ref, [])),
                "addedAt": p.added_at,
                "inProtocolLiterature": p.paper_ref in proto_refs,
            }
            for p in s.scalars(
                select(Paper).where(Paper.study_id == study_id).order_by(Paper.id)
            )
        ]

    def cached_fetch(s: Session):
        """
        A Semantic Scholar GET wrapped in the DB cache (D8, NFR-7): the graph renders
        offline after the first fetch.
        """

        def fetch(url: str) -> object:
            hit = s.scalar(select(S2Cache).where(S2Cache.url == url))
            if hit is not None:
                return hit.body
            body = semantic_scholar.get_json(url)
            s.add(S2Cache(url=url, body=body, fetched_at=deps.now()))
            return body

        return fetch

    def upsert_paper(s: Session, study_id: str, record: dict, *, source: str) -> None:
        """Insert-or-update one paper record and (re)index its text."""
        _paper_vals = {
            "study_id": study_id,
            "paper_ref": record["paperRef"],
            "title": record.get("title", ""),
            "authors": record.get("authors", []),
            "year": record.get("year"),
            "venue": record.get("venue", ""),
            "abstract": record.get("abstract", ""),
            "doi": record.get("doi", ""),
            "arxiv_id": record.get("arxivId", ""),
            "url": record.get("url", ""),
            "item_type": record.get("itemType", "paper"),
            "source": source,
            "s2_id": record.get("s2Id", ""),
            "citation_count": record.get("citationCount"),
            "full_text": record.get("fullText", ""),
            "added_at": deps.now(),
        }
        _update_vals = {
            "title": record.get("title", ""),
            "abstract": record.get("abstract", ""),
            "s2_id": record.get("s2Id", ""),
            "citation_count": record.get("citationCount"),
            **({"full_text": record["fullText"]} if record.get("fullText") else {}),
        }
        _engine = get_engine()
        if _engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as _pg_insert

            stmt = (
                _pg_insert(Paper)
                .values([_paper_vals])
                .on_conflict_do_update(
                    index_elements=["study_id", "paper_ref"], set_=_update_vals
                )
            )
        else:
            from sqlalchemy.dialects.sqlite import insert as _sq_insert

            stmt = (
                _sq_insert(Paper)
                .values([_paper_vals])
                .on_conflict_do_update(
                    index_elements=["study_id", "paper_ref"], set_=_update_vals
                )
            )
        s.execute(stmt)
        paper_index.index_paper(
            s,
            record["paperRef"],
            record.get("title", ""),
            record.get("fullText") or record.get("abstract", ""),
        )
        _seed_links(s, study_id, record["paperRef"])

    def _seed_links(s: Session, study_id: str, paper_ref: str) -> None:
        """
        Seed a newly-ingested paper's protocol links from the protocol's ``literature:``
        list (FR-LIT-3), idempotently.
        """
        _engine = get_engine()
        for target in assistant.protocol_literature_targets(deps.check.protocol).get(
            paper_ref, []
        ):
            if _engine.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as _pg_insert

                stmt = (
                    _pg_insert(PaperLink)
                    .values(study_id=study_id, paper_ref=paper_ref, target=target)
                    .on_conflict_do_nothing()
                )
            else:
                from sqlalchemy.dialects.sqlite import insert as _sq_insert

                stmt = (
                    _sq_insert(PaperLink)
                    .values(study_id=study_id, paper_ref=paper_ref, target=target)
                    .on_conflict_do_nothing(
                        index_elements=["study_id", "paper_ref", "target"]
                    )
                )
            s.execute(stmt)

    def _adopt_corpus_edges(s: Session, study_id: str, paper_ref: str) -> int:
        """Copy the corpus's own edges touching ``paper_ref`` into this study."""
        corpus_edges = list(
            s.scalars(
                select(PaperEdge).where(
                    PaperEdge.study_id == CORPUS_STUDY_ID,
                    (PaperEdge.src_ref == paper_ref) | (PaperEdge.dst_ref == paper_ref),
                )
            )
        )
        n = 0
        _engine = get_engine()
        for edge in corpus_edges:
            vals = {
                "study_id": study_id,
                "src_ref": edge.src_ref,
                "dst_ref": edge.dst_ref,
                "kind": edge.kind,
                "dst_title": edge.dst_title,
                "dst_authors": edge.dst_authors,
                "dst_year": edge.dst_year,
                "dst_abstract": edge.dst_abstract,
                "dst_citation_count": edge.dst_citation_count,
            }
            if _engine.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as _pg_insert

                stmt = _pg_insert(PaperEdge).values([vals]).on_conflict_do_nothing()
            else:
                from sqlalchemy.dialects.sqlite import insert as _sq_insert

                stmt = (
                    _sq_insert(PaperEdge)
                    .values([vals])
                    .on_conflict_do_nothing(
                        index_elements=["study_id", "src_ref", "dst_ref", "kind"]
                    )
                )
            n += len(s.execute(stmt.returning(PaperEdge.id)).fetchall())
        return n

    def harvest_edges(s: Session, study_id: str, paper_ref: str) -> int:
        """Fetch and store the paper's graph neighbourhood (FR-LIT-2)."""
        # Adding the same paper again should be a local idempotent read, not another
        # three remote calls. The persistent response cache handles individual URLs;
        # this guard handles the more common whole-paper repeat.
        if (
            s.scalar(
                select(PaperEdge.id).where(
                    PaperEdge.study_id == study_id,
                    PaperEdge.src_ref == paper_ref,
                    PaperEdge.kind.in_(("references", "citations", "recommendations")),
                )
            )
            is not None
        ):
            return 0
        try:
            edges = semantic_scholar.fetch_edges(paper_ref, fetch=cached_fetch(s))
        except semantic_scholar.SemanticScholarError as exc:
            log.warning("edge harvest failed for %s: %s", paper_ref, exc)
            return 0
        n = 0
        _engine = get_engine()
        for kind, neighbours in edges.items():
            for nb in neighbours:
                dst = nb["paperRef"]
                if dst == paper_ref:
                    continue
                _edge_vals = {
                    "study_id": study_id,
                    "src_ref": paper_ref,
                    "dst_ref": dst,
                    "kind": kind,
                    "dst_title": nb.get("title", ""),
                    "dst_authors": nb.get("authors") or None,
                    "dst_year": nb.get("year"),
                    "dst_abstract": nb.get("abstract", ""),
                    "dst_citation_count": nb.get("citationCount"),
                }
                if _engine.dialect.name == "postgresql":
                    from sqlalchemy.dialects.postgresql import insert as _pg_insert

                    stmt = (
                        _pg_insert(PaperEdge)
                        .values([_edge_vals])
                        .on_conflict_do_nothing()
                    )
                else:
                    from sqlalchemy.dialects.sqlite import insert as _sq_insert

                    stmt = (
                        _sq_insert(PaperEdge)
                        .values([_edge_vals])
                        .on_conflict_do_nothing(
                            index_elements=["study_id", "src_ref", "dst_ref", "kind"]
                        )
                    )
                n += len(s.execute(stmt.returning(PaperEdge.id)).fetchall())
        return n

    def harvest_edges_in_background(study_id: str, paper_ref: str) -> None:
        """Enrich after the paper has already become visible to the researcher."""
        with deps.session_factory() as background_session:
            harvest_edges(background_session, study_id, paper_ref)
            background_session.commit()

    @app.post(
        "/studies/{study_id}/papers",
        dependencies=[Depends(deps.authz["require_project_for_study"]("contribute"))],
    )
    def ingest_paper(
        study_id: str,
        body: PaperIngestIn,
        background_tasks: BackgroundTasks,
        s: Session = Depends(deps.db),
    ) -> dict:
        """
        Ingest one paper by arXiv id / DOI (FR-LIT-1 id path): fetch S2 metadata, index
        it, and harvest its graph neighbourhood (FR-LIT-2).
        """

        if body.arxivId:
            ref = f"arxiv:{body.arxivId.strip()}"
        elif body.doi:
            ref = f"doi:{body.doi.strip().lower()}"
        else:
            raise HTTPException(400, "provide arxivId or doi")
        try:
            record = semantic_scholar.fetch_paper(ref, fetch=cached_fetch(s))
        except semantic_scholar.SemanticScholarError as exc:
            if exc.status == 404:
                raise HTTPException(
                    404, "We couldn't find that paper. Check the arXiv id or DOI."
                ) from exc
            raise HTTPException(
                502, "Paper lookup is unavailable right now. Try again later."
            ) from exc
        upsert_paper(s, study_id, record, source="id")
        adopted = _adopt_corpus_edges(s, study_id, record["paperRef"])
        # Release the request transaction before the background session opens its
        # enrichment transaction. This matters for SQLite, where a response that is
        # already ready can still hold the writer lock until dependency cleanup.
        s.commit()
        # Metadata is the blocking part of the add action. The neighbourhood is useful
        # but not required to confirm the paper, so let the graph catch up in a fresh
        # session after this response is sent.
        background_tasks.add_task(
            harvest_edges_in_background, study_id, record["paperRef"]
        )
        return {
            "paperRef": record["paperRef"],
            "title": record["title"],
            "edges": adopted,
            "edgesPending": True,
        }

    @app.post(
        "/studies/{study_id}/papers/upload",
        dependencies=[Depends(deps.authz["require_project_for_study"]("contribute"))],
    )
    async def ingest_paper_pdf(
        study_id: str, file: UploadFile, s: Session = Depends(deps.db)
    ) -> dict:
        """
        Ingest a paper from a PDF (FR-LIT-1 PDF path): extract text + a title guess
        locally (D21), then enrich by DOI/title via S2 when possible.
        """

        content = await file.read()
        if not content.startswith(b"%PDF-"):
            raise HTTPException(415, "Upload a PDF file.")
        extracted = pdf.extract(content)
        record = None
        title = extracted["title"] or (file.filename or "uploaded.pdf")
        try:
            hits = semantic_scholar.get_json(
                f"{semantic_scholar.GRAPH_API}/paper/search?"
                f"query={_urlquote(title)}&fields={semantic_scholar.PAPER_FIELDS}&limit=1"
            )
            papers = hits.get("data") if isinstance(hits, dict) else None
            if papers:
                record = semantic_scholar.normalize_paper(papers[0])
        except semantic_scholar.SemanticScholarError:
            record = None
        if record is None:
            digest = sha256(content).hexdigest()[:16]
            record = {
                "paperRef": f"pdf:{digest}",
                "title": title,
                "authors": [],
                "abstract": "",
            }
        record["fullText"] = extracted["text"]
        upsert_paper(s, study_id, record, source="upload")
        edges = 0
        if not record["paperRef"].startswith("pdf:"):
            edges = harvest_edges(s, study_id, record["paperRef"])
        return {
            "paperRef": record["paperRef"],
            "title": record["title"],
            "textChars": len(extracted["text"]),
            "edges": edges,
        }

    @app.delete(
        "/studies/{study_id}/papers/{paper_ref:path}",
        dependencies=[Depends(deps.authz["require_project_for_study"]("contribute"))],
    )
    def delete_paper(
        study_id: str, paper_ref: str, s: Session = Depends(deps.db)
    ) -> dict:

        deleted = s.execute(
            select(Paper).where(
                Paper.study_id == study_id, Paper.paper_ref == paper_ref
            )
        ).scalar_one_or_none()
        if deleted is None:
            raise HTTPException(404, f"no paper {paper_ref!r}")
        s.delete(deleted)
        for edge in s.scalars(
            select(PaperEdge).where(
                PaperEdge.study_id == study_id,
                (PaperEdge.src_ref == paper_ref) | (PaperEdge.dst_ref == paper_ref),
            )
        ):
            s.delete(edge)
        for link in s.scalars(
            select(PaperLink).where(
                PaperLink.study_id == study_id, PaperLink.paper_ref == paper_ref
            )
        ):
            s.delete(link)
        # The FTS table is intentionally shared by the corpus and every study. A
        # graph suggestion is only warm edge metadata until it is explicitly added;
        # once added, deleting it from one study must not erase the same paper from
        # another study or from the corpus search index.
        has_another_copy = s.scalar(
            select(Paper.id).where(
                Paper.paper_ref == paper_ref,
                Paper.id != deleted.id,
            )
        )
        if has_another_copy is None:
            paper_index.deindex_paper(s, paper_ref)
        return {"deleted": paper_ref}

    @app.get(
        "/studies/{study_id}/papers/graph",
        dependencies=[Depends(deps.authz["require_project_for_study"]("view"))],
    )
    def papers_graph(study_id: str, s: Session = Depends(deps.db)) -> dict:
        """
        The related-papers graph (FR-LIT-2): ingested nodes (solid) plus suggested stub
        nodes (hollow, un-ingested), and the typed edges between them - the
        ResearchRabbit-style view's data.
        """

        ingested = {
            p.paper_ref: p
            for p in s.scalars(select(Paper).where(Paper.study_id == study_id))
        }
        edges = list(s.scalars(select(PaperEdge).where(PaperEdge.study_id == study_id)))
        nodes: dict[str, dict] = {}
        for ref, p in ingested.items():
            nodes[ref] = {
                "paperRef": ref,
                "title": p.title,
                "authors": p.authors,
                "year": p.year,
                "abstract": p.abstract,
                "citationCount": p.citation_count,
                "ingested": True,
            }

        # A harvested edge may point back to a corpus paper that has not been
        # ingested into this study. The old response only materialised the
        # destination stub, leaving that edge's source without a node. The
        # client quite correctly refused to paint a path between a node and
        # nothing, which made references, citations, and recommendations all
        # appear to have vanished. Materialise both endpoints, preferring
        # study metadata and then the shared corpus metadata when available.
        endpoint_refs = {e.src_ref for e in edges} | {e.dst_ref for e in edges}
        missing_refs = endpoint_refs - nodes.keys()
        paper_metadata: dict[str, Paper] = {}
        if missing_refs:
            for p in s.scalars(
                select(Paper).where(
                    Paper.paper_ref.in_(missing_refs),
                    Paper.study_id.in_([study_id, CORPUS_STUDY_ID]),
                )
            ):
                if p.paper_ref not in paper_metadata or p.study_id == study_id:
                    paper_metadata[p.paper_ref] = p

        for ref in missing_refs:
            p = paper_metadata.get(ref)
            edge_metadata = next(
                (
                    edge
                    for edge in reversed(edges)
                    if edge.dst_ref == ref and edge.dst_title
                ),
                None,
            )
            title = (p.title if p else "") or (
                edge_metadata.dst_title if edge_metadata else ""
            )
            authors = (
                (p.authors if p else None)
                or (edge_metadata.dst_authors if edge_metadata else None)
                or []
            )
            year = (
                p.year
                if p and p.year is not None
                else (edge_metadata.dst_year if edge_metadata else None)
            )
            abstract = (p.abstract if p else "") or (
                edge_metadata.dst_abstract if edge_metadata else ""
            )
            citation_count = (
                p.citation_count
                if p and p.citation_count is not None
                else (edge_metadata.dst_citation_count if edge_metadata else None)
            )
            nodes[ref] = {
                "paperRef": ref,
                "title": title,
                "authors": authors,
                "year": year,
                "abstract": abstract,
                "citationCount": citation_count,
                "ingested": False,
            }

        for e in edges:
            if e.dst_ref not in nodes:
                nodes[e.dst_ref] = {
                    "paperRef": e.dst_ref,
                    "title": e.dst_title,
                    "authors": e.dst_authors or [],
                    "year": e.dst_year,
                    "abstract": e.dst_abstract,
                    "citationCount": e.dst_citation_count,
                    "ingested": False,
                }
        return {
            "studyId": study_id,
            "nodes": sorted(nodes.values(), key=lambda n: not n["ingested"]),
            "edges": [
                {"src": e.src_ref, "dst": e.dst_ref, "kind": e.kind} for e in edges
            ],
        }

    @app.post(
        "/studies/{study_id}/papers/match",
        dependencies=[Depends(deps.authz["require_project_for_study"]("view"))],
    )
    def match_study_papers(
        study_id: str, body: MatchIn, s: Session = Depends(deps.db)
    ) -> dict:
        """Idea → paper recommendations via the match ladder (FR-LIT-9)."""
        recommendations = matching.match_papers(
            s,
            body.query,
            study_id=study_id,
            limit=body.limit,
            # Keep the interaction responsive and deterministic. The design
            # conversation has its own model call; adding a second reranker and
            # query-expansion call here made a paper recommendation block the
            # next turn without improving the evidence trail reliably.
            use_llm=False,
            expand=False,
        )
        return {"studyId": study_id, "recommendations": recommendations}

    def _adopt_corpus_paper(
        s: Session,
        study_id: str,
        ref: str,
        *,
        added_via: str,
        match_reason: str = "",
    ) -> str | None:
        """
        Copy one corpus paper into a study's own paper set, or return None if the corpus
        does not hold it.
        """
        corpus_row = s.execute(
            select(Paper).where(
                Paper.study_id == CORPUS_STUDY_ID, Paper.paper_ref == ref
            )
        ).scalar_one_or_none()
        if corpus_row is None:
            return None
        vals = {
            "study_id": study_id,
            "paper_ref": corpus_row.paper_ref,
            "title": corpus_row.title,
            "authors": corpus_row.authors,
            "year": corpus_row.year,
            "venue": corpus_row.venue,
            "abstract": corpus_row.abstract,
            "doi": corpus_row.doi,
            "arxiv_id": corpus_row.arxiv_id,
            "url": corpus_row.url,
            "item_type": corpus_row.item_type,
            "source": added_via,
            "s2_id": corpus_row.s2_id,
            "citation_count": corpus_row.citation_count,
            "tier": corpus_row.tier,
            "added_via": added_via,
            "match_reason": match_reason,
            "added_at": deps.now(),
        }
        update = {"added_via": added_via, "match_reason": match_reason}
        engine = get_engine()
        if engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as _pg_insert

            stmt = (
                _pg_insert(Paper)
                .values([vals])
                .on_conflict_do_update(
                    index_elements=["study_id", "paper_ref"], set_=update
                )
            )
        else:
            from sqlalchemy.dialects.sqlite import insert as _sq_insert

            stmt = (
                _sq_insert(Paper)
                .values([vals])
                .on_conflict_do_update(
                    index_elements=["study_id", "paper_ref"], set_=update
                )
            )
        s.execute(stmt)
        _seed_links(s, study_id, corpus_row.paper_ref)
        _adopt_corpus_edges(s, study_id, corpus_row.paper_ref)
        return corpus_row.paper_ref

    def _warmed_graph_record(s: Session, study_id: str, paper_ref: str) -> dict | None:
        """Build an ingest record from metadata already stored on a graph edge.

        A graph suggestion is not an invitation to make another rate-limited metadata
        request. The edge harvest already paid that cost and stores the preview fields
        needed to make the node useful. This is also the graceful path when Semantic
        Scholar is temporarily returning 429s.
        """
        edge = s.scalar(
            select(PaperEdge)
            .where(
                PaperEdge.study_id == study_id,
                PaperEdge.dst_ref == paper_ref,
                PaperEdge.dst_title != "",
            )
            .order_by(PaperEdge.id.desc())
        )
        if edge is None:
            return None
        record = {
            "paperRef": paper_ref,
            "title": edge.dst_title,
            "authors": edge.dst_authors or [],
            "year": edge.dst_year,
            "venue": "",
            "abstract": edge.dst_abstract or "",
            "doi": paper_ref.removeprefix("doi:"),
            "arxivId": paper_ref.removeprefix("arxiv:"),
            "url": "",
            "citationCount": edge.dst_citation_count,
            "itemType": "paper",
            "source": "graph",
        }
        if paper_ref.startswith("arxiv:"):
            record["url"] = f"https://arxiv.org/abs/{record['arxivId']}"
        elif paper_ref.startswith("doi:"):
            record["url"] = f"https://doi.org/{record['doi']}"
        elif paper_ref.startswith("s2:"):
            record["url"] = (
                f"https://www.semanticscholar.org/paper/{paper_ref.removeprefix('s2:')}"
            )
        return record

    @app.post(
        "/studies/{study_id}/papers/from-match",
        dependencies=[Depends(deps.authz["require_project_for_study"]("contribute"))],
    )
    def add_paper_from_match(
        study_id: str,
        body: FromMatchIn,
        background_tasks: BackgroundTasks,
        s: Session = Depends(deps.db),
    ) -> dict:
        """
        One-click ingest of a recommendation card (FR-LIT-9.3): the corpus row joins the
        study's paper set with ``addedVia=match`` and the match reason kept - it is
        elicitation evidence.
        """
        corpus_row = s.execute(
            select(Paper).where(
                Paper.study_id == CORPUS_STUDY_ID, Paper.paper_ref == body.ref
            )
        ).scalar_one_or_none()
        if corpus_row is None:
            raise HTTPException(404, f"paper {body.ref!r} is not in the corpus")
        _match_vals = {
            "study_id": study_id,
            "paper_ref": corpus_row.paper_ref,
            "title": corpus_row.title,
            "authors": corpus_row.authors,
            "year": corpus_row.year,
            "venue": corpus_row.venue,
            "abstract": corpus_row.abstract,
            "doi": corpus_row.doi,
            "arxiv_id": corpus_row.arxiv_id,
            "url": corpus_row.url,
            "item_type": corpus_row.item_type,
            "source": "match",
            "s2_id": corpus_row.s2_id,
            "citation_count": corpus_row.citation_count,
            "tier": corpus_row.tier,
            "added_via": "match",
            "match_reason": body.matchReason,
            "added_at": deps.now(),
        }
        _match_update = {"added_via": "match", "match_reason": body.matchReason}
        _engine = get_engine()
        if _engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as _pg_insert

            stmt = (
                _pg_insert(Paper)
                .values([_match_vals])
                .on_conflict_do_update(
                    index_elements=["study_id", "paper_ref"], set_=_match_update
                )
            )
        else:
            from sqlalchemy.dialects.sqlite import insert as _sq_insert

            stmt = (
                _sq_insert(Paper)
                .values([_match_vals])
                .on_conflict_do_update(
                    index_elements=["study_id", "paper_ref"], set_=_match_update
                )
            )
        s.execute(stmt)
        _seed_links(s, study_id, corpus_row.paper_ref)
        adopted = _adopt_corpus_edges(s, study_id, corpus_row.paper_ref)
        # A corpus recommendation may carry provenance edges but not the full
        # Semantic Scholar neighbourhood. Start the same enrichment used by
        # direct ingest so accepting a recommendation grows the graph too.
        s.commit()
        background_tasks.add_task(
            harvest_edges_in_background, study_id, corpus_row.paper_ref
        )
        return {
            "studyId": study_id,
            "paperRef": corpus_row.paper_ref,
            "title": corpus_row.title,
            "tier": corpus_row.tier,
            "addedVia": "match",
            "edges": adopted,
            "edgesPending": True,
        }

    @app.post(
        "/studies/{study_id}/papers/from-graph",
        dependencies=[Depends(deps.authz["require_project_for_study"]("contribute"))],
    )
    def add_paper_from_graph(
        study_id: str,
        body: FromGraphIn,
        background_tasks: BackgroundTasks,
        s: Session = Depends(deps.db),
    ) -> dict:
        """Add a visible graph suggestion without repeating its upstream fetch.

        The Library detail panel is backed by the same graph a researcher is reading.
        If the node is already warm there, it must be actionable even when the remote
        provider is rate-limited. Only a genuinely cold node falls back to a fresh S2
        metadata request.
        """
        paper_ref = body.ref.strip()
        if not paper_ref:
            raise HTTPException(400, "paper ref is required")

        existing = s.scalar(
            select(Paper).where(
                Paper.study_id == study_id, Paper.paper_ref == paper_ref
            )
        )
        if existing is not None:
            return {
                "studyId": study_id,
                "paperRef": paper_ref,
                "title": existing.title,
                "edges": 0,
                "edgesPending": False,
            }

        adopted = _adopt_corpus_paper(
            s, study_id, paper_ref, added_via="graph", match_reason=""
        )
        if adopted is not None:
            has_edges = (
                s.scalar(
                    select(PaperEdge.id).where(
                        PaperEdge.study_id == study_id,
                        (PaperEdge.src_ref == paper_ref)
                        | (PaperEdge.dst_ref == paper_ref),
                    )
                )
                is not None
            )
            s.commit()
            if not has_edges:
                background_tasks.add_task(
                    harvest_edges_in_background, study_id, paper_ref
                )
            title = (
                s.scalar(
                    select(Paper.title).where(
                        Paper.study_id == study_id, Paper.paper_ref == paper_ref
                    )
                )
                or paper_ref
            )
            return {
                "studyId": study_id,
                "paperRef": paper_ref,
                "title": title,
                "edges": 0,
                "edgesPending": not has_edges,
            }

        record = _warmed_graph_record(s, study_id, paper_ref)
        edges_pending = record is None
        if record is None:
            try:
                record = semantic_scholar.fetch_paper(paper_ref, fetch=cached_fetch(s))
            except semantic_scholar.SemanticScholarError as exc:
                raise HTTPException(502, f"Semantic Scholar: {exc}") from exc

        upsert_paper(s, study_id, record, source="graph")
        adopted_edges = _adopt_corpus_edges(s, study_id, paper_ref)
        s.commit()
        # A warm graph node already has the neighbourhood edge that made it
        # actionable. Do not turn a successful click into another rate-limited
        # provider request; only genuinely cold metadata needs enrichment.
        if edges_pending:
            background_tasks.add_task(harvest_edges_in_background, study_id, paper_ref)
        return {
            "studyId": study_id,
            "paperRef": paper_ref,
            "title": record.get("title", paper_ref),
            "edges": adopted_edges,
            "edgesPending": edges_pending,
        }

    @app.get(
        "/studies/{study_id}/papers/{paper_ref:path}/links",
        dependencies=[Depends(deps.authz["require_project_for_study"]("view"))],
    )
    def get_paper_links(
        study_id: str, paper_ref: str, s: Session = Depends(deps.db)
    ) -> dict:

        targets = sorted(
            s.scalars(
                select(PaperLink.target).where(
                    PaperLink.study_id == study_id, PaperLink.paper_ref == paper_ref
                )
            )
        )
        return {"paperRef": paper_ref, "links": targets}

    @app.put(
        "/studies/{study_id}/papers/{paper_ref:path}/links",
        dependencies=[Depends(deps.authz["require_project_for_study"]("contribute"))],
    )
    def set_paper_links(
        study_id: str, paper_ref: str, body: PaperLinksIn, s: Session = Depends(deps.db)
    ) -> dict:
        """Replace a paper's protocol-element links (FR-LIT-3)."""

        for link in s.scalars(
            select(PaperLink).where(
                PaperLink.study_id == study_id, PaperLink.paper_ref == paper_ref
            )
        ):
            s.delete(link)
        s.flush()
        wanted = sorted({t.strip() for t in body.targets if t.strip()})
        for target in wanted:
            s.add(PaperLink(study_id=study_id, paper_ref=paper_ref, target=target))
        return {"paperRef": paper_ref, "links": wanted}

    @app.get("/papers/index")
    def corpus_index() -> dict:
        """Return the machine-readable literature index."""
        repo = template_registry.REPO
        corpus_index_path = repo / "docs" / "papers" / "corpus-index.json"

        if corpus_index_path.exists():
            import json

            return json.loads(corpus_index_path.read_text())

        return {
            "generatedAt": "",
            "pipeline": "",
            "tierA": {"count": 0, "arxivResolvable": 0, "source": ""},
            "tierB": [],
            "scoringVersion": 0,
        }

    @app.get("/corpus/status")
    def corpus_status(s: Session = Depends(deps.db)) -> dict:
        """
        How much of the corpus carries a real abstract, not just a title (FR-LIT-8
        quality).
        """
        return {
            **corpus_importer.corpus_status_for_session(s),
            **corpus_enrich.enrichment_status_for_session(s),
            "lastRefresh": corpus_refresh.last_run_summary(
                s, today=deps.clock().date()
            ),
            "candidates": corpus_refresh.candidate_counts(s),
        }

    @app.get(
        "/corpus/candidates", dependencies=[Depends(deps.authz["resolve_identity"])]
    )
    def corpus_candidates(
        status: str = "new", limit: int = 50, s: Session = Depends(deps.db)
    ) -> dict:
        """
        Papers a refresh found, awaiting a human decision (read-only; decide
        via CLI).
        """
        if not 1 <= limit <= 200:
            raise HTTPException(422, "limit must be between 1 and 200")
        try:
            rows = corpus_refresh.list_candidates(s, status=status, limit=limit)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {
            "status": status,
            "candidates": rows,
            **corpus_refresh.candidate_counts(s),
        }

    return _adopt_corpus_paper
