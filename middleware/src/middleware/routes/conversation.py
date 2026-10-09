"""Conversation API routes."""

import logging
import secrets
from collections import defaultdict
from hashlib import sha256

import yaml
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
)
from fastapi.responses import (
    StreamingResponse,
)
from protocol.measure_catalog import catalog_entry, suggest_measures
from sqlalchemy import select
from sqlalchemy.orm import Session

from middleware import (
    assistant,
    auth,
    compiler,
    corpus_importer,
    design_assistant,
    elicitation,
    template_registry,
    template_repertoire,
)
from middleware.db import (
    ApprovalEvent,
    Compilation,
    ConversationTurn,
    DesignMoveRow,
    Membership,
    Paper,
    ProtocolDraftRow,
)
from middleware.evidence_mapping import evidence_export
from middleware.route_helpers import (
    _sse,
)
from middleware.routes.deps import ApiDeps
from middleware.schemas import (
    ApproveIn,
    CompileIn,
    ConversationTurnIn,
    DecisionTriggerIn,
    MeasureSuggestionIn,
    MoveDecisionIn,
    QuickProtocolIn,
    TemplateInstantiateIn,
)

log = logging.getLogger("middleware.app")


def register(app: FastAPI, deps: ApiDeps):
    @app.post(
        "/studies/{study_id}/measure-suggestions",
        dependencies=[Depends(deps.authz["require_project_for_study"]("contribute"))],
    )
    def measure_suggestions(study_id: str, body: MeasureSuggestionIn) -> dict:
        if not body.text.strip():
            raise HTTPException(422, "Describe the outcome you want to measure.")
        return {
            **suggest_measures(body.text, body.design, top_k=body.topK),
            "requestId": body.requestId,
        }

    @app.get("/templates/featured")
    def featured_templates() -> list[dict]:
        """V6 starting designs, with the complete registry still available."""
        return template_registry.featured_templates()

    @app.get("/templates")
    def template_index() -> dict:
        """Return the machine-readable template registry index."""
        templates_dir = template_registry.REGISTRY_DIR

        templates = []
        if templates_dir.exists():
            import yaml

            for template_file in sorted(templates_dir.glob("*.yaml")):
                try:
                    with open(template_file) as f:
                        template_data = yaml.safe_load(f)
                    templates.append(
                        {
                            "id": template_data.get("templateId", ""),
                            "version": template_data.get("templateVersion", 1),
                            "title": template_data.get("title", ""),
                            "description": template_data.get("description", ""),
                            "designType": template_data.get("designType", ""),
                            "dataPath": template_data.get("dataPath", ""),
                            "source": template_data.get("source", []),
                        }
                    )
                except Exception:  # noqa: BLE001,S112 - skip unparseable template files
                    # Skip files that can't be parsed.
                    continue

        return {
            "templates": templates,
            "count": len(templates),
            "generatedAt": deps.now(),
        }

    @app.get("/conversation/profiles")
    def researcher_profiles() -> dict:
        """The researcher profiles the design conversation adapts to (FR-CONV-9)."""
        return {
            "profiles": elicitation.profile_catalog(),
            "default": elicitation.DEFAULT_PROFILE,
        }

    @app.post("/templates/{template_id}/instantiate")
    def instantiate_template(template_id: str, body: TemplateInstantiateIn) -> dict:
        """Template + parameters → a validated protocol draft (FR-TPL-1.4)."""
        try:
            template_registry.load_template(template_id)
        except template_registry.TemplateError as exc:
            raise HTTPException(404, "template not found") from exc
        params = dict(body.parameters)
        if body.studyId:
            params.setdefault("studyId", body.studyId)
        if body.title:
            params.setdefault("title", body.title)
        try:
            out = template_registry.instantiate_template(template_id, params)
        except template_registry.TemplateError as exc:
            raise HTTPException(422, str(exc)) from exc
        out["yaml"] = yaml.safe_dump(
            out["protocol"], sort_keys=False, default_flow_style=False
        )
        return out

    @app.get("/templates/{template_id}/plan")
    def template_plan(template_id: str) -> dict:
        """
        The statistical-plan explainer (FR-TPL-2.3): each choice in plain language with
        its why  -  never a bare test name.
        """
        try:
            tpl = template_registry.load_template(template_id)
        except template_registry.TemplateError as exc:
            raise HTTPException(404, "template not found") from exc
        return {
            "templateId": template_id,
            "explanation": template_registry.explain_plan(tpl),
        }

    @app.get("/templates/repertoire")
    def template_repertoire_route(
        limitRefs: int = 6,
        s: Session = Depends(deps.db),
    ) -> dict:
        """
        The protocol repertoire (FR-TPL): design shapes ranked common → rare by how many
        corpus papers use them, each carrying its ranked references.
        """
        corpus = corpus_importer.corpus_status_for_session(s)
        # Do not repeatedly scan a partially imported corpus. The client keeps the
        # small readiness poll cheap and only asks for the full ranking once every
        # manifest row is present, so partial matches can never look authoritative.
        entries = (
            template_repertoire.rank_repertoire(
                s, limit_refs=max(1, min(limitRefs, 20))
            )
            if corpus["state"] == "ready"
            else []
        )
        return {
            "repertoire": entries,
            "count": len(entries),
            "minReferenceConfidence": template_repertoire.MIN_REFERENCE_CONFIDENCE,
            "corpus": corpus,
            "generatedAt": deps.now(),
        }

    def _validate_decision_followup(
        s: Session, study_id: str, decision: DecisionTriggerIn | None
    ) -> None:
        """Keep a follow-up tied to the decision the server just recorded."""
        if decision is None:
            return
        move = s.get(DesignMoveRow, decision.moveId)
        expected = "rejected" if decision.action == "rejected" else "accepted"
        if move is None or move.study_id != study_id or move.status != expected:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This card decision is no longer current. "
                    "Refresh the conversation and try again."
                ),
            )
        if decision.action == "noted" and move.kind != "caution":
            raise HTTPException(
                status_code=409,
                detail="Only a caution card can be noted.",
            )

    def _turn_for_request(
        s: Session, study_id: str, request_id: str | None
    ) -> ConversationTurn | None:
        """Find a previously committed turn for a retried browser request."""
        if not request_id:
            return None
        return s.scalar(
            select(ConversationTurn).where(
                ConversationTurn.study_id == study_id,
                ConversationTurn.request_id == request_id,
            )
        )

    def _stored_turn_payload(
        s: Session, study_id: str, researcher: ConversationTurn
    ) -> dict | None:
        """Return the same wire shape as a fresh reply for an idempotent retry."""
        platform = s.scalar(
            select(ConversationTurn).where(
                ConversationTurn.study_id == study_id,
                ConversationTurn.role == "platform",
                ConversationTurn.seq == researcher.seq + 1,
            )
        )
        if platform is None:
            return None
        moves = []
        for move in s.scalars(
            select(DesignMoveRow)
            .where(DesignMoveRow.turn_id == platform.id)
            .order_by(DesignMoveRow.seq)
        ):
            item = {
                "moveId": move.id,
                "kind": move.kind,
                "target": move.target,
                "proposal": move.proposal,
                "patch": move.patch,
                "grounding": move.grounding,
                "status": move.status,
            }
            if move.kind == "merge-templates" and move.patch:
                item["mergeData"] = {
                    "templateIds": list(move.patch.get("templateIds") or []),
                    "reason": str(move.patch.get("reason") or ""),
                }
            moves.append(item)
        return {
            "researcherTurnId": researcher.id,
            "platformTurnId": platform.id,
            "text": platform.text,
            "moves": moves,
            "recommendations": platform.recommendations or [],
            "source": platform.source,
            "understanding": None,
            "turnIntent": "",
        }

    @app.post(
        "/studies/{study_id}/conversation/turns",
        dependencies=[Depends(deps.authz["require_project_for_study"]("contribute"))],
    )
    def append_turn(
        study_id: str,
        body: ConversationTurnIn,
        s: Session = Depends(deps.db),
        identity: auth.Identity = Depends(deps.authz["resolve_identity"]),
    ) -> dict:
        """
        Append a researcher turn and generate the platform's grounded reply (FR-CONV-1).
        """
        _validate_decision_followup(s, study_id, body.decision)
        existing = _turn_for_request(s, study_id, body.requestId)
        if existing is not None:
            replay = _stored_turn_payload(s, study_id, existing)
            if replay is not None:
                return replay
        researcher = _append_researcher_turn(s, study_id, body)
        try:
            reply = design_assistant.respond(
                s,
                body.text,
                seq=researcher.seq + 1,
                study_id=study_id,
                client=_design_turn_client(),
                steer=body.steer,
                decision=body.decision.model_dump() if body.decision else None,
            )
        except design_assistant.ModelUnavailable as exc:
            log.info("design turn unanswered: %s", exc)
            # Persisted like any other reply, not held in memory only. The
            # unpersisted version was the researcher's own question surviving
            # a reload while the platform's explanation of why it went
            # unanswered did not  -  so the exact moment a plain answer mattered
            # most was the one moment it was allowed to vanish. `source:
            # "unavailable"` still marks it as neither grounded nor scripted;
            # the client already renders that source as "Not answered"
            # (StreamingTurn.tsx) rather than as a real reply.
            return _persist_platform_turn(
                s, study_id, researcher, design_assistant.holding_turn(str(exc))
            )
        return _persist_platform_turn(s, study_id, researcher, reply)

    def _append_researcher_turn(
        s: Session, study_id: str, body: ConversationTurnIn
    ) -> ConversationTurn:
        """Land the researcher's own turn; its seq settles the reply's."""
        researcher = ConversationTurn(
            id=secrets.token_hex(8),
            study_id=study_id,
            seq=deps.conversation_seq(s, study_id),
            role="researcher",
            author=body.author,
            text=body.text,
            retrieved_refs=[],
            created_at=deps.now(),
            request_id=body.requestId or None,
        )
        s.add(researcher)
        s.flush()
        return researcher

    def _design_turn_client():
        """
        Use the fast, schema-constrained design model for protocol-shaping turns. The
        knowledge assistant retains its larger model for citation-heavy answers.
        """
        return assistant.make_design_client()

    def _persist_platform_turn(
        s: Session, study_id: str, researcher: ConversationTurn, reply: dict
    ) -> dict:
        """Persist the platform reply + its moves and return the wire shape."""
        retrieved = set(reply["retrievedRefs"])
        for m in reply["moves"]:
            cited = {g["ref"] for g in m["grounding"]}
            assert cited <= retrieved, (  # noqa: S101 - FR-ETH-4 boundary
                f"move {m['moveId']} cites outside retrieved set: "
                f"{sorted(cited - retrieved)}"
            )
        platform = ConversationTurn(
            id=secrets.token_hex(8),
            study_id=study_id,
            seq=researcher.seq + 1,
            role="platform",
            author="Platform",
            text=reply["text"],
            retrieved_refs=sorted(retrieved),
            recommendations=reply["recommendations"],
            created_at=deps.now(),
            source=reply["source"],
        )
        s.add(platform)
        for i, m in enumerate(reply["moves"]):
            s.add(
                DesignMoveRow(
                    id=f"{platform.id}:{m['moveId']}",
                    study_id=study_id,
                    turn_id=platform.id,
                    seq=i + 1,
                    kind=m["kind"],
                    target=m["target"],
                    proposal=m["proposal"],
                    patch=m["patch"],
                    grounding=m["grounding"],
                    status="proposed",
                )
            )
        s.commit()
        return {
            "researcherTurnId": researcher.id,
            "platformTurnId": platform.id,
            "text": reply["text"],
            "moves": [
                {
                    "moveId": f"{platform.id}:{m['moveId']}",
                    "kind": m["kind"],
                    "target": m["target"],
                    "proposal": m["proposal"],
                    "patch": m["patch"],
                    "grounding": m["grounding"],
                    "status": "proposed",
                    **(
                        {"mergeData": m["mergeData"]}
                        if m["kind"] == "merge-templates" and m.get("mergeData")
                        else {}
                    ),
                }
                for m in reply["moves"]
            ],
            "recommendations": reply["recommendations"],
            "source": reply["source"],
            "understanding": reply["understanding"],
            "turnIntent": reply["turnIntent"],
        }

    @app.post(
        "/studies/{study_id}/conversation/turns/stream",
        dependencies=[Depends(deps.authz["require_project_for_study"]("contribute"))],
    )
    def append_turn_streaming(
        study_id: str,
        body: ConversationTurnIn,
        s: Session = Depends(deps.db),
        identity: auth.Identity = Depends(deps.authz["resolve_identity"]),
    ) -> StreamingResponse:
        """The same turn as ``POST .../turns``, streamed (NFR-12)."""

        def frames():
            try:
                _validate_decision_followup(s, study_id, body.decision)
                existing = _turn_for_request(s, study_id, body.requestId)
                if existing is not None:
                    replay = _stored_turn_payload(s, study_id, existing)
                    if replay is not None:
                        yield _sse("done", replay)
                        return
                researcher = _append_researcher_turn(s, study_id, body)
                stream = design_assistant.respond_streaming(
                    s,
                    body.text,
                    seq=researcher.seq + 1,
                    study_id=study_id,
                    client=_design_turn_client(),
                    steer=body.steer,
                    decision=body.decision.model_dump() if body.decision else None,
                )
                reply = None
                while True:
                    try:
                        prose = next(stream)
                    except StopIteration as done:
                        reply = done.value
                        break
                    yield _sse("token", {"text": prose})
                payload = _persist_platform_turn(s, study_id, researcher, reply)
                yield _sse("done", payload)
            except design_assistant.ModelUnavailable as exc:
                # Keep the researcher's own turn so they never have to retype it, and
                # close the stream with a normal `done` frame carrying the holding turn
                # - an `error` frame would leave the thread looking broken rather than
                # waiting.
                #
                # Persisted, same as the blocking endpoint's branch just above
                # and for the same reason: unpersisted, a reload kept the
                # researcher's question on screen and silently dropped the one
                # sentence explaining why nothing answered it.
                log.info("conversation turn unanswered: %s", exc)
                payload = _persist_platform_turn(
                    s, study_id, researcher, design_assistant.holding_turn(str(exc))
                )
                yield _sse("done", payload)
            except Exception as exc:
                log.exception("streaming conversation turn failed")
                s.rollback()
                yield _sse("error", {"detail": str(exc)})

        return StreamingResponse(
            frames(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-store",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get(
        "/studies/{study_id}/conversation",
        dependencies=[Depends(deps.authz["require_project_for_study"]("view"))],
    )
    def get_conversation(study_id: str, s: Session = Depends(deps.db)) -> dict:
        turns = s.scalars(
            select(ConversationTurn)
            .where(ConversationTurn.study_id == study_id)
            .order_by(ConversationTurn.seq)
        ).all()
        moves_by_turn: dict[str, list] = defaultdict(list)
        for mv in s.scalars(
            select(DesignMoveRow)
            .where(DesignMoveRow.study_id == study_id)
            .order_by(DesignMoveRow.seq)
        ):
            wire = {
                "moveId": mv.id,
                "kind": mv.kind,
                "target": mv.target,
                "proposal": mv.proposal,
                "patch": mv.patch,
                "grounding": mv.grounding,
                "status": mv.status,
                "decidedBy": mv.decided_by,
                "decidedAt": mv.decided_at,
            }
            if mv.kind == "merge-templates" and isinstance(mv.patch, dict):
                wire["mergeData"] = {
                    "templateIds": list(mv.patch.get("templateIds") or []),
                    "reason": str(mv.patch.get("reason") or ""),
                }
            moves_by_turn[mv.turn_id].append(wire)

        study_refs = set(
            s.scalars(select(Paper.paper_ref).where(Paper.study_id == study_id))
        )

        def current_recommendations(recommendations: list | None) -> list:
            return [
                {
                    **recommendation,
                    "inStudy": recommendation.get("ref") in study_refs,
                }
                for recommendation in (recommendations or [])
            ]

        return {
            "studyId": study_id,
            "turns": [
                {
                    "turnId": t.id,
                    "seq": t.seq,
                    "role": t.role,
                    "author": t.author,
                    "text": "" if t.redacted else t.text,
                    "redacted": bool(t.redacted),
                    "moves": moves_by_turn.get(t.id, []),
                    "recommendations": current_recommendations(t.recommendations),
                    "source": t.source,
                }
                for t in turns
            ],
            # Recomputed the same way a fresh turn computes it
            # (`design_assistant.turn_stance`)  -  otherwise a reload blanks the line
            # the UI keeps this for, until the next turn is sent.
            "understanding": elicitation.understanding_summary(
                elicitation.assess_understanding(
                    design_assistant.researcher_texts(s, study_id)
                )
            ),
        }

    @app.post(
        "/studies/{study_id}/conversation/moves/{move_id}/decision",
        dependencies=[Depends(deps.authz["require_project_for_study"]("contribute"))],
    )
    def decide_move(
        study_id: str, move_id: str, body: MoveDecisionIn, s: Session = Depends(deps.db)
    ) -> dict:
        """
        Accept, reject, or reopen ("proposed") a design move (FR-CONV-1.2)  -  undo is
        just deciding "proposed" again.
        """
        if body.status not in ("accepted", "rejected", "proposed"):
            raise HTTPException(
                400, "status must be 'accepted', 'rejected', or 'proposed'"
            )
        mv = s.get(DesignMoveRow, move_id)
        if mv is None or mv.study_id != study_id:
            raise HTTPException(404, "design move not found")
        mv.status = body.status
        if body.status == "proposed":
            mv.decided_by = ""
            mv.decided_at = ""
        else:
            mv.decided_by = body.decidedBy
            mv.decided_at = deps.now()

        # It did not, and the omission hid behind three surfaces that each looked right
        # on their own: the move card showed its citations, the compiled provenance
        # recorded them, and the library assistant answered questions about them (it
        # searches a cross-study index), while the library's own list and citation graph
        # - both scoped to `study_id` - had never been told the papers existed.
        adopted: list[str] = []
        if body.status == "accepted":
            for g in mv.grounding or []:
                ref = g.get("ref") if isinstance(g, dict) else None
                if not ref:
                    continue
                got = deps.adopt_corpus_paper(
                    s,
                    study_id,
                    str(ref),
                    added_via="grounding",
                    match_reason=str(g.get("why") or g.get("matchReason") or ""),
                )
                if got is not None:
                    adopted.append(got)
        s.commit()
        return {"moveId": move_id, "status": mv.status, "papersAdded": adopted}

    @app.post(
        "/studies/{study_id}/quick-protocol",
        dependencies=[Depends(deps.authz["require_project_for_study"]("contribute"))],
    )
    def create_quick_protocol(
        study_id: str, body: QuickProtocolIn, s: Session = Depends(deps.db)
    ) -> dict:
        """Validate a bounded developer-study checklist and compile it in one pass."""
        if any(
            not value.strip()
            for value in (
                body.title,
                body.participantDescription,
                body.taskDescription,
            )
        ):
            raise HTTPException(422, "the study brief fields cannot be blank")
        questions = [question.strip() for question in body.researchQuestions]
        if any(not 10 <= len(question) <= 500 for question in questions):
            raise HTTPException(
                422, "each research question needs 10 to 500 characters"
            )
        if len({question.casefold() for question in questions}) != len(questions):
            raise HTTPException(422, "research questions must be different")
        conditions = [condition.strip() for condition in body.conditions]
        if any(not condition or len(condition) > 80 for condition in conditions):
            raise HTTPException(
                422, "each condition needs a short, non-empty name (80 characters max)"
            )
        if len({condition.casefold() for condition in conditions}) != 2:
            raise HTTPException(422, "the two conditions must be different")
        if body.design == "within-subjects" and not body.counterbalanced:
            raise HTTPException(
                422,
                "within-subjects studies in this quick path must counterbalance "
                "condition order",
            )
        if body.design == "between-subjects" and body.plannedParticipants < 6:
            raise HTTPException(
                422,
                "between-subjects studies need at least 6 planned participants",
            )

        scope = elicitation.classify_scope(
            [*questions, body.taskDescription, body.participantDescription]
        )
        if scope != "supported":
            raise HTTPException(
                422,
                "Quick protocol is limited to task-based human–AI software-development "
                "studies that run in VS Code. Use the chat for a supported idea that "
                "needs shaping, or choose a different tool for exams, classroom, "
                "clinical, marketing, or general survey studies.",
            )

        measures = [measure.strip() for measure in body.measures]
        if any(not measure or len(measure) > 100 for measure in measures):
            raise HTTPException(
                422,
                "each outcome needs a short, non-empty description "
                "(100 characters max)",
            )
        if len({measure.casefold() for measure in measures}) != len(measures):
            raise HTTPException(422, "selected outcomes must be different")

        existing = s.get(ProtocolDraftRow, study_id)
        base_yaml = existing.yaml if existing else ""
        current = compiler.compile_moves(
            deps.conversation_moves(s, study_id), base_yaml=base_yaml
        ).draft
        typed_mode = (
            body.typedMeasures
            or bool(body.measureIds)
            or bool(body.existingMeasureIds)
            or current.get("protocolVersion") == 6
        )
        preserved = {
            row["id"]: row
            for row in current.get("measures", [])
            if isinstance(row, dict)
        }
        if typed_mode:
            if len(body.measureIds) + len(body.existingMeasureIds) != len(
                measures
            ) or len(set(body.measureIds)) != len(body.measureIds):
                raise HTTPException(
                    422, "Choose a supported mapping for every outcome before saving."
                )
            if len(set(body.existingMeasureIds)) != len(body.existingMeasureIds) or any(
                ident not in preserved for ident in body.existingMeasureIds
            ):
                raise HTTPException(
                    422,
                    "An existing measurement changed; reload the draft before editing.",
                )
            for ident in body.measureIds:
                entry = catalog_entry(ident)
                if entry is None or (
                    entry["id"] != "S10"
                    and not entry["recipeByDesign"].get(body.design)
                ):
                    raise HTTPException(
                        422,
                        "A selected outcome has no supported analysis for this design.",
                    )
            for ident in body.existingMeasureIds:
                recipe = preserved[ident]["analysisRecipe"]
                if (
                    recipe == "paired-nonparametric"
                    and body.design != "within-subjects"
                ) or (
                    recipe in {"two-group-nonparametric", "two-proportion"}
                    and body.design != "between-subjects"
                ):
                    raise HTTPException(
                        422,
                        "The existing measurement analysis is incompatible "
                        "with this design; choose its analysis in Setup.",
                    )

        template_id = (
            "within-subjects-crossover-v1"
            if body.design == "within-subjects"
            else "two-group-rct-v1"
        )
        parameters = {
            "studyId": study_id,
            "title": body.title.strip(),
            "researchQuestion": questions[0],
            "conditions": conditions,
            "participantPlan": body.plannedParticipants,
            "sessionMinutes": body.sessionMinutes,
            "taskDescription": body.taskDescription.strip(),
        }
        move_specs = [
            {
                "kind": "choose-template",
                "target": "design",
                "proposal": (
                    "Use a counterbalanced within-subjects comparison."
                    if body.design == "within-subjects"
                    else "Use a two-group between-subjects comparison."
                ),
                "patch": {
                    "templateId": template_id,
                    "parameters": parameters,
                    "manual": True,
                    "researchQuestions": questions,
                    "typedMeasures": typed_mode,
                    "baseProtocol": current
                    if current.get("protocolVersion") == 6
                    else None,
                    "design": body.design,
                    "counterbalanced": body.counterbalanced,
                },
            },
            *(
                {
                    "kind": "add-rq",
                    "target": "researchQuestions[]",
                    "proposal": question,
                    "patch": {
                        "section": "researchQuestions",
                        "op": "append",
                        "value": question,
                    },
                }
                for question in questions[1:]
            ),
            {
                "kind": "set-field",
                "target": "participants.description",
                "proposal": f"Recruit {body.participantDescription.strip()}.",
                "patch": {
                    "op": "set-field",
                    "path": ["participants", "description"],
                    "value": body.participantDescription.strip(),
                },
            },
            {
                "kind": "add-measure",
                "target": "measures[]",
                "proposal": "Measure " + ", ".join(measures) + ".",
                "patch": {
                    "section": "measures",
                    "op": "set" if typed_mode else "append",
                    "value": [
                        *[preserved[ident] for ident in body.existingMeasureIds],
                        *[{"catalogId": ident} for ident in body.measureIds],
                    ]
                    if typed_mode
                    else measures,
                },
            },
            {
                "kind": "declare-task",
                "target": "tasks[]",
                "proposal": body.taskDescription.strip().rstrip(".") + ".",
                "patch": {
                    "id": "primary-task",
                    "title": body.taskDescription.strip()[:80],
                    "description": body.taskDescription.strip(),
                    "minutes": body.sessionMinutes,
                    "conditions": conditions,
                },
            },
        ]

        kept_recipes = {
            rq.get("text"): entry.get("recipes", [])
            for rq in current.get("researchQuestions") or []
            for entry in current.get("analysisPlan") or []
            if entry.get("rq") == rq.get("id")
        }
        preview = compiler.compile_moves(
            [{**spec, "status": "accepted"} for spec in move_specs]
        ).draft
        move_specs += [
            {
                "kind": "prescribe-statistics",
                "target": "analysisPlan",
                "proposal": f"Keep the {preserved[ident]['analysisRecipe']} analysis.",
                "patch": {"recipeId": preserved[ident]["analysisRecipe"], "rq": "RQ-1"},
            }
            for ident in body.existingMeasureIds
        ]
        move_specs += [
            {
                "kind": "prescribe-statistics",
                "target": "analysisPlan",
                "proposal": f"Keep the {recipe} analysis for {rq['id']}.",
                "patch": {"recipeId": recipe, "rq": rq["id"]},
            }
            for rq in preview.get("researchQuestions") or []
            for recipe in kept_recipes.get(rq.get("text"), [])
        ]

        researcher = ConversationTurn(
            id=secrets.token_hex(8),
            study_id=study_id,
            seq=deps.conversation_seq(s, study_id),
            role="researcher",
            author="Researcher",
            text=(f"Protocol details entered manually: {questions[0]}"),
            retrieved_refs=[],
            created_at=deps.now(),
        )
        s.add(researcher)
        s.flush()
        platform = ConversationTurn(
            id=secrets.token_hex(8),
            study_id=study_id,
            seq=researcher.seq + 1,
            role="platform",
            author="Platform",
            text=(
                "The checklist is complete. I instantiated the matching study "
                "template and ran the protocol compiler. Review the verified draft "
                "before applying it."
            ),
            retrieved_refs=[],
            recommendations=[],
            created_at=deps.now(),
            source="scripted",
        )
        s.add(platform)
        s.flush()
        moves = []
        for index, spec in enumerate(move_specs, start=1):
            move_id = f"{platform.id}:quick-{index}"
            move = {
                "moveId": move_id,
                **spec,
                "grounding": [],
                "status": "accepted",
            }
            moves.append(move)
            s.add(
                DesignMoveRow(
                    id=move_id,
                    study_id=study_id,
                    turn_id=platform.id,
                    seq=index,
                    kind=spec["kind"],
                    target=spec["target"],
                    proposal=spec["proposal"],
                    patch=spec["patch"],
                    grounding=[],
                    status="accepted",
                    decided_by="Researcher",
                    decided_at=deps.now(),
                )
            )

        s.flush()
        all_moves = deps.conversation_moves(s, study_id)
        result = compiler.compile_moves(all_moves, base_yaml=base_yaml)
        comp = Compilation(
            id=secrets.token_hex(8),
            study_id=study_id,
            base_sha256=sha256(base_yaml.encode()).hexdigest(),
            draft_yaml=result.yaml,
            diff=result.diff,
            move_ids=[m["moveId"] for m in all_moves if m["status"] == "accepted"],
            errors=result.errors,
            unresolved=result.unresolved,
            valid=int(result.valid),
            created_at=deps.now(),
        )
        s.add(comp)
        platform.text = (
            "The checklist is complete and the compiler "
            + ("verified the draft." if result.valid else "found issues to resolve.")
            + " Review the result before applying it."
        )
        s.commit()
        return {
            "compilationId": comp.id,
            "valid": result.valid,
            "errors": result.errors,
            "unresolved": result.unresolved,
            "warnings": result.warnings,
            "diff": result.diff,
            "yaml": result.yaml,
            "protocol": result.draft,
            "templateId": result.template_id,
            "selectedMeasures": measures,
            "participantDescription": body.participantDescription.strip(),
        }

    @app.post(
        "/studies/{study_id}/conversation/compile",
        dependencies=[Depends(deps.authz["require_project_for_study"]("contribute"))],
    )
    def compile_conversation(
        study_id: str, body: CompileIn, s: Session = Depends(deps.db)
    ) -> dict:
        """Compile the study's accepted moves into a protocol draft diff (FR-CONV-3)."""
        moves = deps.conversation_moves(s, study_id)
        base_yaml = body.baseYaml
        if base_yaml is None:
            existing = s.get(ProtocolDraftRow, study_id)
            base_yaml = existing.yaml if existing else ""
        result = compiler.compile_moves(moves, base_yaml=base_yaml)
        comp = Compilation(
            id=secrets.token_hex(8),
            study_id=study_id,
            base_sha256=sha256(base_yaml.encode()).hexdigest(),
            draft_yaml=result.yaml,
            diff=result.diff,
            move_ids=[m["moveId"] for m in moves if m["status"] == "accepted"],
            errors=result.errors,
            unresolved=result.unresolved,
            valid=int(result.valid),
            created_at=deps.now(),
        )
        s.add(comp)
        s.commit()
        return {
            "compilationId": comp.id,
            "valid": result.valid,
            "errors": result.errors,
            "unresolved": result.unresolved,
            "warnings": result.warnings,
            "diff": result.diff,
            "yaml": result.yaml,
            "protocol": result.draft,
            "templateId": result.template_id,
        }

    @app.post(
        "/studies/{study_id}/conversation/approve",
        dependencies=[Depends(deps.authz["require_project_for_study"]("apply_draft"))],
    )
    def approve_compilation(
        study_id: str,
        body: ApproveIn,
        membership: Membership = Depends(
            deps.authz["require_project_for_study"]("apply_draft")
        ),
        s: Session = Depends(deps.db),
    ) -> dict:
        """Apply a compiled diff  -  the audited step (FR-CONV-3.3/F3.3)."""
        comp = s.get(Compilation, body.compilationId)
        if comp is None or comp.study_id != study_id:
            raise HTTPException(404, "compilation not found")
        if not comp.valid:
            raise HTTPException(
                409,
                "this draft did not pass validation and cannot be applied. "
                f"Resolve: {comp.errors or comp.unresolved}",
            )

        current_draft = s.get(ProtocolDraftRow, study_id)
        base_yaml = current_draft.yaml if current_draft else ""
        if sha256(base_yaml.encode()).hexdigest() != comp.base_sha256:
            raise HTTPException(
                409,
                "this compilation is stale because its base draft changed. "
                "Recompile before applying it.",
            )
        moves = deps.conversation_moves(s, study_id)
        verified = compiler.compile_moves(moves, base_yaml=base_yaml)
        accepted_move_ids = [m["moveId"] for m in moves if m["status"] == "accepted"]
        if (
            not verified.valid
            or verified.yaml != comp.draft_yaml
            or accepted_move_ids != comp.move_ids
        ):
            raise HTTPException(
                409,
                "this compilation is stale because the accepted moves changed. "
                "Recompile before applying it.",
            )

        s.add(
            ApprovalEvent(
                study_id=study_id,
                compilation_id=comp.id,
                approved_by=body.approvedBy,
                role=str(membership.role),
                at=deps.now(),
            )
        )
        comp.applied_at = deps.now()
        draft = s.get(ProtocolDraftRow, study_id)
        if draft is None:
            draft = ProtocolDraftRow(study_id=study_id)
            s.add(draft)
        draft.yaml = comp.draft_yaml
        draft.compilation_id = comp.id
        draft.updated_at = deps.now()
        s.commit()
        return {"applied": True, "compilationId": comp.id}

    @app.get(
        "/studies/{study_id}/conversation/export",
        dependencies=[Depends(deps.authz["require_project_for_study"]("view"))],
    )
    def export_elicitation(study_id: str, s: Session = Depends(deps.db)) -> dict:
        """
        The elicitation record (FR-CONV-6): the full chain from idea to specification  -
        turns, moves + grounding, compilations, approvals, and the current draft  -
        captured by construction, not reconstructed.
        """
        conv = get_conversation(study_id, s)
        # Abstracts remain available in the live conversation, but are not
        # redistributed with its downloadable provenance record or kit.
        for turn in conv["turns"]:
            for recommendation in turn["recommendations"]:
                recommendation.pop("abstract", None)
        compilations = [
            {
                "compilationId": c.id,
                "valid": bool(c.valid),
                "moveIds": c.move_ids,
                "errors": c.errors,
                "appliedAt": c.applied_at or None,
            }
            for c in s.scalars(
                select(Compilation)
                .where(Compilation.study_id == study_id)
                .order_by(Compilation.created_at)
            )
        ]
        approvals = [
            {
                "compilationId": a.compilation_id,
                "approvedBy": a.approved_by,
                "role": a.role,
                "at": a.at,
            }
            for a in s.scalars(
                select(ApprovalEvent).where(ApprovalEvent.study_id == study_id)
            )
        ]
        draft = s.get(ProtocolDraftRow, study_id)
        return {
            "studyId": study_id,
            "turns": conv["turns"],
            "compilations": compilations,
            "approvals": approvals,
            "currentDraft": draft.yaml if draft else "",
            "evidenceMaps": evidence_export(s, study_id),
        }

    return export_elicitation
