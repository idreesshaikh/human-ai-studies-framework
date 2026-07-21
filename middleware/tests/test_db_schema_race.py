"""The schema-creation resilience guards in db._create_schema.

On Railway a redeploy can briefly overlap the old and new container against
the same Postgres database; both processes' create_all() can race on the
catalog's own unique indexes (pg_type_typname_nsp_index). That specific,
narrow race should be logged and survived, not crash-loop the service -
but any other integrity/programming error must still fail loudly.

Separately, a managed database can be briefly unreachable right after
provisioning (DNS not yet propagated) - a bounded retry gives that a chance
to heal instead of crashing on the very first hiccup, while a persistent
misconfiguration still exits fatally once attempts are exhausted.
"""

import middleware.db as db_mod
from middleware.db import (
    Base,
    _all_tables_present,
    _create_schema,
    _is_concurrent_create_race,
)
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError


class _FakeOrig(Exception):
    pass


def _integrity_error(message: str) -> IntegrityError:
    return IntegrityError("CREATE TABLE events (...)", {}, _FakeOrig(message))


def test_recognizes_the_pg_type_race():
    exc = _integrity_error(
        'duplicate key value violates unique constraint "pg_type_typname_nsp_index"\n'
        "DETAIL:  Key (typname, typnamespace)=(events, 2200) already exists."
    )
    assert _is_concurrent_create_race(exc)


def test_recognizes_a_generic_already_exists_duplicate_key():
    exc = _integrity_error(
        'duplicate key value violates unique constraint "x"\nDETAIL: already exists.'
    )
    assert _is_concurrent_create_race(exc)


def test_does_not_recognize_an_unrelated_integrity_error():
    # e.g. a real NOT NULL / foreign-key violation elsewhere - must stay fatal.
    exc = _integrity_error(
        'null value in column "session_id" violates not-null constraint'
    )
    assert not _is_concurrent_create_race(exc)


def test_does_not_recognize_an_unrelated_programming_error():
    exc = ProgrammingError(
        "SELECT ...", {}, _FakeOrig('relation "nonexistent" does not exist')
    )
    assert not _is_concurrent_create_race(exc)


def test_all_tables_present_true_once_schema_exists(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'race.sqlite3'}")
    Base.metadata.create_all(engine)
    assert _all_tables_present(engine)


def test_all_tables_present_false_on_a_bare_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'empty.sqlite3'}")
    assert inspect(engine).get_table_names() == []
    assert not _all_tables_present(engine)


def _operational_error(message: str) -> OperationalError:
    return OperationalError("CONNECT", {}, _FakeOrig(message))


def test_create_schema_retries_transient_connection_failures_then_succeeds(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(db_mod.time, "sleep", lambda _seconds: None)
    engine = create_engine(f"sqlite:///{tmp_path / 'retry.sqlite3'}")
    real_create_all = Base.metadata.create_all
    calls = {"n": 0}

    def flaky_create_all(bound_engine):
        calls["n"] += 1
        if calls["n"] < 3:
            raise _operational_error(
                "failed to resolve host 'postgres.railway.internal'"
            )
        real_create_all(bound_engine)

    monkeypatch.setattr(Base.metadata, "create_all", flaky_create_all)
    _create_schema(engine, "postgresql://x/y")  # must not raise
    assert calls["n"] == 3
    assert _all_tables_present(engine)


def test_create_schema_exhausts_retries_and_exits(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod.time, "sleep", lambda _seconds: None)
    engine = create_engine(f"sqlite:///{tmp_path / 'dead.sqlite3'}")

    def always_fails(_engine):
        raise _operational_error("failed to resolve host 'postgres.railway.internal'")

    monkeypatch.setattr(Base.metadata, "create_all", always_fails)
    try:
        _create_schema(engine, "postgresql://x/y")
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert exc.code == 1
