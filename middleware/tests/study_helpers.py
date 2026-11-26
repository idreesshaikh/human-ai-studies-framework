"""Helpers for tests that need a study whose protocol has been applied."""

from __future__ import annotations

from fastapi.testclient import TestClient


def apply_draft(client: TestClient, study_id: str, headers: dict | None = None) -> dict:
    """Compile the study's draft and apply it, as Review draft → Apply does.

    A study created from a template starts with that template as an unapplied
    draft; planning, links and data wait for this step."""
    compiled = client.post(
        f"/studies/{study_id}/conversation/compile", json={}, headers=headers or {}
    )
    assert compiled.status_code == 200, compiled.text
    result = compiled.json()
    assert result["valid"], (result["errors"], result["unresolved"])
    approved = client.post(
        f"/studies/{study_id}/conversation/approve",
        json={"compilationId": result["compilationId"], "approvedBy": "Owner"},
        headers=headers or {},
    )
    assert approved.status_code == 200, approved.text
    return result
