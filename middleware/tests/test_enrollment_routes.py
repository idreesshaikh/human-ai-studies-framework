from fastapi.testclient import TestClient


def test_mint_refuses_before_ethics_gate(client_no_ethics: TestClient):
    r = client_no_ethics.post(
        "/studies/pilot/enrollment/tokens", json={"count": 2, "grain": "participant"}
    )
    assert r.status_code == 409
    assert "ethics" in r.json()["detail"].lower()


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
    assert body["participantId"] == "P01"
    assert body["condition"] == "ai-assisted"
    assert body["sessionCredential"]
    assert body["ingestEndpoint"].endswith("/ingest/events")
    assert body["captureConfig"]["settings"]["cognitiveOverlay.participantId"] == "P01"
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
