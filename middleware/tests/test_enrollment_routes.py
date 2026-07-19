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
    assert client_ethics_ok.delete(f"/enrollment/tokens/{tid}").status_code == 200
    assert client_ethics_ok.get("/studies/pilot/enrollment/tokens").json() == []
