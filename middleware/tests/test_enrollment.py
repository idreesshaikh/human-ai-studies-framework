from middleware.db import EnrollmentToken, make_session_factory


def test_enrollment_token_round_trips(tmp_path):
    factory = make_session_factory(str(tmp_path / "t.sqlite3"))
    with factory() as s:
        s.add(
            EnrollmentToken(
                id="e1",
                study_id="pilot",
                participant_id="P01",
                condition="ai-assisted",
                grain="participant",
                token="tok-abc",
                expires_at="2099-01-01T00:00:00Z",
                created_at="2026-07-19T00:00:00Z",
            )
        )
        s.commit()
    with factory() as s:
        row = s.query(EnrollmentToken).filter_by(token="tok-abc").one()
        assert row.participant_id == "P01"
        assert row.grain == "participant"
        assert row.credential is None
        assert row.redeemed_at is None
