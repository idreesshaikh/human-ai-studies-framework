#!/usr/bin/env python3
"""The agent-discovery demo.

Given ONLY a deployment's manifest URL — zero repository access — an agent
can bootstrap everything it needs to work with the platform. This script
*is* that agent, and it *is* the fit criterion made executable: it doubles
as living documentation of the agent-discovery flow.

The flow, using nothing but HTTP against the manifest:

  1. GET /.well-known/platform-manifest        → discover the whole surface
  2. follow manifest.api.openapi               → the API contract
  3. follow manifest.schemas.protocol.url      → the real protocol schema,
     then validate a draft against it (locally, no repo)
  4. follow manifest.vocabulary.glossary       → answer "what does
     `condition` mean here?" from the documents of record

Run against a live local boot:
    uv run python scripts/agent_manifest_demo.py --base http://127.0.0.1:8000

Or in-process against a fresh app (no server needed), which is what CI runs:
    uv run python scripts/agent_manifest_demo.py --in-process

Exit 0 = every discovery step succeeded; exit 1 = a step failed (printed).
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request

MANIFEST_PATH = "/.well-known/platform-manifest"


class Http:
    """Minimal GET client — either real HTTP or an in-process FastAPI
    TestClient, behind one interface so the demo body is identical."""

    def get_json(self, path: str) -> dict:
        raise NotImplementedError


class LiveHttp(Http):
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    def get_json(self, path: str) -> dict:
        url = path if path.startswith("http") else self.base + path
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))


class InProcessHttp(Http):
    def __init__(self) -> None:
        import tempfile
        from pathlib import Path

        from fastapi.testclient import TestClient
        from middleware.app import create_app
        from middleware.settings import Settings

        d = Path(tempfile.mkdtemp())
        self.client = TestClient(
            create_app(
                Settings(
                    db_path=d / "demo.sqlite3",
                    data_dir=d / "data",
                    protocol_path=None,
                    spa_dist=d / "nd",
                )
            )
        )

    def get_json(self, path: str) -> dict:
        # Relative paths only (the manifest links are relative to baseUrl).
        rel = path
        if path.startswith("http"):
            rel = "/" + path.split("/", 3)[-1] if path.count("/") >= 3 else path
        res = self.client.get(rel)
        res.raise_for_status()
        return res.json()


def _log(step: str, ok: bool, detail: str = "") -> bool:
    mark = "✓" if ok else "✗"
    print(f"{mark} {step}{f' — {detail}' if detail else ''}")
    return ok


def run(http: Http) -> bool:
    ok = True

    # 1. Discover the platform from the manifest alone.
    manifest = http.get_json(MANIFEST_PATH)
    ok &= _log(
        "discover platform from the manifest",
        "platform" in manifest and "capabilities" in manifest,
        f"{manifest.get('platform', {}).get('name', '?')} — "
        f"{len(manifest.get('capabilities', []))} capabilities",
    )

    # 2. Follow the linked OpenAPI doc — the API contract.
    openapi_url = manifest.get("api", {}).get("openapi", "")
    openapi = http.get_json(openapi_url)
    ok &= _log(
        "follow api.openapi → the API contract",
        bool(openapi.get("paths")),
        f"{len(openapi.get('paths', {}))} endpoints; auth = "
        f"{manifest.get('api', {}).get('auth', {}).get('mode')}",
    )

    # 3. Fetch the real protocol schema and validate a draft against it —
    #    the agent can check its own work with zero repository access.
    protocol_schema_url = manifest.get("schemas", {}).get("protocol", {}).get("url", "")
    schema = http.get_json(protocol_schema_url)
    ok &= _log(
        "fetch schemas.protocol → the real protocol schema",
        "properties" in schema,
        "protocolVersion accepts "
        f"{schema.get('properties', {}).get('protocolVersion', {}).get('enum')}",
    )
    valid_draft = _minimal_valid_protocol()
    errors = _validate(schema, valid_draft)
    ok &= _log(
        "validate a well-formed draft against it",
        not errors,
        "0 errors" if not errors else f"errors: {errors}",
    )
    broken = {"study": {"id": "x"}}  # missing everything
    ok &= _log(
        "a broken draft is rejected (the agent can check its work)",
        bool(_validate(schema, broken)),
    )

    # 4. Answer "what does `condition` mean here?" from the vocabulary.
    glossary_url = manifest.get("vocabulary", {}).get("glossary", "")
    try:
        glossary = http.get_json(glossary_url)
        term = _find_term(glossary, "condition")
        ok &= _log(
            'answer "what does `condition` mean?" from the vocabulary',
            term is not None,
            (term or "")[:60],
        )
    except Exception as exc:  # vocabulary may require auth in some modes
        ok &= _log("vocabulary lookup", False, f"could not read glossary ({exc})")

    return ok


def _minimal_valid_protocol() -> dict:
    """A minimal protocol the real schema accepts — enough for the agent to
    prove it can construct a valid draft from the schema alone."""
    return {
        "protocolVersion": 4,
        "study": {
            "id": "agent-demo",
            "title": "Agent-constructed draft",
            "researchers": ["Agent"],
            "ethicsRef": "n/a",
        },
        "researchQuestions": [{"id": "RQ-1", "text": "Does discovery work?"}],
        "conditions": ["a", "b"],
        "participants": {
            "planned": 2,
            "design": "within-subjects",
            "counterbalanced": True,
        },
        "session": {"durationMinutes": 30, "taskDescription": "demo"},
        "instruments": {
            "tern": {
                "session": {"durationMinutes": 30},
                "fatigue": {"intervalMinutes": 15, "waitForPauseSeconds": 4},
                "stuck": {"enabled": True, "thresholdSeconds": 90},
                "output": {"httpEndpoint": "http://127.0.0.1:8000/ingest/events"},
            }
        },
        "phases": [{"name": "design", "gates": []}],
        "analysisPlan": [{"rq": "RQ-1", "recipes": ["task-outcome-by-condition"]}],
    }


def _validate(schema: dict, doc: dict) -> list[str]:
    import jsonschema

    validator = jsonschema.Draft202012Validator(schema)
    return [e.message for e in validator.iter_errors(doc)]


def _find_term(glossary: object, term: str) -> str | None:
    """The vocabulary endpoint returns terms in one of a few shapes; find the
    definition of ``term`` robustly."""
    if isinstance(glossary, dict):
        if term in glossary and isinstance(glossary[term], str):
            return glossary[term]
        for key in ("terms", "glossary", "entries"):
            if key in glossary:
                return _find_term(glossary[key], term)
    if isinstance(glossary, list):
        for entry in glossary:
            if isinstance(entry, dict):
                name = entry.get("term") or entry.get("name") or entry.get("id")
                if name and name.lower() == term.lower():
                    return entry.get("definition") or entry.get("text") or str(entry)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="deployment base URL")
    parser.add_argument(
        "--in-process",
        action="store_true",
        help="run against a fresh in-process app (no server; CI mode)",
    )
    args = parser.parse_args()

    if args.in_process or not args.base:
        http: Http = InProcessHttp()
        where = "in-process app"
    else:
        http = LiveHttp(args.base)
        where = args.base

    print(f"Agent discovery demo — against {where}\n")
    ok = run(http)
    verdict = (
        "✓ agent bootstrapped from the manifest alone" if ok else "✗ discovery failed"
    )
    print("\n" + verdict)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
