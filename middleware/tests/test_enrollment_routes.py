from fastapi.testclient import TestClient


def test_mint_refuses_before_ethics_gate(client_no_ethics: TestClient):
    r = client_no_ethics.post(
        "/studies/pilot/enrollment/tokens", json={"count": 2, "grain": "participant"}
    )
    assert r.status_code == 409
    assert "ethics" in r.json()["detail"].lower()


def test_dev_mode_bypasses_ethics_gate_for_minting(
    client_dev_mode_no_ethics: TestClient,
):
    # MIDDLEWARE_DEV_MODE relaxes the ethics gate so the enrollment flow is
    # testable on a study that hasn't cleared ethics — the same request that
    # 409s in production succeeds here.
    r = client_dev_mode_no_ethics.post(
        "/studies/pilot/enrollment/tokens", json={"count": 2, "grain": "participant"}
    )
    assert r.status_code == 200, r.text
    assert len(r.json()) == 2


def test_mint_batch_assigns_counterbalanced_conditions(client_ethics_ok: TestClient):
    r = client_ethics_ok.post(
        "/studies/pilot/enrollment/tokens", json={"count": 4, "grain": "participant"}
    )
    assert r.status_code == 200
    toks = r.json()
    assert len(toks) == 4
    conds = [t["condition"] for t in toks]
    # 2-condition protocol, round-robin -> exactly balanced
    assert conds.count("ai-assisted") == 2 and conds.count("unassisted") == 2
    assert all(t["connectionString"].count("#") == 1 for t in toks)
    assert [t["participantId"] for t in toks] == ["P01", "P02", "P03", "P04"]


def test_list_then_revoke(client_ethics_ok: TestClient):
    client_ethics_ok.post(
        "/studies/pilot/enrollment/tokens", json={"count": 1, "grain": "session"}
    )
    listed = client_ethics_ok.get("/studies/pilot/enrollment/tokens").json()
    assert listed[0]["status"] == "unredeemed"
    tid = listed[0]["id"]
    assert (
        client_ethics_ok.delete(f"/studies/pilot/enrollment/tokens/{tid}").status_code
        == 200
    )
    assert client_ethics_ok.get("/studies/pilot/enrollment/tokens").json() == []
    # IDOR guard: a token that isn't in this study cannot be revoked via it.
    other = client_ethics_ok.post(
        "/studies/pilot/enrollment/tokens", json={"count": 1, "grain": "session"}
    ).json()[0]
    # 404 (not 403): a study's members must not learn another study's token exists.
    assert (
        client_ethics_ok.delete(
            f"/studies/other-study/enrollment/tokens/{other['id']}"
        ).status_code
        == 404
    )


def test_redeem_returns_identity_config_and_consent(client_ethics_ok: TestClient):
    tok = client_ethics_ok.post(
        "/studies/pilot/enrollment/tokens", json={"count": 1, "grain": "participant"}
    ).json()[0]
    raw = tok["connectionString"].split("#", 1)[1]
    r = client_ethics_ok.post("/pair/redeem", json={"token": raw})
    assert r.status_code == 200
    body = r.json()
    assert body["studyId"] == "pilot"
    assert body["participantId"] == "P01"
    assert body["condition"] == "ai-assisted"
    assert body["sessionCredential"]
    assert body["ingestEndpoint"].endswith("/ingest/events")
    assert body["captureConfig"]["settings"]["tern.participantId"] == "P01"
    assert body["contentPolicy"] == "metadata-only"
    # The study title, not the "pilot" study_id/URL segment, is what the
    # consent statement embeds (enrollment.consent_statement reads
    # protocol["study"]["title"]). client_ethics_ok compiles the METR
    # template with no parameter overrides, so the title is the template's
    # own default (templates/registry/metr-rct-v1.yaml) rather than the
    # word "Pilot" — confirmed by inspecting the compiled YAML directly.
    assert "AI assistance on real tasks" in body["consentStatement"]


def test_session_grain_token_is_single_use(client_ethics_ok: TestClient):
    tok = client_ethics_ok.post(
        "/studies/pilot/enrollment/tokens", json={"count": 1, "grain": "session"}
    ).json()[0]
    raw = tok["connectionString"].split("#", 1)[1]
    assert client_ethics_ok.post("/pair/redeem", json={"token": raw}).status_code == 200
    second = client_ethics_ok.post("/pair/redeem", json={"token": raw})
    assert second.status_code == 410


def test_revoked_token_cannot_redeem(client_ethics_ok: TestClient):
    tok = client_ethics_ok.post(
        "/studies/pilot/enrollment/tokens", json={"count": 1, "grain": "participant"}
    ).json()[0]
    client_ethics_ok.delete(f"/studies/pilot/enrollment/tokens/{tok['id']}")
    raw = tok["connectionString"].split("#", 1)[1]
    assert client_ethics_ok.post("/pair/redeem", json={"token": raw}).status_code == 410


def test_capture_config_matches_redeem_and_requires_credential(
    client_ethics_ok: TestClient,
):
    tok = client_ethics_ok.post(
        "/studies/pilot/enrollment/tokens", json={"count": 1, "grain": "participant"}
    ).json()[0]
    raw = tok["connectionString"].split("#", 1)[1]
    cred = client_ethics_ok.post("/pair/redeem", json={"token": raw}).json()[
        "sessionCredential"
    ]

    assert client_ethics_ok.get("/studies/pilot/capture-config").status_code == 401
    r = client_ethics_ok.get(
        "/studies/pilot/capture-config",
        headers={"authorization": f"Bearer {cred}"},
    )
    assert r.status_code == 200
    assert r.json()["settings"]["tern.participantId"] == "P01"


def test_list_carries_capture_config_pre_flight_visibility(
    client_ethics_ok: TestClient,
):
    client_ethics_ok.post(
        "/studies/pilot/enrollment/tokens", json={"count": 1, "grain": "participant"}
    )
    row = client_ethics_ok.get("/studies/pilot/enrollment/tokens").json()[0]
    assert row["captureConfig"]["captureConfigVersion"]
    assert row["captureConfig"]["enabledInstruments"] == [
        {"name": "stuck", "enabled": True}
    ]
    assert row["connectionString"] and "#" in row["connectionString"]


def test_list_status_flips_to_streaming_once_events_arrive(
    client_ethics_ok: TestClient,
):
    tok = client_ethics_ok.post(
        "/studies/pilot/enrollment/tokens", json={"count": 1, "grain": "participant"}
    ).json()[0]
    raw = tok["connectionString"].split("#", 1)[1]
    cred = client_ethics_ok.post("/pair/redeem", json={"token": raw}).json()[
        "sessionCredential"
    ]
    listed = client_ethics_ok.get("/studies/pilot/enrollment/tokens").json()
    assert listed[0]["status"] == "paired"  # redeemed, but no events yet

    client_ethics_ok.post(
        "/ingest/events",
        json=_events("P01", "ai-assisted"),
        headers={"authorization": f"Bearer {cred}"},
    )
    listed = client_ethics_ok.get("/studies/pilot/enrollment/tokens").json()
    assert listed[0]["status"] == "streaming"
    # Outside the window, it reads back as merely paired.
    stale = client_ethics_ok.get(
        "/studies/pilot/enrollment/tokens", params={"windowSeconds": 0}
    ).json()
    assert stale[0]["status"] == "paired"


# ========================================================== toggle tests


def test_toggle_catalog_refuses_before_ethics(client_no_ethics):
    r = client_no_ethics.get("/studies/pilot/enrollment/toggles/catalog")
    assert r.status_code == 404  # study not built yet


def test_toggle_catalog_returns_filtered_entries(client_ethics_ok):
    """Only entries whose instrument is present in the protocol appear."""
    r = client_ethics_ok.get("/studies/pilot/enrollment/toggles/catalog")
    assert r.status_code == 200
    entries = r.json()
    # METR template has tern but not agentCapture.
    names = [e["label"] for e in entries]
    assert "Stuck detection" in names
    assert "Fatigue probe cadence" in names
    assert "Agent conversation content policy" not in names  # no agentCapture instr
    assert all(e.get("grounding") for e in entries)


def test_toggle_catalog_current_value_matches_protocol(client_ethics_ok):
    """The currentValue field mirrors the protocol's instrument config."""
    r = client_ethics_ok.get("/studies/pilot/enrollment/toggles/catalog")
    stuck = [e for e in r.json() if e["path"] == ["stuck", "enabled"]]
    assert stuck
    assert stuck[0]["currentValue"] is True  # METR defaults stuck.enabled: true


def test_toggle_refuses_before_ethics(client_no_ethics):
    body = {"instrument": "tern", "path": ["stuck", "enabled"],
            "value": False, "rationale": "test"}
    r = client_no_ethics.post("/studies/pilot/enrollment/toggles", json=body)
    assert r.status_code == 404


def test_toggle_nested_enabled_is_consent_relevant(client_ethics_ok):
    """FR-CONV-7: toggling a nested 'enabled' field records an amendment."""
    body = {"instrument": "tern", "path": ["stuck", "enabled"],
            "value": False, "rationale": "testing FR-CONV-7"}
    r = client_ethics_ok.post("/studies/pilot/enrollment/toggles", json=body)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["applied"] is True
    assert body["requiresReapproval"] is True
    assert body["amendmentId"]
    # Verify the amendment exists in the amendment history.
    hist = client_ethics_ok.get("/studies/pilot/amendments").json()
    assert hist["amendments"]
    assert hist["pendingReapproval"] is not None


def test_toggle_non_consent_change_applies_directly(client_ethics_ok):
    """A threshold change is NOT consent-relevant — applies without amendment."""
    body = {"instrument": "tern", "path": ["stuck", "thresholdSeconds"],
            "value": 120, "rationale": "fine-tune"}
    r = client_ethics_ok.post("/studies/pilot/enrollment/toggles", json=body)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["applied"] is True
    assert body["requiresReapproval"] is False


def test_toggle_catalog_reflects_amended_protocol(client_ethics_ok):
    """After a toggle, the catalog returns the new currentValue."""
    body = {"instrument": "tern", "path": ["stuck", "enabled"],
            "value": False, "rationale": "turn off stuck"}
    client_ethics_ok.post("/studies/pilot/enrollment/toggles", json=body)
    r = client_ethics_ok.get("/studies/pilot/enrollment/toggles/catalog")
    stuck = [e for e in r.json() if e["path"] == ["stuck", "enabled"]]
    assert stuck[0]["currentValue"] is False


def test_toggle_invalid_path_returns_400(client_ethics_ok):
    body = {"instrument": "tern", "path": ["nonexistent", "value"],
            "value": True, "rationale": "bad"}
    r = client_ethics_ok.post("/studies/pilot/enrollment/toggles", json=body)
    assert r.status_code == 422


# ==========================================================


def _events(pid, cond):
    return {
        "events": [
            {
                "sessionId": "s1",
                "seq": 0,
                "v": 3,
                "participantId": pid,
                "condition": cond,
                "type": "session_start",
            }
        ]
    }


def test_credentialed_ingest_server_stamps_join_keys(client_ethics_ok: TestClient):
    tok = client_ethics_ok.post(
        "/studies/pilot/enrollment/tokens", json={"count": 1, "grain": "participant"}
    ).json()[0]
    raw = tok["connectionString"].split("#", 1)[1]
    cred = client_ethics_ok.post("/pair/redeem", json={"token": raw}).json()[
        "sessionCredential"
    ]
    # Client LIES about being P08; the credential says P01 -> server overrides.
    r = client_ethics_ok.post(
        "/ingest/events",
        json=_events("P08", "unassisted"),
        headers={"authorization": f"Bearer {cred}"},
    )
    assert r.status_code == 200
    row = client_ethics_ok.get("/sessions/s1/events").json()[0]
    assert row["participantId"] == "P01"  # stamped from the credential
    assert row["condition"] == "ai-assisted"
    assert "credential-mismatch" in row["flags"]


def test_ingest_without_credential_still_lands_flagged(client_ethics_ok: TestClient):
    # Bearer present but bogus -> never 401, row stored and flagged.
    r = client_ethics_ok.post(
        "/ingest/events",
        json=_events("P01", "ai-assisted"),
        headers={"authorization": "Bearer not-a-real-credential"},
    )
    assert r.status_code == 200
    row = client_ethics_ok.get("/sessions/s1/events").json()[0]
    assert "unauthenticated" in row["flags"]


def _db_dependency(client: TestClient):
    """Find the exact ``db`` closure FastAPI resolved for ``/ingest/events``
    (Task A7): dependency_overrides is keyed on callable identity, and
    ``db`` is a closure inside ``create_app`` with no importable name, so
    the override target must be recovered from the route's dependant tree."""
    for route in client.app.routes:
        if getattr(route, "path", None) == "/ingest/events":
            for dep in route.dependant.dependencies:
                if getattr(dep.call, "__name__", None) == "db":
                    return dep.call
    raise AssertionError("could not find the `db` dependency on /ingest/events")


def test_ingest_survives_a_failing_credential_lookup(client_ethics_ok: TestClient):
    """Task A7 (Critical): resolve_credential's docstring promises 'never
    raises', but its DB read was unguarded. A SQLite lock / I/O error /
    any SQLAlchemy error there must degrade to the already-correct
    'unauthenticated' path (NFR-1/FR-ING-6: ingest never 500s, never drops
    a row) - not surface as a 500 that discards the whole batch.

    Forces the credential lookup itself to raise (not just 'no matching
    row') by overriding the `db` dependency with a session whose FIRST
    `.scalar(...)` call (the EnrollmentToken lookup) raises, while
    delegating everything else to a real session bound to the same
    on-disk sqlite file so the Event insert genuinely persists.
    """
    from middleware.db import make_session_factory

    db_dep = _db_dependency(client_ethics_ok)
    real_factory = make_session_factory(client_ethics_ok.db_path)

    class _FailFirstScalar:
        def __init__(self, real):
            self._real = real
            self._calls = 0

        def scalar(self, *args, **kwargs):
            self._calls += 1
            if self._calls == 1:
                raise RuntimeError("simulated DB error (lock/IO) on credential read")
            return self._real.scalar(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._real, name)

    def failing_db():
        real = real_factory()
        try:
            yield _FailFirstScalar(real)
            real.commit()
        finally:
            real.close()

    client_ethics_ok.app.dependency_overrides[db_dep] = failing_db
    try:
        r = client_ethics_ok.post(
            "/ingest/events",
            json=_events("P01", "ai-assisted"),
            headers={"authorization": "Bearer anything"},
        )
        assert r.status_code == 200, r.text
        rows = client_ethics_ok.get("/sessions/s1/events").json()
        assert len(rows) == 1  # the row was NOT dropped
        assert "unauthenticated" in rows[0]["flags"]
    finally:
        del client_ethics_ok.app.dependency_overrides[db_dep]


def test_credential_never_persists_into_stored_rows(client_ethics_ok: TestClient):
    tok = client_ethics_ok.post(
        "/studies/pilot/enrollment/tokens", json={"count": 1, "grain": "participant"}
    ).json()[0]
    raw = tok["connectionString"].split("#", 1)[1]
    cred = client_ethics_ok.post("/pair/redeem", json={"token": raw}).json()[
        "sessionCredential"
    ]
    client_ethics_ok.post(
        "/ingest/events",
        json=_events("P01", "ai-assisted"),
        headers={"authorization": f"Bearer {cred}"},
    )
    dump = client_ethics_ok.get("/sessions/s1/events").text
    assert cred not in dump  # the secret never leaks into stored data (wall #7)
