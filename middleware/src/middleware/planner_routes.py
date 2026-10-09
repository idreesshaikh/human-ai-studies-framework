"""Study-scoped planner, real-pilot update, audit decisions and lineage routes."""

from dataclasses import asdict

import numpy as np
from analysis.outcomes import participant_outcomes
from analysis.planner import PlanInput, estimate_variance, plan_study
from analysis.recipes.control_arm_audit import audit_sessions, calibration_report
from fastapi import Depends, Header, HTTPException
from protocol.measures import normalized_measures, shipped_instruments
from protocol.versioning import compare_designs, content_hash, provenance
from pydantic import BaseModel, ConfigDict, Field
from scipy import stats
from sqlalchemy import select

from middleware.db import SessionAnnotation, StudyAuditRecord, StudyPlan


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    design: str = "between-subjects"
    test: str = "mann-whitney"
    distribution: str = "normal"
    effect: float = Field(0.5, gt=0)
    sd: float = Field(1, gt=0)
    alpha: float = Field(0.05, gt=0, lt=1)
    target_power: float = Field(0.8, gt=0, lt=1)
    dropout: float = Field(0, ge=0, lt=1)
    covariate_correlation: float = Field(0, ge=-0.95, le=0.95)
    period_effect: float = 0
    order_effect: float = 0
    counterbalanced: bool = True
    planned_n: int = Field(40, ge=4, le=1000)
    max_n: int = Field(400, ge=4, le=1000)
    simulations: int = Field(1000, ge=200, le=10000)
    seed: int = Field(20261007, ge=0, le=2**32 - 1)
    ordinal_levels: int = Field(7, ge=2, le=11)
    measure_id: str | None = None

    def assumptions(self) -> PlanInput:
        return PlanInput(**self.model_dump(exclude={"measure_id"}))


class SessionTagRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pilot: bool | None = None
    decision: str | None = Field(None, pattern="^(include|exclude|undecided)$")
    reason: str = Field(min_length=1, max_length=4000)


class CalibrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    labels: dict[str, bool]
    source: str = Field(min_length=1, max_length=4000)


TEST_RECIPES = {
    "mann-whitney": {"two-group-nonparametric", "typed-measures"},
    "wilcoxon": {"paired-nonparametric", "typed-measures"},
    "two-sample-t": {"mean-comparison"},
    "paired-t": {"mean-comparison"},
}


def check_plan(body: PlanRequest, proto: dict) -> dict | None:
    body.assumptions().validate()
    if len(proto.get("conditions", [])) != 2:
        raise ValueError("Planning requires exactly two declared conditions")
    participants = proto.get("participants", {})
    if body.design != participants.get(
        "design"
    ) or body.counterbalanced != participants.get("counterbalanced"):
        raise ValueError("Design and counterbalancing must match the recorded protocol")
    recipes = {r for e in proto.get("analysisPlan", []) for r in e.get("recipes", [])}
    measure = next(
        (m for m in normalized_measures(proto) if m["id"] == body.measure_id), None
    )
    if body.measure_id and not measure:
        raise ValueError("Unknown measure_id")
    if body.test not in TEST_RECIPES or not recipes & TEST_RECIPES[body.test]:
        raise ValueError(
            "This test is not run by a supported recipe in the recorded analysisPlan"
        )
    if measure and (
        measure.get("legacy")
        or measure["analysisRecipe"] not in TEST_RECIPES[body.test]
    ):
        raise ValueError("The selected measure does not run this planned test")
    if proto.get("protocolVersion", 1) >= 6 and not measure:
        raise ValueError("Select a typed measure for protocol v6 planning")
    if body.covariate_correlation and not proto.get("covariate"):
        raise ValueError("ANCOVA requires a protocol-declared pre-task covariate")
    if (
        body.test.endswith("-t")
        and body.distribution == "log-normal"
        and (not measure or measure.get("analysisScale") != "log")
    ):
        raise ValueError(
            "Analytic log-normal planning requires a declared log "
            "transformation in the mean-comparison recipe"
        )
    if measure:
        if len(measure["fields"]) != 1:
            raise ValueError(
                "Power planning requires a single outcome field per measure"
            )
        if measure["analysisRecipe"] in {
            "paired-nonparametric",
            "two-group-nonparametric",
        } and measure["fields"] != ["task_outcome.firstGreenMs"]:
            raise ValueError(
                "This recipe currently analyses task_outcome.firstGreenMs only"
            )
        if (
            measure.get("analysisScale", "raw") == "log"
            and body.distribution != "log-normal"
        ):
            raise ValueError(
                "A log-scale outcome requires log-normal planning assumptions"
            )
    return measure


def saved_plan(s, study_id: str, proto: dict, inputs: dict, result: dict, now) -> dict:
    record = StudyPlan(
        study_id=study_id,
        protocol_version=proto["protocolVersion"],
        protocol_hash=content_hash(proto),
        protocol=proto,
        inputs=inputs,
        result=result,
        created_at=now(),
    )
    s.add(record)
    s.flush()
    return {
        **result,
        "planId": record.id,
        "createdAt": record.created_at,
        "protocol": provenance(proto),
        "measureId": inputs.get("measure_id"),
    }


def latest_plan(s, study_id: str) -> StudyPlan | None:
    return s.scalar(
        select(StudyPlan)
        .where(StudyPlan.study_id == study_id)
        .order_by(StudyPlan.id.desc())
        .limit(1)
    )


def decision_records(s, study_id: str) -> dict:
    return {
        a.session_id: {
            "pilot": bool(a.pilot),
            "decision": a.decision,
            "reason": a.reason,
            "decidedBy": a.decided_by,
            "updatedAt": a.updated_at,
        }
        for a in s.scalars(
            select(SessionAnnotation).where(SessionAnnotation.study_id == study_id)
        )
    }


def audit_records(s, study_id: str) -> list[dict]:
    return [
        {
            "id": r.id,
            "kind": r.kind,
            "record": r.record,
            "recordedBy": r.recorded_by,
            "createdAt": r.created_at,
        }
        for r in s.scalars(
            select(StudyAuditRecord)
            .where(StudyAuditRecord.study_id == study_id)
            .order_by(StudyAuditRecord.id)
        )
    ]


def register_routes(app, db, authorize, resolve_protocol, joined_rows, now, identity):
    def protocol(s, study_id):
        proto = resolve_protocol(s, study_id)
        if proto is None:
            raise HTTPException(
                409, "Compile and approve a study protocol before planning"
            )
        return proto

    @app.get("/instruments/surveys")
    def instruments():
        return {"instruments": shipped_instruments()}

    @app.get("/studies/{study_id}/plan", dependencies=[Depends(authorize("view"))])
    def get_plan(study_id: str, s=Depends(db)):
        proto = protocol(s, study_id)
        record = latest_plan(s, study_id)
        return {
            "plan": (
                {
                    **record.result,
                    "planId": record.id,
                    "createdAt": record.created_at,
                    "protocol": provenance(record.protocol),
                    "measureId": record.inputs.get("measure_id"),
                    "stale": record.protocol_hash != content_hash(proto),
                }
                if record
                else None
            ),
            "protocol": proto,
            "decisions": decision_records(s, study_id),
        }

    @app.post(
        "/studies/{study_id}/plan", dependencies=[Depends(authorize("contribute"))]
    )
    def create_plan(study_id: str, body: PlanRequest, s=Depends(db)):
        proto = protocol(s, study_id)
        try:
            check_plan(body, proto)
            result = plan_study(body.assumptions())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return saved_plan(s, study_id, proto, body.model_dump(), result, now)

    @app.post(
        "/studies/{study_id}/pilot-variance",
        dependencies=[Depends(authorize("contribute"))],
    )
    def pilot_update(study_id: str, body: PlanRequest, s=Depends(db)):
        proto = protocol(s, study_id)
        try:
            measure = check_plan(body, proto)
            if body.distribution == "ordinal":
                raise ValueError(
                    "Pilot latent ordinal variance is not identifiable from "
                    "Likert ratings; no sample size is reported"
                )
            field = measure["fields"][0] if measure else "task_outcome.firstGreenMs"
            pid_rows = joined_rows(s, study_id)
            tagged = {r["sessionId"] for r in pid_rows if r.get("pilot")}
            rows = [
                r
                for r in pid_rows
                if r["sessionId"] in tagged and r.get("inclusionDecision") != "exclude"
            ]
            values = participant_outcomes(
                rows,
                proto,
                field,
                measure.get("instrument") if measure else None,
                "log" if body.distribution == "log-normal" else "raw",
            )
            conditions = proto["conditions"]
            ids = {p for p, c in values}
            if body.design == "within-subjects":
                ids = {p for p in ids if all((p, c) in values for c in conditions)}
                variance = estimate_variance(
                    [
                        values[(p, conditions[1])] - values[(p, conditions[0])]
                        for p in sorted(ids)
                    ]
                )
            else:
                if any(sum((p, c) in values for c in conditions) != 1 for p in ids):
                    raise ValueError(
                        "Between-subjects pilot contains participants in more "
                        "than one arm"
                    )
                groups = [
                    [v for (p, c), v in values.items() if c == cond]
                    for cond in conditions
                ]
                if min(map(len, groups)) < 2:
                    raise ValueError(
                        "At least two real pilot participants per arm are required"
                    )
                df = sum(map(len, groups)) - len(groups)
                pooled = (
                    sum(
                        float(np.sum((np.asarray(g) - np.mean(g)) ** 2)) for g in groups
                    )
                    / df
                )
                if pooled <= 0:
                    raise ValueError("Pilot variance is zero")
                ci = [
                    df * pooled / stats.chi2.ppf(0.975, df),
                    df * pooled / stats.chi2.ppf(0.025, df),
                ]
                variance = {
                    "participants": len(ids),
                    "variance": pooled,
                    "sd": float(np.sqrt(pooled)),
                    "varianceCI": list(map(float, ci)),
                    "sdCI": list(map(float, np.sqrt(ci))),
                    "actionable": len(ids) >= 8,
                    "warnings": (
                        [
                            "Fewer than 8 pilot participants: the variance interval "
                            "is too wide to act on."
                        ]
                        if len(ids) < 8
                        else []
                    )
                    + [
                        "Pooled variance CI assumes independent normal outcomes "
                        "(log outcomes for log-normal plans)."
                    ],
                }
            variance["sessionIds"] = sorted(tagged)
            variance["field"] = field
            if body.period_effect or body.order_effect:
                raise ValueError(
                    "Pilot variance updates with period/order effects "
                    "require an adjusted model; no updated sample size is "
                    "reported"
                )
            if body.covariate_correlation:
                raise ValueError(
                    "Pilot ANCOVA variance updates require a "
                    "residual-variance estimator; no updated sample size is "
                    "reported"
                )
            before = plan_study(body.assumptions())
            inputs = {**asdict(body.assumptions()), "sd": variance["sd"]}
            after = plan_study(PlanInput(**inputs), pilot=variance)
            after["before"] = before
            after["pilotSensitivity"] = [
                {
                    "sd": sd,
                    "required": plan_study(
                        PlanInput(**{**inputs, "sd": sd}), pilot=variance
                    )["required"],
                }
                for sd in variance["sdCI"]
            ]
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return saved_plan(
            s, study_id, proto, {**inputs, "measure_id": body.measure_id}, after, now
        )

    @app.get(
        "/studies/{study_id}/control-arm-audit",
        dependencies=[Depends(authorize("view"))],
    )
    def control_audit(study_id: str, s=Depends(db)):
        proto = protocol(s, study_id)
        return {
            **audit_sessions(
                joined_rows(s, study_id),
                proto.get("controlConditions", []),
                decision_records(s, study_id),
            ),
            "records": audit_records(s, study_id),
        }

    @app.post(
        "/studies/{study_id}/sessions/{session_id}/annotation",
        dependencies=[Depends(authorize("contribute"))],
    )
    def annotate(
        study_id: str,
        session_id: str,
        body: SessionTagRequest,
        s=Depends(db),
        who=Depends(identity),
    ):
        rows = joined_rows(s, study_id)
        if not any(r["sessionId"] == session_id for r in rows):
            raise HTTPException(
                404, "Session not found in this study's real captured data"
            )
        record = s.get(SessionAnnotation, session_id)
        if record is not None and record.study_id != study_id:
            raise HTTPException(404, "Session not found")
        if record is None:
            record = SessionAnnotation(
                session_id=session_id,
                study_id=study_id,
                pilot=0,
                decision="undecided",
                reason="",
                decided_by="",
                updated_at=now(),
            )
            s.add(record)
        if body.pilot is not None:
            record.pilot = int(body.pilot)
        if body.decision is not None:
            record.decision = body.decision
        record.reason, record.decided_by, record.updated_at = (
            body.reason,
            who.sub,
            now(),
        )
        s.flush()
        decision = decision_records(s, study_id)[session_id]
        s.add(
            StudyAuditRecord(
                study_id=study_id,
                kind="session-decision",
                record={"sessionId": session_id, **decision},
                recorded_by=who.sub,
                created_at=now(),
            )
        )
        return decision

    @app.post(
        "/studies/{study_id}/audit-calibration",
        dependencies=[Depends(authorize("contribute"))],
    )
    def calibration(
        study_id: str, body: CalibrationRequest, s=Depends(db), who=Depends(identity)
    ):
        proto = protocol(s, study_id)
        audit = audit_sessions(
            joined_rows(s, study_id), proto.get("controlConditions", [])
        )
        known = {row["sessionId"] for row in audit["sessions"]}
        if not body.labels or set(body.labels) - known:
            raise HTTPException(
                422,
                "Labels must reference real captured control sessions in this study",
            )
        result = {
            **calibration_report(audit, body.labels),
            "source": body.source,
            "labels": body.labels,
            "protocolHash": content_hash(proto),
            "labelPolicy": "Researcher-supplied independent truth; no inferred labels",
        }
        s.add(
            StudyAuditRecord(
                study_id=study_id,
                kind="calibration",
                record=result,
                recorded_by=who.sub,
                created_at=now(),
            )
        )
        return result

    @app.get("/studies/{study_id}/lineage", dependencies=[Depends(authorize("view"))])
    def lineage(
        study_id: str,
        originalStudyId: str | None = None,
        authorization: str = Header(default=""),
        s=Depends(db),
    ):
        proto = protocol(s, study_id)
        target = originalStudyId or proto.get("rerunOf")
        if not target:
            return {
                "rerun": provenance(proto),
                "original": None,
                "fields": [],
                "pooled": False,
            }
        # Resolve by id only after authorizing the original as well.
        if len(target) == 64:
            match = s.scalar(
                select(StudyPlan)
                .where(StudyPlan.protocol_hash == target)
                .order_by(StudyPlan.id)
                .limit(1)
            )
            if match is None:
                raise HTTPException(404, "Original protocol hash was not recorded")
            target = match.study_id
            authorize("view")(authorization=authorization, study_id=target)
            original = match.protocol
        else:
            authorize("view")(authorization=authorization, study_id=target)
            original = protocol(s, target)
        return compare_designs(original, proto)
