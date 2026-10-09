"""
The corpus-refresh / corpus-candidates / corpus-decide commands and the read-only
routes.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.auth import Identity
from middleware.db import CorpusCandidate, make_session_factory
from middleware.settings import Settings

from middleware import __main__ as cli
from middleware import corpus_fetchers
from middleware import corpus_refresh as cr

FIX = Path(__file__).parent / "fixtures" / "refresh"
CONFIG = {
    "arxiv": [{"terms": ["coding assistant"], "categories": ["cs.SE"]}],
    "semanticScholar": ["AI coding assistant developer"],
    "maxPerQuery": 50,
}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MIDDLEWARE_API_ONLY", "1")
    db = tmp_path / "cli.sqlite3"
    cfg = tmp_path / "q.json"
    cfg.write_text(json.dumps(CONFIG))
    monkeypatch.setattr(
        corpus_fetchers,
        "fetch_arxiv",
        lambda q, a, b, start, n: (
            (FIX / "arxiv_real.xml").read_bytes()
            if start == 0
            else b'<feed xmlns="http://www.w3.org/2005/Atom"/>'
        ),
    )
    monkeypatch.setattr(
        corpus_fetchers,
        "fetch_s2",
        lambda *a: json.loads((FIX / "s2_real.json").read_text()),
    )
    return db, cfg


def run_cli(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["middleware", *argv])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    return exc.value.code


def test_refresh_command_reports_and_exits_zero(env, monkeypatch, capsys):
    db, cfg = env
    code = run_cli(
        monkeypatch, "corpus-refresh", "--db", str(db), "--queries", str(cfg)
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "corpus refresh ok" in out and "4 new candidates" in out


def test_dry_run_stores_nothing(env, monkeypatch, capsys):
    db, cfg = env
    assert (
        run_cli(
            monkeypatch,
            "corpus-refresh",
            "--db",
            str(db),
            "--queries",
            str(cfg),
            "--dry-run",
        )
        == 0
    )
    assert "dry-run" in capsys.readouterr().out
    with make_session_factory(db)() as s:
        assert s.query(CorpusCandidate).count() == 0


def test_bad_queries_file_exits_two_with_the_reason(env, monkeypatch, capsys, tmp_path):
    db, _ = env
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    assert (
        run_cli(monkeypatch, "corpus-refresh", "--db", str(db), "--queries", str(bad))
        == 2
    )
    assert "no sources" in capsys.readouterr().err


def test_a_failing_source_makes_the_exit_code_nonzero_only_when_all_fail(
    env, monkeypatch, capsys
):
    db, cfg = env
    monkeypatch.setattr(
        corpus_fetchers,
        "fetch_s2",
        lambda *a: (_ for _ in ()).throw(RuntimeError("429")),
    )
    assert (
        run_cli(monkeypatch, "corpus-refresh", "--db", str(db), "--queries", str(cfg))
        == 1
    )  # partial
    assert "429" in capsys.readouterr().out


def test_candidates_then_decide(env, monkeypatch, capsys):
    db, cfg = env
    run_cli(monkeypatch, "corpus-refresh", "--db", str(db), "--queries", str(cfg))
    capsys.readouterr()
    assert run_cli(monkeypatch, "corpus-candidates", "--db", str(db)) == 0
    listing = capsys.readouterr().out
    assert "candidates: 4 new" in listing and "arxiv:2610.07639" in listing
    assert (
        run_cli(
            monkeypatch,
            "corpus-decide",
            "--db",
            str(db),
            "--ref",
            "arxiv:2610.07639",
            "--decision",
            "accept",
            "--note",
            "on topic",
        )
        == 0
    )
    assert "accepted" in capsys.readouterr().out
    assert (
        run_cli(
            monkeypatch,
            "corpus-decide",
            "--db",
            str(db),
            "--ref",
            "arxiv:2610.07639",
            "--decision",
            "reject",
        )
        == 1
    )  # cannot reverse
    assert (
        run_cli(
            monkeypatch,
            "corpus-decide",
            "--db",
            str(db),
            "--ref",
            "arxiv:0000.00000",
            "--decision",
            "accept",
        )
        == 1
    )
    assert run_cli(monkeypatch, "corpus-decide", "--db", str(db)) == 2


# --- API


@pytest.fixture
def client(tmp_path, monkeypatch, env):
    import middleware.auth as auth_mod

    def _verifier(authorization: str) -> Identity:
        if not authorization.startswith("Bearer "):
            raise auth_mod.HTTPException(401, "missing bearer token")
        sub = authorization.removeprefix("Bearer ")
        return Identity(sub=sub, display_name=sub, mode="clerk")

    monkeypatch.setattr(auth_mod, "verifier_from_settings", lambda _s: _verifier)
    settings = Settings(
        db_path=tmp_path / "api.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=None,
        spa_dist=tmp_path / "no-dist",
    )
    app_client = TestClient(
        create_app(settings, clock=lambda: datetime(2026, 10, 8, tzinfo=UTC))
    )
    factory = make_session_factory(settings.db_url)
    cr.run_once(
        factory,
        config_path=env[1],
        today=datetime(2026, 10, 8, tzinfo=UTC).date(),
        now=lambda: "2026-10-08T12:00:00Z",
    )
    return app_client


def bearer(sub):
    return {"Authorization": f"Bearer {sub}"}


def test_status_reports_the_last_refresh_and_candidate_counts(client):
    body = client.get("/corpus/status").json()
    assert body["candidates"] == {"new": 4, "accepted": 0, "rejected": 0}
    assert (
        body["lastRefresh"]["status"] == "ok"
        and body["lastRefresh"]["newCandidates"] == 4
    )
    assert isinstance(body["lastRefresh"]["ageDays"], int)


def test_candidates_route_lists_new_papers_best_first_and_is_read_only(client):
    res = client.get("/corpus/candidates", headers=bearer("alice"))
    assert res.status_code == 200, res.text
    body = res.json()
    scores = [c["score"] for c in body["candidates"]]
    assert len(body["candidates"]) == 4 and scores == sorted(scores, reverse=True)
    assert all(len(c["abstract"]) <= 500 for c in body["candidates"])
    for method in ("post", "put", "delete", "patch"):
        assert getattr(client, method)(
            "/corpus/candidates", headers=bearer("alice")
        ).status_code in (404, 405)


def test_candidates_route_requires_sign_in_and_validates_input(client):
    assert client.get("/corpus/candidates").status_code == 401
    assert (
        client.get(
            "/corpus/candidates?status=bogus", headers=bearer("alice")
        ).status_code
        == 422
    )
    assert (
        client.get("/corpus/candidates?limit=0", headers=bearer("alice")).status_code
        == 422
    )
    assert (
        client.get("/corpus/candidates?limit=1000", headers=bearer("alice")).status_code
        == 422
    )
