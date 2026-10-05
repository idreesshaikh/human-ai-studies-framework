"""Study-scoped evidence maps and proposals, reusing researcher approval."""

import json
import secrets

from fastapi import Depends, HTTPException
from protocol.evidence import validate_evidence_map
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from middleware.db import ConversationTurn, DesignMoveRow, EvidenceMapRow
from middleware.evidence_mapping import (
    EvidenceContext,
    EvidenceProposal,
    digest,
    latest_map,
    rank_candidates,
)


def register_routes(app, db, require_study, now, conversation_seq, current_draft):
    path = "/studies/{study_id}/evidence-map"

    @app.get(path, dependencies=[Depends(require_study("view"))])
    def get_map(study_id: str, s: Session = Depends(db)):
        row = latest_map(s, study_id)
        return {
            "document": row.document if row else None,
            "digest": row.digest if row else None,
        }

    @app.put(path, dependencies=[Depends(require_study("contribute"))])
    def import_map(study_id: str, document: dict, s: Session = Depends(db)):
        if len(json.dumps(document)) > 1_000_000:
            raise HTTPException(413, "Evidence maps must be smaller than 1 MB.")
        errors = validate_evidence_map(document)
        if errors:
            raise HTTPException(422, "Invalid evidence map: " + "; ".join(errors[:8]))
        fingerprint = digest(document)
        existing = s.scalar(
            select(EvidenceMapRow).where(
                EvidenceMapRow.study_id == study_id,
                EvidenceMapRow.map_id == document["mapId"],
                EvidenceMapRow.map_version == document["mapVersion"],
            )
        )
        if existing:
            if existing.digest != fingerprint:
                raise HTTPException(
                    409,
                    "This version is immutable. Import changes with a new mapVersion.",
                )
            if latest_map(s, study_id).id != existing.id:
                raise HTTPException(
                    409,
                    "A newer map is active. Import a new version "
                    "rather than silently rolling it back.",
                )
        else:
            s.add(
                EvidenceMapRow(
                    study_id=study_id,
                    map_id=document["mapId"],
                    map_version=document["mapVersion"],
                    digest=fingerprint,
                    document=document,
                )
            )
            try:
                s.commit()
            except IntegrityError as exc:
                s.rollback()
                raise HTTPException(
                    409, "Another import completed. Reload and retry."
                ) from exc
        return {"document": document, "digest": fingerprint}

    @app.post(path + "/candidates", dependencies=[Depends(require_study("view"))])
    def candidates(study_id: str, body: EvidenceContext, s: Session = Depends(db)):
        row = latest_map(s, study_id)
        if not row:
            raise HTTPException(409, "Import an evidence map first.")
        return {"digest": row.digest, "candidates": rank_candidates(row.document, body)}

    @app.post(path + "/propose", dependencies=[Depends(require_study("contribute"))])
    def propose(study_id: str, body: EvidenceProposal, s: Session = Depends(db)):
        row = latest_map(s, study_id)
        if not row or row.digest != body.mapDigest:
            raise HTTPException(409, "The evidence map changed. Compare methods again.")
        context = EvidenceContext.model_validate(
            body.model_dump(include=set(EvidenceContext.model_fields), by_alias=True)
        )
        candidate = next(
            (
                c
                for c in rank_candidates(row.document, context)
                if c["id"] == body.candidateId
            ),
            None,
        )
        if not candidate or candidate["status"] not in ("compatible", "conditional"):
            raise HTTPException(
                409,
                "This method needs more evidence or does not meet your constraints.",
            )
        fingerprint = digest(body.model_dump(by_alias=True))
        draft = current_draft(s, study_id)
        recipes = list(
            dict.fromkeys(
                measure["analysisRecipe"]
                for measure in candidate["study"]["measures"]
                if measure["analysisRecipe"]
            )
        )
        target_rq = next(
            (
                rq["id"]
                for rq in draft.get("researchQuestions", [])
                if rq["text"].strip().casefold() == body.query.strip().casefold()
            ),
            None,
        )
        changes_design = (
            draft.get("participants", {}).get("design") != candidate["designFamily"]
        )
        if changes_design and (not recipes or not target_rq):
            raise HTTPException(
                409,
                "A design change needs mapped analysis recipes and an exact "
                "draft research-question match. Review the map and draft first.",
            )
        analysis = (
            {"rq": target_rq, "recipes": recipes} if recipes and target_rq else None
        )
        request_id = "evidence:" + body.requestId
        prior = s.scalar(
            select(ConversationTurn).where(
                ConversationTurn.study_id == study_id,
                ConversationTurn.request_id == request_id,
            )
        )
        if prior:
            move = s.scalar(
                select(DesignMoveRow).where(DesignMoveRow.turn_id == prior.id)
            )
            if move.grounding[0]["evidence"]["requestDigest"] != fingerprint:
                raise HTTPException(
                    409, "This request ID belongs to another evidence choice."
                )
            return {"moveId": move.id}
        turn = ConversationTurn(
            id=secrets.token_hex(8),
            study_id=study_id,
            seq=conversation_seq(s, study_id),
            role="platform",
            author="Evidence mapping",
            source="scripted",
            created_at=now(),
            request_id=request_id,
            text="Review this evidence-linked choice. Accepting it updates "
            "the draft, not the running protocol.",
        )
        s.add(turn)
        try:
            s.flush()
        except IntegrityError as exc:
            s.rollback()
            raise HTTPException(
                409, "The conversation changed. Retry this choice."
            ) from exc
        move_id = turn.id + ":evidence"
        snapshot = {
            "mapId": row.map_id,
            "mapVersion": row.map_version,
            "mapDescription": row.document["description"],
            "mapDigest": row.digest,
            "requestDigest": fingerprint,
            "context": context.model_dump(by_alias=True),
            "candidate": candidate,
        }
        s.add(
            DesignMoveRow(
                id=move_id,
                study_id=study_id,
                turn_id=turn.id,
                seq=1,
                kind="set-field",
                target="participants.design",
                proposal=f"Use a {candidate['designFamily']} design.",
                patch={
                    "op": "set-field",
                    "path": ["participants", "design"],
                    "value": candidate["designFamily"],
                    "evidenceAnalysis": analysis,
                },
                grounding=[
                    {
                        "ref": "evidence:" + row.map_id,
                        "title": "Evidence map " + row.map_version,
                        "why": "; ".join(candidate["reasons"]),
                        "evidence": snapshot,
                    }
                ],
                status="proposed",
            )
        )
        s.commit()
        return {"moveId": move_id}
