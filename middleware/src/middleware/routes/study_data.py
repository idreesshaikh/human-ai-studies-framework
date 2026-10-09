"""Study data API routes."""

import csv
import io
import json
import logging
import tempfile
from collections import defaultdict
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
)
from fastapi.responses import (
    PlainTextResponse,
    Response,
)
from protocol.assignment import assign, tasks_of
from protocol.capture import (
    producer_capabilities,
    required_producers,
)
from protocol.errors import ProtocolError
from protocol.export import build_kit
from protocol.versioning import content_hash
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from middleware import (
    design_assistant,
    template_registry,
)
from middleware.db import (
    EnrollmentToken,
    Event,
    MetricRow,
    RecipeRun,
    SessionBlock,
    StoredFile,
)
from middleware.evidence_mapping import evidence_export
from middleware.route_helpers import (
    _session_gap_facts,
)
from middleware.routes.deps import ApiDeps
from middleware.schemas import (
    RecipeRunIn,
)

log = logging.getLogger("middleware.app")


def register(app: FastAPI, deps: ApiDeps):
    @app.get(
        "/studies/{study_id}/dataset",
        dependencies=[Depends(deps.authz["require_project_for_study"]("view"))],
    )
    def dataset(
        study_id: str,
        format: str = "json",
        includeSynthetic: bool = False,
        s: Session = Depends(deps.db),
    ):
        """The joined one-timeline export all legs share (FR-ING-4)."""
        rows = deps.joined_rows(s, study_id, includeSynthetic)
        if format == "json":
            return {"studyId": study_id, "rows": rows}
        if format == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            header = [
                "source",
                "ts",
                "sessionId",
                "participantId",
                "condition",
                "taskId",
                "schemaVersion",
                "type",
                "seq",
                "flags",
                "payload",
            ]
            writer.writerow(header)
            for r in rows:
                writer.writerow(
                    [
                        r[k] if k not in ("flags", "payload") else json.dumps(r[k])
                        for k in header
                    ]
                )
            return PlainTextResponse(
                buf.getvalue(),
                media_type="text/csv",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="{study_id}-dataset.csv"'
                    )
                },
            )
        raise HTTPException(400, "format must be 'json' or 'csv'")

    def _design_card(s, study_id, rows=None):
        from analysis.recipes.control_arm_audit import audit_sessions
        from protocol.design_card import design_card

        from middleware.planner_routes import (
            audit_records,
            decision_records,
            latest_plan,
        )

        proto = deps.resolve_study_protocol(s, study_id)
        if proto is None:
            return None
        record = latest_plan(s, study_id)
        plan = (
            {
                **record.result,
                "protocolHash": record.protocol_hash,
                "protocolVersion": record.protocol_version,
                "stale": record.protocol_hash != content_hash(proto),
            }
            if record
            else None
        )
        decisions = decision_records(s, study_id)
        data = rows if rows is not None else deps.joined_rows(s, study_id)
        return design_card(
            proto,
            plan=plan,
            decisions=decisions,
            rows=data,
            audit={
                **audit_sessions(data, proto.get("controlConditions", []), decisions),
                "records": audit_records(s, study_id),
            },
        )

    @app.get(
        "/studies/{study_id}/design-card",
        dependencies=[Depends(deps.authz["require_project_for_study"]("view"))],
    )
    def download_design_card(
        study_id: str, format: str = "json", s: Session = Depends(deps.db)
    ):
        from protocol.design_card import design_card_markdown

        card = _design_card(s, study_id)
        if card is None:
            raise HTTPException(409, "No recorded protocol")
        if format == "markdown":
            return PlainTextResponse(
                design_card_markdown(card),
                headers={
                    "Content-Disposition": f"attachment; "
                    f'filename="{study_id}-design-card.md"'
                },
            )
        if format != "json":
            raise HTTPException(422, "format must be json or markdown")
        return card

    @app.get(
        "/studies/{study_id}/data-bundle",
        dependencies=[Depends(deps.authz["require_project_for_study"]("view"))],
    )
    def download_data_bundle(
        study_id: str,
        includeSynthetic: bool = False,
        s: Session = Depends(deps.db),
    ):
        """
        The collected data as a zip of tidy CSVs, the joined timeline, a data
        dictionary and uploaded files, for the researcher's own postprocessing.
        Dry-run (synthetic) rows are left out unless asked for.
        """
        from analysis.dataset import Dataset
        from analysis.notebook import data_dictionary_markdown

        from middleware.export_bundle import build_bundle, is_synthetic

        rows = deps.joined_rows(s, study_id, include_synthetic=includeSynthetic)
        if not includeSynthetic:
            rows = [r for r in rows if not is_synthetic(r)]
        ds = Dataset(rows=rows, study_id=study_id)
        dictionary_md = f"# {study_id}: data dictionary\n\n" + data_dictionary_markdown(
            ds
        )
        files = []
        for f in s.scalars(
            select(StoredFile)
            .where(StoredFile.study_id == study_id)
            .order_by(StoredFile.id)
        ):
            path = Path(f.stored_path)
            if path.is_file():
                files.append((f"{f.id}-{f.filename}", path.read_bytes()))
        evidence = evidence_export(s, study_id)
        if evidence:
            files.append(
                ("evidence-maps.json", json.dumps(evidence, indent=2).encode())
            )
            files.append(
                (
                    "design-decisions.json",
                    json.dumps(deps.conversation_moves(s, study_id), indent=2).encode(),
                )
            )
        return Response(
            content=build_bundle(
                study_id,
                rows,
                dictionary_md,
                files,
                protocol=deps.resolve_study_protocol(s, study_id),
                include_synthetic=includeSynthetic,
                design_card_record=_design_card(s, study_id, rows),
            ),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{study_id}-data.zip"',
                "Cache-Control": "no-store",
            },
        )

    @app.get(
        "/studies/{study_id}/protocol",
        dependencies=[Depends(deps.authz["require_project_for_study"]("view"))],
    )
    def study_protocol(study_id: str, s: Session = Depends(deps.db)) -> dict:
        """
        Protocol summary for the overview card (FR-DASH-1) and the traceability chips
        (FR-DASH-6): RQ -> planned recipes comes verbatim from the protocol's analysis
        plan.
        """

        proto = deps.resolve_study_protocol(s, study_id)
        if proto is None:
            raise HTTPException(404, f"no protocol for study {study_id!r}")
        recipes_by_rq = {
            p["rq"]: list(p.get("recipes", [])) for p in proto.get("analysisPlan", [])
        }
        return {
            "studyId": proto["study"]["id"],
            "protocolVersion": proto.get("protocolVersion"),
            "title": proto["study"].get("title", ""),
            "researchers": proto["study"].get("researchers", []),
            "ethicsRef": proto["study"].get("ethicsRef", ""),
            "conditions": list(proto.get("conditions", [])),
            "participants": proto.get("participants", {}),
            "session": proto.get("session", {}),
            "researchQuestions": [
                {
                    "id": rq["id"],
                    "text": rq["text"],
                    "recipes": recipes_by_rq.get(rq["id"], []),
                }
                for rq in proto.get("researchQuestions", [])
            ],
            "phases": [
                {"name": p["name"], "gates": list(p.get("gates", []))}
                for p in proto["phases"]
            ],
            # Readers need the recorded protocol without invoking compilation,
            # which requires contribution permission.
            "document": proto,
        }

    @app.get(
        "/studies/{study_id}/status",
        dependencies=[Depends(deps.authz["require_project_for_study"]("view"))],
    )
    def study_status(
        study_id: str, includeSynthetic: bool = False, s: Session = Depends(deps.db)
    ) -> dict:
        """One factual status document (FR-DASH-7)."""

        proto = deps.resolve_study_protocol(s, study_id)
        if proto is None:
            raise HTTPException(404, f"no protocol for study {study_id!r}")

        # Every read below is scoped to this study's sessions; without it the
        # status document described the whole database (see `_session_scope`).
        in_this_study = deps.session_scope(study_id, includeSynthetic)

        seqs_by_session: dict[str, dict[str, list[int]]] = defaultdict(
            lambda: defaultdict(list)
        )
        source_counts_by_session: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        for sid, src, seq in s.execute(
            select(Event.session_id, Event.source, Event.seq).where(
                in_this_study(Event.session_id)
            )
        ):
            seqs_by_session[sid][src].append(seq)
            source_counts_by_session[sid][src] += 1

        flag_kinds: dict[str, set[str]] = defaultdict(set)
        flagged_events: dict[str, int] = defaultdict(int)
        for sid, flags in s.execute(
            select(Event.session_id, Event.flags).where(
                func.json_array_length(Event.flags) > 0,
                in_this_study(Event.session_id),
            )
        ):
            flagged_events[sid] += 1
            flag_kinds[sid].update(flags)

        sessions = {}
        for sid, pid, cond, task_id, n, last_recv in s.execute(
            select(
                Event.session_id,
                Event.participant_id,
                Event.condition,
                Event.task_id,
                func.count(),
                func.max(Event.received_at),
            )
            .where(in_this_study(Event.session_id))
            .group_by(
                Event.session_id,
                Event.participant_id,
                Event.condition,
                Event.task_id,
            )
        ):
            agg = _session_gap_facts(seqs_by_session[sid])
            sessions[sid] = {
                "sessionId": sid,
                "participantId": pid,
                "condition": cond,
                "taskId": task_id,
                "events": n,
                "metricRows": 0,
                "sourceCounts": dict(source_counts_by_session[sid]),
                "flaggedEvents": flagged_events.get(sid, 0),
                "flagKinds": sorted(flag_kinds.get(sid, ())),
                "gapCount": agg["gapCount"],
                "missingEvents": agg["missingEvents"],
                "complete": agg["complete"],
                "lastReceivedAt": last_recv,
            }
        for sid, pid, cond, task_id, n in s.execute(
            select(
                MetricRow.session_id,
                MetricRow.participant_id,
                MetricRow.condition,
                MetricRow.task_id,
                func.count(),
            )
            .where(in_this_study(MetricRow.session_id))
            .group_by(
                MetricRow.session_id,
                MetricRow.participant_id,
                MetricRow.condition,
                MetricRow.task_id,
            )
        ):
            entry = sessions.setdefault(
                sid,
                {
                    "sessionId": sid,
                    "participantId": pid,
                    "condition": cond,
                    "events": 0,
                    "metricRows": 0,
                    "sourceCounts": {},
                    "flaggedEvents": 0,
                    "flagKinds": [],
                    "gapCount": 0,
                    "missingEvents": 0,
                    "complete": False,
                    "lastReceivedAt": None,
                },
            )
            entry["metricRows"] = n
            entry["taskId"] = entry.get("taskId") or task_id
            entry["sourceCounts"]["metrics"] = n

        participants = proto.get("participants", {})
        within = participants.get("design") == "within-subjects"
        conditions = list(proto.get("conditions", []))
        recipes_by_rq = {
            p["rq"]: list(p.get("recipes", [])) for p in proto.get("analysisPlan", [])
        }
        ran = set(
            s.scalars(
                select(RecipeRun.recipe_id).where(
                    RecipeRun.study_id == proto["study"]["id"], RecipeRun.status == "ok"
                )
            )
        )
        return {
            "studyId": proto["study"]["id"],
            "generatedAt": deps.now(),
            "conditions": conditions,
            "plannedParticipants": int(participants.get("planned", 0)),
            "plannedSessionsPerParticipant": len(conditions) if within else 1,
            "sessions": sorted(sessions.values(), key=lambda e: e["sessionId"]),
            "researchQuestions": [
                {
                    "id": rq["id"],
                    "recipes": recipes_by_rq.get(rq["id"], []),
                    "recipeRuns": [
                        r for r in recipes_by_rq.get(rq["id"], []) if r in ran
                    ],
                }
                for rq in proto.get("researchQuestions", [])
            ],
            "producers": producer_capabilities(proto),
            "requiredProducers": required_producers(proto),
        }

    @app.get(
        "/studies/{study_id}/live",
        dependencies=[Depends(deps.authz["require_project_for_study"]("view"))],
    )
    def live_sessions(
        study_id: str,
        windowSeconds: int = 300,
        bucketSeconds: int = 10,
        includeSynthetic: bool = False,
        s: Session = Depends(deps.db),
    ) -> dict:
        """
        Sessions with ingests inside the window (FR-DASH-3), with per- bucket receive
        counts for the event-rate sparkline.
        """

        now_dt = deps.clock()
        cutoff = (now_dt - timedelta(seconds=windowSeconds)).astimezone(UTC)
        cutoff_s = cutoff.isoformat(timespec="milliseconds")
        buckets = max(1, windowSeconds // bucketSeconds)

        recent = s.scalars(
            select(Event)
            .where(
                Event.received_at >= cutoff_s,
                deps.session_scope(study_id, includeSynthetic)(Event.session_id),
            )
            .order_by(Event.received_at, Event.seq)
        ).all()
        by_session: dict[str, list[Event]] = defaultdict(list)
        for e in recent:
            by_session[e.session_id].append(e)

        protocol = deps.resolve_study_protocol(s, study_id)
        task_titles = {
            t.get("id"): t.get("title", "")
            for t in (tasks_of(protocol) if protocol else [])
        }
        session_blocks = {
            b.session_id: b
            for b in s.scalars(
                select(SessionBlock).where(SessionBlock.session_id.in_(set(by_session)))
            )
        }
        blocks_total: dict[str, int] = {}
        if protocol:
            for row in s.scalars(
                select(EnrollmentToken).where(EnrollmentToken.study_id == study_id)
            ):
                with suppress(ProtocolError):
                    blocks_total[row.participant_id] = len(
                        assign(protocol, row.participant_index or 0)
                    )

        out = []
        for sid, events in sorted(by_session.items()):
            block = session_blocks.get(sid)
            rate = [0] * buckets
            for e in events:
                age = (now_dt - datetime.fromisoformat(e.received_at)).total_seconds()
                # Clock skew must not produce an out-of-range bucket index.
                offset = min(max(int(age // bucketSeconds), 0), buckets - 1)
                idx = buckets - 1 - offset
                rate[idx] += 1
            last = events[-1]
            per_source: dict[str, list[int]] = defaultdict(list)
            for src, seq in s.execute(
                select(Event.source, Event.seq).where(Event.session_id == sid)
            ):
                per_source[src].append(seq)
            agg = _session_gap_facts(per_source)
            out.append(
                {
                    "sessionId": sid,
                    "participantId": last.participant_id,
                    "condition": last.condition,
                    "taskId": last.task_id,
                    "taskTitle": (task_titles.get(last.task_id) or ""),
                    "blockIndex": (block.block_index if block else None),
                    "blocksTotal": blocks_total.get(last.participant_id),
                    "eventsInWindow": len(events),
                    "lastEventType": last.type,
                    "lastReceivedAt": last.received_at,
                    "lastSeq": last.seq,
                    "rate": rate,
                    "gapCount": agg["gapCount"],
                    "missingEvents": agg["missingEvents"],
                }
            )
        return {
            "now": deps.now(),
            "windowSeconds": windowSeconds,
            "bucketSeconds": bucketSeconds,
            "sessions": out,
        }

    @app.post(
        "/studies/{study_id}/recipe-runs",
        dependencies=[Depends(deps.authz["require_project_for_study"]("run_recipe"))],
    )
    def add_recipe_run(
        study_id: str, run: RecipeRunIn, s: Session = Depends(deps.db)
    ) -> dict:
        """Record one analysis-recipe run."""

        row = RecipeRun(
            study_id=study_id,
            recipe_id=run.recipeId,
            answers=run.answers,
            status=run.status,
            note=run.note,
            at=deps.now(),
        )
        s.add(row)
        s.flush()
        return {"id": row.id}

    @app.get(
        "/studies/{study_id}/recipe-runs",
        dependencies=[Depends(deps.authz["require_project_for_study"]("view"))],
    )
    def list_recipe_runs(study_id: str, s: Session = Depends(deps.db)) -> list[dict]:

        return [
            {
                "id": r.id,
                "recipeId": r.recipe_id,
                "answers": r.answers,
                "status": r.status,
                "note": r.note,
                "at": r.at,
            }
            for r in s.scalars(
                select(RecipeRun)
                .where(RecipeRun.study_id == study_id)
                .order_by(RecipeRun.id)
            )
        ]

    @app.get(
        "/studies/{study_id}/power",
        dependencies=[Depends(deps.authz["require_project_for_study"]("view"))],
    )
    def study_power_curve(
        study_id: str,
        alpha: float = 0.05,
        maxN: int = 120,
        powerTarget: float = 0.8,
        effectSizes: str = "0.2,0.5,0.8",
        s: Session = Depends(deps.db),
    ) -> dict:
        """
        The power/sensitivity curve for the study's planned comparison (P2-2): exact
        two-sample t-test power (non-central t, equal per-group n, two-sided) across
        per-group n, plus the first n reaching the target power, per effect size.
        """
        from analysis.planner import compatibility_curve

        try:
            sizes = [float(x.strip()) for x in effectSizes.split(",")]
            proto = deps.resolve_study_protocol(s, study_id)
            participants = (proto or {}).get("participants", {})
            design = participants.get("design", "between-subjects")
            recipes = {
                r
                for a in (proto or {}).get("analysisPlan", [])
                for r in a.get("recipes", [])
            }
            paired = design == "within-subjects"
            test = "paired-t" if paired else "two-sample-t"
            if proto and "mean-comparison" not in recipes:
                if not recipes & {
                    "typed-measures",
                    "paired-nonparametric" if paired else "two-group-nonparametric",
                }:
                    raise ValueError(
                        "No supported two-arm comparison recipe is recorded; no "
                        "sample size is reported"
                    )
                test = "wilcoxon" if paired else "mann-whitney"
            result = compatibility_curve(
                sizes,
                design=design,
                test=test,
                alpha=alpha,
                power_target=powerTarget,
                max_total_n=maxN,
                counterbalanced=participants.get("counterbalanced", True),
            )
            result.update(
                plannedParticipants=participants.get("planned"), design=design
            )
            if not proto:
                result["note"] = (
                    "No recorded comparison yet. This compatibility "
                    "estimate uses exploratory t-test assumptions; record a "
                    "protocol to plan against its actual analysis."
                )
            return result
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/analysis/prescriptions")
    def analysis_prescriptions(
        study_id: str | None = None, s: Session = Depends(deps.db)
    ) -> dict:
        """
        The deterministic, LLM-free prescription table (FR-TPL-6): design shape →
        the exact test, effect size, correction, and sample-size guidance, each with its
        rationale.

        Without ``study_id`` this is the full reference table  -  every shape PHOENIX
        knows how to prescribe, the browsable catalogue. With ``study_id``, it's
        filtered to the shape(s) that study's *own compiled protocol* actually calls
        for (read off ``analysisPlan[].recipes[]`` and mapped back through the same
        shape→recipe table the compiler used to pick them)  -  "what analysis your
        design calls for" was previously showing the full catalogue unconditionally
        on every study's Data tab, identical regardless of that study's actual
        design, which the researcher reads as bespoke guidance it isn't.
        """
        from analysis.prescribe import design_shapes, shapes_from_recipe_ids

        if study_id is None:
            rows = [
                design_assistant.recommend_prescription(shape)
                for shape in design_shapes()
            ]
            return {"prescriptions": [r for r in rows if r is not None]}

        protocol = deps.resolve_study_protocol(s, study_id)
        recipe_ids: set[str] = set()
        for entry in (protocol or {}).get("analysisPlan") or []:
            recipe_ids.update(entry.get("recipes") or [])
        matched_shapes = shapes_from_recipe_ids(recipe_ids)
        participants = (protocol or {}).get("participants", {})
        participant_design = (
            participants.get("design", "") if isinstance(participants, dict) else ""
        )
        # Domain-specific recipes answer the study's operational questions, while
        # the prescription catalogue is keyed by statistical design shape. The
        # protocol's participant design is the authoritative bridge when a
        # recipe has no generic shape mapping.
        if str(participant_design).lower() in {"within-subjects", "paired"}:
            matched_shapes.add("paired")
        rows = [
            design_assistant.recommend_prescription(shape)
            for shape in design_shapes()
            if shape in matched_shapes
        ]
        return {"prescriptions": [r for r in rows if r is not None]}

    @app.get(
        "/studies/{study_id}/replication-kit",
        dependencies=[Depends(deps.authz["require_project_for_study"]("view"))],
    )
    def export_replication_kit(study_id: str, s: Session = Depends(deps.db)):
        """The study's replication kit as a download (FR-PROT-7)."""
        proto = deps.resolve_study_protocol(s, study_id)
        if proto is None:
            raise HTTPException(
                409,
                f"study {study_id!r} has no compiled protocol yet. "
                "Approve a draft in the design conversation first",
            )
        payload = dataset(study_id, "json", s=s)
        repo_root = template_registry.REPO
        with tempfile.TemporaryDirectory() as td:
            staging = Path(td)
            protocol_path = staging / "protocol.yaml"
            protocol_path.write_text(
                yaml.safe_dump(proto, sort_keys=False, default_flow_style=False)
            )
            out = staging / f"{study_id}-replication-kit.tar.gz"
            try:
                build_kit(
                    protocol_path,
                    payload,
                    out,
                    repo_root=repo_root,
                    design_card_record=_design_card(s, study_id, payload["rows"]),
                    evidence_record=deps.export_elicitation(study_id, s)
                    if evidence_export(s, study_id)
                    else None,
                )
            except ProtocolError as exc:
                raise HTTPException(422, str(exc)) from exc
            archive = out.read_bytes()
        return Response(
            content=archive,
            media_type="application/gzip",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{study_id}-replication-kit.tar.gz"'
                ),
                "Cache-Control": "no-store",
            },
        )

    @app.get(
        "/studies/{study_id}/notebook",
        dependencies=[Depends(deps.authz["require_project_for_study"]("view"))],
    )
    def download_notebook(study_id: str, s: Session = Depends(deps.db)):
        """The starter notebook (.ipynb) + its data dictionary as a zip."""
        import zipfile

        from analysis.dataset import Dataset
        from analysis.notebook import build_notebook, data_dictionary_markdown

        proto = deps.resolve_study_protocol(s, study_id)
        if proto is None:
            raise HTTPException(
                409,
                f"study {study_id!r} has no compiled protocol yet. "
                "Approve a draft in the design conversation first",
            )
        payload = dataset(study_id, "json", s=s)
        ds = Dataset(rows=payload["rows"], study_id=study_id)
        notebook_json = json.dumps(build_notebook(proto, ds, study_id), indent=1)
        dictionary_md = f"# {study_id}: data dictionary\n\n" + data_dictionary_markdown(
            ds
        )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # `writestr(name, data)` stamps each member with the current clock,
            # which made two exports of the same study differ byte-for-byte.
            # A replication artifact should be stable: fix the DOS timestamp and
            # permissions while retaining normal deflate compression.
            epoch = (1980, 1, 1, 0, 0, 0)
            for name, content in (
                ("notebook.ipynb", notebook_json),
                ("data-dictionary.md", dictionary_md),
            ):
                info = zipfile.ZipInfo(name, date_time=epoch)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                zf.writestr(info, content)
        return Response(
            content=buf.getvalue(),
            media_type="application/zip",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{study_id}-notebook.zip"'
                ),
                "Cache-Control": "no-store",
            },
        )
