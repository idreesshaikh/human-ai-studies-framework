"""Deletion respects study/session ownership and leaves no scoped evidence behind."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from middleware import db


@pytest.mark.parametrize("delete_project", [False, True])
def test_delete_cleans_owned_capture_and_evidence_only(
    client_no_protocol, delete_project
):
    client = client_no_protocol
    project = client.post("/projects", json={"name": "Synthetic deletion test"}).json()
    target = client.post(
        f"/projects/{project['slug']}/studies", json={"name": "Target"}
    ).json()["id"]
    other = client.post(
        "/projects/implicit/studies", json={"name": "Preserved"}
    ).json()["id"]
    with Session(db._engine) as session:
        for sid, owner in [("owned", target), ("shared", target), ("other", other)]:
            session.add(
                db.SessionBlock(
                    session_id=sid, study_id=owner, participant_id="fixture"
                )
            )
        # An inconsistent shared mapping must not destroy another study's capture.
        session.add(
            db.SessionOpen(
                session_id="shared",
                study_id=other,
                protocol_version=1,
                opened_at="fixture",
            )
        )
        session.add(
            db.SessionOpen(
                session_id="open-only",
                study_id=target,
                protocol_version=1,
                opened_at="fixture",
            )
        )
        for sid in ["owned", "open-only", "shared", "other", "unmapped"]:
            session.add(
                db.Event(
                    session_id=sid,
                    source="tern",
                    seq=1,
                    participant_id="fixture",
                    condition="fixture",
                    v=4,
                    ts="fixture",
                    mono=0,
                    type="session_start",
                    payload={},
                    received_at="fixture",
                )
            )
            session.add(
                db.MetricRow(
                    table="file",
                    session_id=sid,
                    participant_id="fixture",
                    condition="fixture",
                    timestamp="fixture",
                    schema_version=1,
                    row={},
                    row_hash=sid,
                    received_at="fixture",
                )
            )
        for owner in [target, other, db.CORPUS_STUDY_ID]:
            session.add(
                db.EvidenceMapRow(
                    study_id=owner,
                    map_id="fixture",
                    map_version="1",
                    digest="fixture",
                    document={},
                )
            )
        session.commit()

    if delete_project:
        denied = client.request(
            "DELETE", f"/projects/{project['slug']}", json={"confirm": "wrong"}
        )
        assert denied.status_code == 400
        response = client.request(
            "DELETE", f"/projects/{project['slug']}", json={"confirm": "DELETE"}
        )
    else:
        response = client.delete(f"/studies/{target}")
    assert response.status_code == 200, response.text
    with Session(db._engine) as session:
        assert session.get(db.Study, target) is None
        assert session.get(db.Study, other) is not None
        for model in [db.Event, db.MetricRow, db.SessionBlock, db.SessionOpen]:
            assert set(session.scalars(select(model.session_id))) == (
                {"shared", "other", "unmapped"}
                if model in [db.Event, db.MetricRow]
                else {"other"}
                if model is db.SessionBlock
                else {"shared"}
            )
        assert set(session.scalars(select(db.EvidenceMapRow.study_id))) == {
            other,
            db.CORPUS_STUDY_ID,
        }
