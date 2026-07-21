# The Live Capture Link — Implementation Plan (Phase 19)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a researcher mint a pairing token from a study, a participant paste one connection string into VS Code, and the extension redeem it for a session credential + protocol-derived capture config + the study's consent statement, then stream server-stamped events onto the one timeline — no hand-typed IDs, no config drift, running sessions never reconfigured.

**Architecture:** Three subsystems, one vertical feature. **Middleware** gains an `EnrollmentToken` model, a pure `enrollment.py` helper module, mint/list/revoke + `/pair/redeem` + `/capture-config` routes, and optional Bearer auth on ingest that server-stamps join keys and accepts-and-flags mismatches. **Extension** gains four `src/core` modules (connection-string codec, capture-config applier, pre-flight summary, consent gate), an auth header on `HttpSink`, a `connectToStudy` command, a walkthrough, and a deep-link handler — config applied only at a session boundary. **Platform** gains an Enrollment tab in the study workspace (mint dialog + copy-link table + revoke).

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy / SQLite (uv workspace); TypeScript / VS Code API / `node:test` (extension); React 19 / Vite / shadcn-ui / Tailwind v4 (platform).

## Global Constraints

Every task's requirements implicitly include these (copied from `docs/roadmap/19-live-capture-link.md` and the load-bearing walls):

- **Wall #6 is HARD.** A running session is never reconfigured. Capture config is applied only at pair and at each session start (before the clock arms). No mid-session mutation, no live control channel, no consent-relevance classifier.
- **Ingest never blocks, never drops** (NFR-1/FR-ING-6). Adding Bearer auth to ingest must never return 401 and never drop a row. Un-credentialed/mismatched rows are stored with a flag.
- **Server-authoritative join keys** (wall #4). A credentialed ingest row's `participantId`/`condition` are stamped from the credential, overriding client values.
- **Privacy by construction** (wall #7). The pairing token and the session credential are transport secrets — they MUST NOT appear in any stored event row, export, or log line. This is a grep test, not a hope.
- **`src/core` never imports `vscode`** (NFR-3). Codec, config-apply, pre-flight, and consent-gate logic live in `extension/src/core` and are unit-tested with `node:test`; only the adapter (`src/vscode`) touches VS Code APIs.
- **No new dependency** (NFR-10). `secrets`, SQLAlchemy, VS Code built-ins, existing `fetch`/`HttpSink`, shadcn primitives already vendored. Nothing adopted.
- **`SCHEMA_VERSION` stays 3.** Event shape is unchanged; this is transport + config source + a consent gate. Do not bump it.
- **Ethics gate first.** Minting and redeeming refuse unless the study has cleared ethics (`StudyEvolution.ethics_approved_at` is set).
- **Glossary terms** (use verbatim in identifiers/copy): *pairing token*, *connection string*, *session credential*, *capture config*, *enrollment*. Never "session token" as a bare synonym.
- **Gates:** `uv run pytest && uv run ruff check .` (Python, from repo root); `npm run check` in `extension/`; `npm run build && npm run lint` in `platform/`.

**Connection-string format (fixed contract across subsystems):** `<serverBaseUrl>#<token>`, e.g. `https://study.lab.example#Ab3...`. The base URL never contains `#`; the token is URL-safe base64 (no `#`). The extension derives `ingestEndpoint = base + "/ingest/events"` and the redeem URL = `base + "/pair/redeem"`.

**captureConfigVersion (fixed contract):** `sha256(json.dumps(protocol["instruments"], sort_keys=True, separators=(",",":")).encode()).hexdigest()[:12]` — a 12-char hex string that changes iff the derived instruments config changes. Computed identically wherever needed.

---

## Part 0 — Traceability spine

### Task 0: Requirements, glossary, tracker rows

**Files:**
- Modify: `requirements/srs.md` (append four rows to the FR-INST / FR-ING / FR-DASH families)
- Modify: `requirements/traceability.md:§1` (four rows, status ⬜)
- Modify: `requirements/glossary.md` (five term rows)
- Modify: `docs/roadmap/README.md` (a "Study conductor (19–21)" section with the Phase 19 tracker row, status specced)

**Interfaces:**
- Produces: the requirement IDs `FR-INST-20`, `FR-ING-7`, `FR-INST-21`, `FR-DASH-10` that every later task's commit message references.

- [ ] **Step 1: Add the four SRS rows.** In `requirements/srs.md`, add to the FR-INST table:
  ```
  | FR-INST-20 | M | The framework SHALL let a participant's IDE enroll into a study by redeeming one pairing token (a connection string encoding middleware URL + token) that resolves its identity (participantId, condition), ingest endpoint, and capture config with no hand-entered IDs or endpoint; tokens are minted per-participant (reusable) or per-session (single-use), grain chosen at mint. | the platform loop's live-data rung; S6/S7. | ⬜ |
  | FR-INST-21 | M | The middleware SHALL serve a capture config derived deterministically from the protocol's instruments block; the IDE SHALL apply it at pair and at each session start behind a capture pre-flight; a running session SHALL NOT be reconfigured (wall #6) — a mid-run change takes effect at the next session start. Config carries a captureConfigVersion consumers branch on. | wall #6; FR-PROT-1/2/4; FR-INST-3. | ⬜ |
  ```
  To the FR-ING table:
  ```
  | FR-ING-7 | M | The middleware SHALL mint, list, and revoke pairing tokens (study-scoped, ethics-gated, role-gated) and verify them on redemption, issuing a short-lived session credential; credentialed ingest SHALL server-stamp participantId/condition, un-credentialed/mismatched rows SHALL be stored and flagged, never rejected or blocking. | RQ-F1; S3; NFR-1/2; FR-ING-6. | ⬜ |
  ```
  To the FR-DASH table:
  ```
  | FR-DASH-10 | S | The platform SHALL provide an enrollment surface in the study workspace: mint pairing tokens (batch/single, pick grain) as copy-links with live status (unredeemed/paired/streaming) and revoke, role-gated. | S1; FR-DASH-3; the platform loop. | ⬜ |
  ```

- [ ] **Step 2: Add the traceability rows.** In `requirements/traceability.md` §1 table, add four rows:
  ```
  | FR-INST-20 | S6,S7; platform loop | `middleware/` enrollment + `extension/` connect | ⬜ |
  | FR-ING-7 | RQ-F1; S3 | `middleware/enrollment.py` + ingest auth | ⬜ |
  | FR-INST-21 | wall #6; FR-PROT-4 | `middleware/` capture-config + `extension/` core | ⬜ |
  | FR-DASH-10 | S1; FR-DASH-3 | `platform/` EnrollmentPanel | ⬜ |
  ```

- [ ] **Step 3: Add the glossary rows.** In `requirements/glossary.md`, add:
  ```
  | **Pairing token** | The minted, single- or multi-use secret binding a study + participant + condition, delivered inside a connection string; redeemed by an IDE to enroll (FR-INST-20). *(not: session token)* |
  | **Connection string** | The copy-safe `serverUrl#token` a participant pastes once to connect their IDE to a study. |
  | **Session credential** | The short-lived bearer an IDE receives when it redeems a pairing token; authenticates ingest so the middleware can server-stamp join keys (FR-ING-7). |
  | **Capture config** | The versioned, protocol-derived set of enabled instruments/metrics an IDE applies at a session boundary (FR-INST-21). |
  | **Enrollment** | A participant's IDE joining a study by redeeming a pairing token. |
  ```

- [ ] **Step 4: Add the roadmap tracker row.** In `docs/roadmap/README.md`, after the platform-layer table, add:
  ```markdown
  ### Study conductor (19–21)

  | Phase | Title | Satisfies | Status |
  | ----- | ----- | --------- | ------ |
  | [19](19-live-capture-link.md) | The live capture link | FR-INST-20/21, FR-ING-7, FR-DASH-10 | ⬜ specced |
  | 20 | The capture console (grounded per-metric toggles) | (to be specced) | ⬜ |
  | 21 | The conductor overlay (in-editor cognitive load) | (to be specced) | ⬜ |
  ```

- [ ] **Step 5: Verify and commit.**
  Run: `grep -c "FR-INST-20\|FR-ING-7\|FR-INST-21\|FR-DASH-10" requirements/srs.md requirements/traceability.md`
  Expected: both files report the four IDs present.
  ```bash
  git add requirements/srs.md requirements/traceability.md requirements/glossary.md docs/roadmap/README.md
  git commit -m "MP-19: traceability spine — FR-INST-20/21, FR-ING-7, FR-DASH-10 + glossary + tracker

Assisted-by: Claude (Opus 4.8)"
  ```

---

## Part A — Middleware backend

### Task A1: The `EnrollmentToken` model

**Files:**
- Modify: `middleware/src/middleware/db.py` (add the model class after `Invitation`, ~line 391)
- Test: `middleware/tests/test_enrollment.py` (create)

**Interfaces:**
- Produces: `EnrollmentToken` ORM class with columns `id, study_id, participant_id, condition, grain, token, credential, expires_at, revoked_at, redeemed_at, created_by, created_at`. Table `enrollment_tokens`. Later tasks import it from `middleware.db`.

- [ ] **Step 1: Write the failing test.** Create `middleware/tests/test_enrollment.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails.**
  Run: `uv run pytest middleware/tests/test_enrollment.py::test_enrollment_token_round_trips -q`
  Expected: FAIL — `ImportError: cannot import name 'EnrollmentToken'`.

- [ ] **Step 3: Add the model.** In `middleware/src/middleware/db.py`, after the `Invitation` class (before `Study`), add:

```python
class EnrollmentToken(Base):
    """A pairing token binding a study + participant + condition (FR-INST-20).

    ``grain`` is 'participant' (reusable across that participant's sessions)
    or 'session' (single-use). ``token`` is what the participant pastes (inside
    a connection string); ``credential`` is the short-lived bearer minted on
    redeem and sent on ingest so the middleware can server-stamp join keys
    (FR-ING-7). Mirrors the ``Invitation`` mint/expire/revoke shape.
    """

    __tablename__ = "enrollment_tokens"
    __table_args__ = (
        CheckConstraint(
            "grain IN ('participant', 'session')", name="ck_enrollment_grain"
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    study_id: Mapped[str] = mapped_column(
        String, ForeignKey("studies.id"), index=True
    )
    participant_id: Mapped[str] = mapped_column(String)
    condition: Mapped[str] = mapped_column(String)
    grain: Mapped[str] = mapped_column(String)
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    #: Minted on redeem; sent as the ingest bearer. NULL until first redeem.
    credential: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    expires_at: Mapped[str] = mapped_column(String)
    revoked_at: Mapped[str | None] = mapped_column(String, nullable=True)
    redeemed_at: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[str] = mapped_column(String)
```

- [ ] **Step 4: Run test to verify it passes.**
  Run: `uv run pytest middleware/tests/test_enrollment.py::test_enrollment_token_round_trips -q`
  Expected: PASS. (The table is created by the existing `Base.metadata.create_all` at `make_session_factory`. If it does not exist, add the table to whatever boot table-creation the factory performs — a new SQLite table is additive.)

- [ ] **Step 5: Commit.**
  ```bash
  git add middleware/src/middleware/db.py middleware/tests/test_enrollment.py
  git commit -m "MP-19 A1: EnrollmentToken model (FR-INST-20)

Assisted-by: Claude (Opus 4.8)"
  ```

### Task A2: Pure enrollment helpers — connection string, config version, capture config

**Files:**
- Create: `middleware/src/middleware/enrollment.py`
- Test: `middleware/tests/test_enrollment.py` (append)

**Interfaces:**
- Consumes: `protocol.derive.derive_overlay_settings(protocol, participant_id, condition)` → flat `cognitiveOverlay.*` dict.
- Produces:
  - `connection_string(base_url: str, token: str) -> str`
  - `capture_config_version(protocol: dict) -> str`
  - `build_capture_config(protocol: dict, participant_id: str, condition: str, producer: str = "overlay") -> dict` → `{"captureConfigVersion": str, "producer": str, "settings": dict}`

- [ ] **Step 1: Write the failing tests.** Append to `middleware/tests/test_enrollment.py`:

```python
from middleware import enrollment

PROTOCOL = {
    "study": {"id": "pilot", "title": "Pilot"},
    "conditions": ["ai-assisted", "unassisted"],
    "participants": {"planned": 8},
    "session": {"durationMinutes": 60},
    "instruments": {
        "cognitiveOverlay": {
            "stuck": {"enabled": True, "thresholdSeconds": 90},
            "output": {"httpEndpoint": "http://x/ingest/events"},
        }
    },
}


def test_connection_string_format():
    assert (
        enrollment.connection_string("https://s.example/", "tok-1")
        == "https://s.example#tok-1"
    )


def test_capture_config_version_is_stable_and_content_sensitive():
    v1 = enrollment.capture_config_version(PROTOCOL)
    assert len(v1) == 12
    assert enrollment.capture_config_version(PROTOCOL) == v1  # deterministic
    changed = {**PROTOCOL, "instruments": {"cognitiveOverlay": {"stuck": {"enabled": False}}}}
    assert enrollment.capture_config_version(changed) != v1


def test_build_capture_config_carries_derived_overlay_settings():
    cfg = enrollment.build_capture_config(PROTOCOL, "P03", "ai-assisted")
    assert cfg["producer"] == "overlay"
    assert cfg["captureConfigVersion"] == enrollment.capture_config_version(PROTOCOL)
    assert cfg["settings"]["cognitiveOverlay.participantId"] == "P03"
    assert cfg["settings"]["cognitiveOverlay.stuck.enabled"] is True
```

- [ ] **Step 2: Run to verify failure.**
  Run: `uv run pytest middleware/tests/test_enrollment.py -q -k "connection or capture_config"`
  Expected: FAIL — `ModuleNotFoundError: No module named 'middleware.enrollment'`.

- [ ] **Step 3: Implement.** Create `middleware/src/middleware/enrollment.py`:

```python
"""Pure helpers for the live capture link (FR-INST-20/21, FR-ING-7).

No FastAPI/DB state here — the routes in ``app.py`` call these and own the
session. Keeping the token/config/consent logic pure makes it table-testable
(the FR-ETH-4 / authz pattern).
"""

import json
from hashlib import sha256

from protocol.derive import derive_overlay_settings


def connection_string(base_url: str, token: str) -> str:
    """The copy-safe string a participant pastes: ``serverUrl#token``.

    The base URL never contains ``#`` and the token is URL-safe base64, so a
    single ``#`` split reverses this unambiguously on the extension side.
    """
    return f"{base_url.rstrip('/')}#{token}"


def capture_config_version(protocol: dict) -> str:
    """A 12-char content hash of the protocol's instruments block.

    Changes iff the derived capture config changes (wall #5). Stateless, so
    the redeem and capture-config routes compute the same value.
    """
    blob = json.dumps(
        protocol.get("instruments", {}), sort_keys=True, separators=(",", ":")
    )
    return sha256(blob.encode()).hexdigest()[:12]


def build_capture_config(
    protocol: dict, participant_id: str, condition: str, producer: str = "overlay"
) -> dict:
    """The versioned, protocol-derived capture config for one producer.

    ``overlay`` returns the flat ``cognitiveOverlay.*`` settings the extension
    applies. Other producers (e.g. ``agent``) can be added behind the same
    envelope later; this phase serves ``overlay``.
    """
    if producer != "overlay":
        raise ValueError(f"unknown capture-config producer {producer!r}")
    settings = derive_overlay_settings(protocol, participant_id, condition)
    return {
        "captureConfigVersion": capture_config_version(protocol),
        "producer": producer,
        "settings": settings,
    }
```

- [ ] **Step 4: Run to verify pass.**
  Run: `uv run pytest middleware/tests/test_enrollment.py -q -k "connection or capture_config"`
  Expected: PASS (3 tests).

- [ ] **Step 5: Commit.**
  ```bash
  git add middleware/src/middleware/enrollment.py middleware/tests/test_enrollment.py
  git commit -m "MP-19 A2: enrollment helpers — connection string, config version, capture config (FR-INST-21)

Assisted-by: Claude (Opus 4.8)"
  ```

### Task A3: Consent statement + credential resolution helpers

**Files:**
- Modify: `middleware/src/middleware/enrollment.py`
- Test: `middleware/tests/test_enrollment.py` (append)

**Interfaces:**
- Produces:
  - `consent_statement(protocol: dict, condition: str) -> str` — a plain-language paragraph derived from the protocol (study title, condition, content policy, enabled-capture summary).
  - `content_policy(protocol: dict) -> str` — the agent content policy, default `"metadata-only"`.

- [ ] **Step 1: Write the failing tests.** Append:

```python
def test_content_policy_defaults_to_metadata_only():
    assert enrollment.content_policy(PROTOCOL) == "metadata-only"
    p = {**PROTOCOL, "instruments": {**PROTOCOL["instruments"], "agentCapture": {"contentPolicy": "redacted"}}}
    assert enrollment.content_policy(p) == "redacted"


def test_consent_statement_is_derived_and_names_the_policy():
    text = enrollment.consent_statement(PROTOCOL, "ai-assisted")
    assert "Pilot" in text  # study title
    assert "ai-assisted" in text  # condition
    assert "metadata-only" in text  # active content policy, stated verbatim (FR-AGENT-5)
    assert "raw code" in text.lower()  # the never-captured promise
```

- [ ] **Step 2: Run to verify failure.**
  Run: `uv run pytest middleware/tests/test_enrollment.py -q -k "policy or consent"`
  Expected: FAIL — `AttributeError: module 'middleware.enrollment' has no attribute 'content_policy'`.

- [ ] **Step 3: Implement.** Append to `middleware/src/middleware/enrollment.py`:

```python
#: Plain-language description of each agent content policy (FR-AGENT-5),
#: stated verbatim in the consent statement.
_POLICY_DESCRIPTIONS = {
    "metadata-only": "only sizes, counts, and timings of the conversation — never its text",
    "redacted": "the conversation text with string literals and long identifiers masked",
    "full": "the full conversation text",
}


def content_policy(protocol: dict) -> str:
    """The study's agent content policy (default metadata-only, the safest)."""
    agent = protocol.get("instruments", {}).get("agentCapture", {})
    return agent.get("contentPolicy", "metadata-only")


def consent_statement(protocol: dict, condition: str) -> str:
    """A deterministic, protocol-derived consent paragraph (wall #1, FR-AGENT-5).

    States what the study is, the condition, the active content policy verbatim,
    and the privacy-by-construction promise every instrument keeps.
    """
    title = protocol.get("study", {}).get("title", "this study")
    policy = content_policy(protocol)
    policy_desc = _POLICY_DESCRIPTIONS.get(policy, policy)
    instruments = ", ".join(sorted(protocol.get("instruments", {}).keys())) or "none"
    return (
        f"You are joining “{title}” in the {condition} condition. "
        f"While you work, this study captures aggregate signals from these "
        f"instruments: {instruments}. It never records raw code content, "
        f"keystrokes, or clipboard text — only sizes, shapes, timings, and "
        f"salted hashes. Agent-conversation capture is set to “{policy}”: "
        f"{policy_desc}. You appear in all data only as an anonymized ID. "
        f"You can stop the session at any time."
    )
```

- [ ] **Step 4: Run to verify pass.**
  Run: `uv run pytest middleware/tests/test_enrollment.py -q -k "policy or consent"`
  Expected: PASS.

- [ ] **Step 5: Commit.**
  ```bash
  git add middleware/src/middleware/enrollment.py middleware/tests/test_enrollment.py
  git commit -m "MP-19 A3: consent statement + content policy helpers (FR-AGENT-5)

Assisted-by: Claude (Opus 4.8)"
  ```

### Task A4: Mint / list / revoke endpoints

**Files:**
- Modify: `middleware/src/middleware/app.py` (add request models near the others ~line 255; add routes near the invitation routes ~line 2143; add a `study_protocol` helper inside `create_app`)
- Test: `middleware/tests/test_enrollment_routes.py` (create)

**Interfaces:**
- Consumes: `enrollment.connection_string`, `require_project_for_study`, `EnrollmentToken`, `StudyEvolution`, `study_protocol(s, study_id)`.
- Produces: routes `POST/GET /studies/{study_id}/enrollment/tokens`, `DELETE /enrollment/tokens/{id}`; a new capability `mint_token` (Role.RESEARCHER) added to `authz.CAPABILITIES` and `platform/src/lib/capabilities.ts` (the latter in Task C1).

- [ ] **Step 1: Add the `mint_token` capability.** In `middleware/src/middleware/authz.py`, add to the `CAPABILITIES` dict (after `run_recipe`):
  ```python
      # Mint/revoke enrollment (pairing) tokens for a study.
      "mint_token": Role.RESEARCHER,
  ```

- [ ] **Step 2: Write the failing test.** Create `middleware/tests/test_enrollment_routes.py`. Use the existing test app fixture pattern (grep `middleware/tests/` for how a study with ethics approval is set up; the shape below assumes a `client` + a helper that loads the pilot protocol and approves ethics — reuse whatever `test_evolution*.py` / `conftest.py` already provides):

```python
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
```

  > **Fixture note:** if `conftest.py` has no `client_ethics_ok`/`client_no_ethics`, add them there: build the app with the pilot protocol loaded, and for `client_ethics_ok` POST `/studies/pilot/ethics-approval` after compiling+approving a draft (follow `test_evolution.py`'s setup verbatim). Do not invent a new approval path.

- [ ] **Step 3: Run to verify failure.**
  Run: `uv run pytest middleware/tests/test_enrollment_routes.py -q`
  Expected: FAIL — 404 (routes absent).

- [ ] **Step 4: Add the request model + the `study_protocol` helper + the routes.**
  In `middleware/src/middleware/app.py`, add near the other `BaseModel`s (~line 255):
  ```python
  class MintTokensIn(BaseModel):
      count: int = 1
      grain: str = "participant"  # 'participant' | 'session'
  ```
  Inside `create_app`, after `check = _ProtocolCheck(protocol_doc)` (~line 305), add a helper that resolves a study's protocol (approved YAML wins; boot protocol is the single-facilitator fallback):
  ```python
  def study_protocol(s: Session, study_id: str) -> dict | None:
      import yaml

      from middleware.db import StudyEvolution

      evo = s.get(StudyEvolution, study_id)
      if evo is not None and evo.approved_yaml:
          return yaml.safe_load(evo.approved_yaml)
      if protocol_doc is not None and protocol_doc["study"]["id"] == study_id:
          return protocol_doc
      return None
  ```
  Add the routes near the invitation routes (~line 2143):
  ```python
  @app.post(
      "/studies/{study_id}/enrollment/tokens",
      dependencies=[Depends(require_project_for_study("mint_token"))],
  )
  def mint_enrollment_tokens(
      study_id: str,
      body: MintTokensIn,
      request: Request,
      s: Session = Depends(db),
  ) -> list[dict]:
      from datetime import timedelta as td

      from middleware.db import EnrollmentToken, StudyEvolution

      evo = s.get(StudyEvolution, study_id)
      if evo is None or not evo.ethics_approved_at:
          raise HTTPException(
              409,
              "Mint enrollment tokens only after the study clears its ethics "
              "gate — you cannot collect data before approval.",
          )
      protocol = study_protocol(s, study_id)
      if protocol is None:
          raise HTTPException(404, f"no protocol for study {study_id!r}")
      if body.grain not in {"participant", "session"}:
          raise HTTPException(400, "grain must be 'participant' or 'session'")
      conditions = protocol["conditions"]
      existing = s.scalars(
          select(EnrollmentToken).where(EnrollmentToken.study_id == study_id)
      ).all()
      start = len(existing)
      base = str(request.base_url).rstrip("/")
      expires = (clock() + td(days=30)).isoformat(timespec="milliseconds")
      out = []
      for i in range(body.count):
          n = start + i + 1
          pid = f"P{n:02d}"
          condition = conditions[(n - 1) % len(conditions)]
          token = secrets.token_urlsafe(32)
          row = EnrollmentToken(
              id=secrets.token_hex(8),
              study_id=study_id,
              participant_id=pid,
              condition=condition,
              grain=body.grain,
              token=token,
              expires_at=expires,
              created_at=now(),
          )
          s.add(row)
          out.append(
              {
                  "id": row.id,
                  "participantId": pid,
                  "condition": condition,
                  "grain": body.grain,
                  "connectionString": enrollment.connection_string(base, token),
                  "status": "unredeemed",
              }
          )
      s.commit()
      return out

  @app.get(
      "/studies/{study_id}/enrollment/tokens",
      dependencies=[Depends(require_project_for_study("view"))],
  )
  def list_enrollment_tokens(study_id: str, s: Session = Depends(db)) -> list[dict]:
      from middleware.db import EnrollmentToken

      rows = s.scalars(
          select(EnrollmentToken)
          .where(EnrollmentToken.study_id == study_id)
          .order_by(EnrollmentToken.participant_id)
      ).all()
      out = []
      for r in rows:
          if r.revoked_at:
              status = "revoked"
          elif r.redeemed_at:
              status = "paired"
          else:
              status = "unredeemed"
          out.append(
              {
                  "id": r.id,
                  "participantId": r.participant_id,
                  "condition": r.condition,
                  "grain": r.grain,
                  "status": status,
              }
          )
      return out

  @app.delete(
      "/enrollment/tokens/{token_id}",
      dependencies=[Depends(resolve_identity)],
  )
  def revoke_enrollment_token(token_id: str, s: Session = Depends(db)) -> dict:
      from middleware.db import EnrollmentToken

      row = s.get(EnrollmentToken, token_id)
      if row is None:
          raise HTTPException(404, "enrollment token not found")
      row.revoked_at = now()
      s.commit()
      return {"revoked": token_id}
  ```
  Ensure `from fastapi import Request` is imported at the top of `app.py` (add to the existing fastapi import line if absent), and `from middleware import enrollment`.
  > **Status note:** this list derives `unredeemed`/`paired`/`revoked` from token state. The `streaming` status (events actually arriving) is a live-feed enhancement — join the existing session-status feed (FR-DASH-3, `GET /studies/{id}/status`) in a follow-up; `paired` is the correct baseline until then. The client type keeps `"streaming"` in its union so no client change is needed when it lands.

- [ ] **Step 5: Run to verify pass.**
  Run: `uv run pytest middleware/tests/test_enrollment_routes.py -q`
  Expected: PASS (3 tests).

- [ ] **Step 6: Commit.**
  ```bash
  git add middleware/src/middleware/app.py middleware/src/middleware/authz.py middleware/tests/test_enrollment_routes.py middleware/tests/conftest.py
  git commit -m "MP-19 A4: mint/list/revoke enrollment tokens, ethics- and role-gated (FR-ING-7)

Assisted-by: Claude (Opus 4.8)"
  ```

### Task A5: The `/pair/redeem` endpoint

**Files:**
- Modify: `middleware/src/middleware/app.py` (request model + public route)
- Test: `middleware/tests/test_enrollment_routes.py` (append)

**Interfaces:**
- Consumes: `EnrollmentToken`, `study_protocol`, `enrollment.build_capture_config`, `enrollment.consent_statement`, `enrollment.content_policy`.
- Produces: `POST /pair/redeem` returning `{participantId, condition, sessionCredential, ingestEndpoint, captureConfig, consentStatement, contentPolicy}`.

- [ ] **Step 1: Write the failing tests.** Append to `middleware/tests/test_enrollment_routes.py`:

```python
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
    assert "Pilot" in body["consentStatement"]


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
```

- [ ] **Step 2: Run to verify failure.**
  Run: `uv run pytest middleware/tests/test_enrollment_routes.py -q -k redeem`
  Expected: FAIL — 404.

- [ ] **Step 3: Implement.** Add the model near the others:
  ```python
  class RedeemIn(BaseModel):
      token: str
  ```
  Add the public route (no project dependency — the token is the credential):
  ```python
  @app.post("/pair/redeem")
  def pair_redeem(body: RedeemIn, request: Request, s: Session = Depends(db)) -> dict:
      from middleware.db import EnrollmentToken, StudyEvolution

      row = s.scalar(
          select(EnrollmentToken).where(EnrollmentToken.token == body.token)
      )
      if row is None or row.revoked_at:
          raise HTTPException(410, "this connection link is invalid or has been revoked")
      try:
          if datetime.fromisoformat(row.expires_at) < clock():
              raise HTTPException(410, "this connection link has expired — ask for a new one")
      except (ValueError, TypeError):
          pass
      if row.grain == "session" and row.redeemed_at:
          raise HTTPException(410, "this single-use connection link has already been used")
      evo = s.get(StudyEvolution, row.study_id)
      if evo is None or not evo.ethics_approved_at:
          raise HTTPException(409, "this study has not cleared its ethics gate")
      protocol = study_protocol(s, row.study_id)
      if protocol is None:
          raise HTTPException(404, "no protocol for this study")
      if not row.credential:
          row.credential = secrets.token_urlsafe(32)
      if row.grain == "session":
          row.redeemed_at = now()
      elif not row.redeemed_at:
          row.redeemed_at = now()
      s.commit()
      base = str(request.base_url).rstrip("/")
      return {
          "participantId": row.participant_id,
          "condition": row.condition,
          "sessionCredential": row.credential,
          "ingestEndpoint": f"{base}/ingest/events",
          "captureConfig": enrollment.build_capture_config(
              protocol, row.participant_id, row.condition
          ),
          "consentStatement": enrollment.consent_statement(protocol, row.condition),
          "contentPolicy": enrollment.content_policy(protocol),
      }
  ```

- [ ] **Step 4: Run to verify pass.**
  Run: `uv run pytest middleware/tests/test_enrollment_routes.py -q -k redeem`
  Expected: PASS (3 tests).

- [ ] **Step 5: Commit.**
  ```bash
  git add middleware/src/middleware/app.py middleware/tests/test_enrollment_routes.py
  git commit -m "MP-19 A5: /pair/redeem — token -> credential + config + consent (FR-INST-20)

Assisted-by: Claude (Opus 4.8)"
  ```

### Task A6: The `/capture-config` endpoint (credential-gated)

**Files:**
- Modify: `middleware/src/middleware/app.py` (helper `resolve_credential` + route)
- Test: `middleware/tests/test_enrollment_routes.py` (append)

**Interfaces:**
- Produces: `resolve_credential(s, authorization) -> EnrollmentToken | None` (reused by Task A7); `GET /studies/{study_id}/capture-config` requiring the session credential, returning the same `captureConfig` shape as redeem.

- [ ] **Step 1: Write the failing test.** Append:

```python
def test_capture_config_matches_redeem_and_requires_credential(client_ethics_ok: TestClient):
    tok = client_ethics_ok.post(
        "/studies/pilot/enrollment/tokens", json={"count": 1, "grain": "participant"}
    ).json()[0]
    raw = tok["connectionString"].split("#", 1)[1]
    cred = client_ethics_ok.post("/pair/redeem", json={"token": raw}).json()["sessionCredential"]

    assert client_ethics_ok.get("/studies/pilot/capture-config").status_code == 401
    r = client_ethics_ok.get(
        "/studies/pilot/capture-config",
        headers={"authorization": f"Bearer {cred}"},
    )
    assert r.status_code == 200
    assert r.json()["settings"]["cognitiveOverlay.participantId"] == "P01"
```

- [ ] **Step 2: Run to verify failure.**
  Run: `uv run pytest middleware/tests/test_enrollment_routes.py -q -k capture_config`
  Expected: FAIL — 404.

- [ ] **Step 3: Implement.** Inside `create_app`, add the credential resolver and the route:
  ```python
  def resolve_credential(s: Session, authorization: str):
      """Return the EnrollmentToken for a valid Bearer session credential, else
      None. Never raises — callers decide whether absence is fatal."""
      from middleware.db import EnrollmentToken

      if not authorization.startswith("Bearer "):
          return None
      cred = authorization.removeprefix("Bearer ").strip()
      if not cred:
          return None
      row = s.scalar(select(EnrollmentToken).where(EnrollmentToken.credential == cred))
      if row is None or row.revoked_at:
          return None
      try:
          if datetime.fromisoformat(row.expires_at) < clock():
              return None
      except (ValueError, TypeError):
          pass
      return row

  @app.get("/studies/{study_id}/capture-config")
  def get_capture_config(
      study_id: str,
      authorization: str = Header(default=""),
      s: Session = Depends(db),
  ) -> dict:
      row = resolve_credential(s, authorization)
      if row is None or row.study_id != study_id:
          raise HTTPException(401, "a valid session credential is required")
      protocol = study_protocol(s, study_id)
      if protocol is None:
          raise HTTPException(404, "no protocol for this study")
      return enrollment.build_capture_config(protocol, row.participant_id, row.condition)
  ```
  Confirm `Header` is imported from fastapi at the top of `app.py` (it is used by authz; add if missing).

- [ ] **Step 4: Run to verify pass.**
  Run: `uv run pytest middleware/tests/test_enrollment_routes.py -q -k capture_config`
  Expected: PASS.

- [ ] **Step 5: Commit.**
  ```bash
  git add middleware/src/middleware/app.py middleware/tests/test_enrollment_routes.py
  git commit -m "MP-19 A6: /capture-config, credential-gated session-boundary re-pull (FR-INST-21)

Assisted-by: Claude (Opus 4.8)"
  ```

### Task A7: Authenticated-but-non-blocking ingest

**Files:**
- Modify: `middleware/src/middleware/app.py` (the `ingest_events` handler ~line 406; update `auth.py` docstring)
- Test: `middleware/tests/test_enrollment_routes.py` (append)

**Interfaces:**
- Consumes: `resolve_credential` (Task A6).
- Produces: `POST /ingest/events` accepting an optional `Authorization` header — server-stamps join keys from a valid credential, flags mismatches/absent-but-present-bearer, never 401, never drops.

- [ ] **Step 1: Write the failing tests.** Append:

```python
def _events(pid, cond):
    return {"events": [{"sessionId": "s1", "seq": 0, "v": 3, "participantId": pid, "condition": cond, "type": "session_start"}]}


def test_credentialed_ingest_server_stamps_join_keys(client_ethics_ok: TestClient):
    tok = client_ethics_ok.post(
        "/studies/pilot/enrollment/tokens", json={"count": 1, "grain": "participant"}
    ).json()[0]
    raw = tok["connectionString"].split("#", 1)[1]
    cred = client_ethics_ok.post("/pair/redeem", json={"token": raw}).json()["sessionCredential"]
    # Client LIES about being P08; the credential says P01 -> server overrides.
    r = client_ethics_ok.post(
        "/ingest/events",
        json=_events("P08", "unassisted"),
        headers={"authorization": f"Bearer {cred}"},
    )
    assert r.status_code == 200
    row = client_ethics_ok.get("/sessions/s1/events").json()["events"][0]
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
    row = client_ethics_ok.get("/sessions/s1/events").json()["events"][0]
    assert "unauthenticated" in row["flags"]


def test_credential_never_persists_into_stored_rows(client_ethics_ok: TestClient):
    tok = client_ethics_ok.post(
        "/studies/pilot/enrollment/tokens", json={"count": 1, "grain": "participant"}
    ).json()[0]
    raw = tok["connectionString"].split("#", 1)[1]
    cred = client_ethics_ok.post("/pair/redeem", json={"token": raw}).json()["sessionCredential"]
    client_ethics_ok.post(
        "/ingest/events", json=_events("P01", "ai-assisted"),
        headers={"authorization": f"Bearer {cred}"},
    )
    dump = client_ethics_ok.get("/sessions/s1/events").text
    assert cred not in dump  # the secret never leaks into stored data (wall #7)
```

  > **Note:** the exact read endpoint (`/sessions/s1/events`) and its JSON shape (`{"events": [...]}` with a `flags` list per row) exist today (`app.py:589`). If the shape differs, adjust the assertions to the real one — do not change the ingest contract.

- [ ] **Step 2: Run to verify failure.**
  Run: `uv run pytest middleware/tests/test_enrollment_routes.py -q -k "stamp or unauthenticated or persists"`
  Expected: FAIL — client keys not overridden; no such flags.

- [ ] **Step 3: Implement.** Modify `ingest_events` (`app.py:406`) to take the header and stamp/flag. Replace the signature and the per-event body:
  ```python
  @app.post("/ingest/events")
  def ingest_events(
      batch: EventBatch | list[StudyEventIn],
      authorization: str = Header(default=""),
      s: Session = Depends(db),
  ) -> dict:
      events = batch if isinstance(batch, list) else batch.events
      batch_source = "" if isinstance(batch, list) else batch.source
      received = now()
      cred_row = resolve_credential(s, authorization)
      bearer_present = authorization.startswith("Bearer ")
      flagged = 0
      rows = []
      for e in events:
          pid, cond = e.participantId, e.condition
          extra_flags: list[str] = []
          if cred_row is not None:
              if (e.participantId and e.participantId != cred_row.participant_id) or (
                  e.condition and e.condition != cred_row.condition
              ):
                  extra_flags.append("credential-mismatch")
              pid, cond = cred_row.participant_id, cred_row.condition  # server-stamp
          elif bearer_present:
              extra_flags.append("unauthenticated")  # bearer sent, none valid
          flags = check.flags_for(pid, cond, e.v) + extra_flags
          flagged += bool(flags)
          rows.append(
              dict(
                  session_id=e.sessionId,
                  source=e.source or batch_source or DEFAULT_SOURCE,
                  seq=e.seq,
                  participant_id=pid,
                  condition=cond,
                  v=e.v,
                  ts=e.ts,
                  mono=e.mono,
                  type=e.type,
                  payload=e.payload,
                  flags=flags,
                  received_at=received,
              )
          )
      # ... (the existing insert + log_finding + return block is unchanged)
  ```
  Keep the rest of the handler (the `sqlite_insert(...).on_conflict_do_nothing(...)`, `log_finding`, and return dict) exactly as it is today.
  Update the `auth.py` module docstring line "Ingest is never authenticated in any mode" to: *"Ingest accepts an optional per-session credential (FR-ING-7): a valid one server-stamps the join keys; an absent or invalid one still stores the row, flagged — ingest never returns 401 and never drops (NFR-1)."*

- [ ] **Step 4: Run to verify pass.**
  Run: `uv run pytest middleware/tests/test_enrollment_routes.py -q`
  Expected: PASS (all enrollment-route tests).

- [ ] **Step 5: Full backend gate + commit.**
  Run: `uv run pytest -q && uv run ruff check .`
  Expected: PASS, no lint errors.
  ```bash
  git add middleware/src/middleware/app.py middleware/src/middleware/auth.py middleware/tests/test_enrollment_routes.py
  git commit -m "MP-19 A7: authenticated-but-non-blocking ingest — server-stamp + flag, never 401/drop (FR-ING-7)

Assisted-by: Claude (Opus 4.8)"
  ```

---

## Part B — Extension (Cognitive Overlay)

### Task B1: Core — connection-string codec

**Files:**
- Create: `extension/src/core/connectionString.ts`
- Test: `extension/test/connectionString.test.ts`

**Interfaces:**
- Produces: `interface Connection { serverUrl: string; token: string }`; `decodeConnectionString(raw: string): Connection`; `class ConnectionStringError extends Error`.

- [ ] **Step 1: Write the failing test.** Create `extension/test/connectionString.test.ts`:

```ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  decodeConnectionString,
  ConnectionStringError,
} from '../src/core/connectionString';

test('decodes a well-formed connection string', () => {
  const c = decodeConnectionString('https://study.lab.example#Ab3xToken');
  assert.equal(c.serverUrl, 'https://study.lab.example');
  assert.equal(c.token, 'Ab3xToken');
});

test('strips a trailing slash from the server URL', () => {
  assert.equal(
    decodeConnectionString('https://s.example/#tok').serverUrl,
    'https://s.example',
  );
});

test('rejects a string with no separator', () => {
  assert.throws(() => decodeConnectionString('https://s.example'), ConnectionStringError);
});

test('rejects a non-http server URL', () => {
  assert.throws(() => decodeConnectionString('ftp://s.example#tok'), ConnectionStringError);
});

test('rejects an empty token', () => {
  assert.throws(() => decodeConnectionString('https://s.example#'), ConnectionStringError);
});
```

- [ ] **Step 2: Run to verify failure.**
  Run: `cd extension && npx tsx --test test/connectionString.test.ts` (or the repo's configured test runner — check `package.json` `scripts.test`; use that command form).
  Expected: FAIL — module not found.

- [ ] **Step 3: Implement.** Create `extension/src/core/connectionString.ts`:

```ts
/**
 * The connection string a participant pastes to enroll their IDE: the copy-
 * safe `serverUrl#token`. Portable core (no vscode). The middleware mints it;
 * we split on the last `#` (base URLs never contain `#`; tokens are URL-safe
 * base64).
 */

export interface Connection {
  /** Middleware base URL, trailing slash stripped. */
  serverUrl: string;
  /** The raw pairing token (what /pair/redeem expects). */
  token: string;
}

export class ConnectionStringError extends Error {}

export function decodeConnectionString(raw: string): Connection {
  const s = raw.trim();
  const i = s.lastIndexOf('#');
  if (i <= 0) {
    throw new ConnectionStringError(
      'That does not look like a connection string — paste the whole line your researcher gave you.',
    );
  }
  const serverUrl = s.slice(0, i).replace(/\/$/, '');
  const token = s.slice(i + 1);
  if (!/^https?:\/\//.test(serverUrl)) {
    throw new ConnectionStringError('The connection string must start with http(s)://');
  }
  if (!token) {
    throw new ConnectionStringError('The connection string is missing its token.');
  }
  return { serverUrl, token };
}
```

- [ ] **Step 4: Run to verify pass.**
  Run: `cd extension && npx tsx --test test/connectionString.test.ts`
  Expected: PASS (5 tests).

- [ ] **Step 5: Commit.**
  ```bash
  git add extension/src/core/connectionString.ts extension/test/connectionString.test.ts
  git commit -m "MP-19 B1: connection-string codec (core, FR-INST-20)

Assisted-by: Claude (Opus 4.8)"
  ```

### Task B2: Core — capture-config applier

**Files:**
- Create: `extension/src/core/captureConfig.ts`
- Test: `extension/test/captureConfig.test.ts`

**Interfaces:**
- Produces: `interface CaptureConfig { captureConfigVersion: string; producer: string; settings: Record<string, unknown> }`; `overlayFlags(cfg: CaptureConfig): Record<string, unknown>` (the flat `cognitiveOverlay.*` keys minus the prefix); `configChanged(applied: string | undefined, incoming: string): boolean`.

- [ ] **Step 1: Write the failing test.** Create `extension/test/captureConfig.test.ts`:

```ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { overlayFlags, configChanged, CaptureConfig } from '../src/core/captureConfig';

const CFG: CaptureConfig = {
  captureConfigVersion: 'abc123',
  producer: 'overlay',
  settings: {
    'cognitiveOverlay.participantId': 'P01',
    'cognitiveOverlay.stuck.enabled': true,
    'cognitiveOverlay.behavior.captureClipboard': false,
  },
};

test('overlayFlags strips the cognitiveOverlay prefix', () => {
  const f = overlayFlags(CFG);
  assert.equal(f['participantId'], 'P01');
  assert.equal(f['stuck.enabled'], true);
  assert.equal(f['behavior.captureClipboard'], false);
  assert.equal(Object.hasOwn(f, 'cognitiveOverlay.participantId'), false);
});

test('configChanged is true only when the version differs', () => {
  assert.equal(configChanged(undefined, 'abc123'), true);
  assert.equal(configChanged('abc123', 'abc123'), false);
  assert.equal(configChanged('old', 'abc123'), true);
});
```

- [ ] **Step 2: Run to verify failure.**
  Run: `cd extension && npx tsx --test test/captureConfig.test.ts`
  Expected: FAIL — module not found.

- [ ] **Step 3: Implement.** Create `extension/src/core/captureConfig.ts`:

```ts
/**
 * The versioned, protocol-derived capture config the IDE receives on pair and
 * re-pulls at each session start. Portable core: this module only shapes the
 * data — WHEN it is applied (a session boundary, never mid-run: wall #6) is
 * the adapter's job.
 */

export interface CaptureConfig {
  captureConfigVersion: string;
  producer: string;
  /** Flat `cognitiveOverlay.*` settings from the middleware. */
  settings: Record<string, unknown>;
}

const PREFIX = 'cognitiveOverlay.';

/** The capture flags to apply, with the `cognitiveOverlay.` prefix removed. */
export function overlayFlags(cfg: CaptureConfig): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(cfg.settings)) {
    if (k.startsWith(PREFIX)) out[k.slice(PREFIX.length)] = v;
  }
  return out;
}

/** True if the incoming config differs from what is already applied. */
export function configChanged(applied: string | undefined, incoming: string): boolean {
  return applied !== incoming;
}
```

- [ ] **Step 4: Run to verify pass.**
  Run: `cd extension && npx tsx --test test/captureConfig.test.ts`
  Expected: PASS.

- [ ] **Step 5: Commit.**
  ```bash
  git add extension/src/core/captureConfig.ts extension/test/captureConfig.test.ts
  git commit -m "MP-19 B2: capture-config applier (core, FR-INST-21)

Assisted-by: Claude (Opus 4.8)"
  ```

### Task B3: Core — pre-flight summary

**Files:**
- Create: `extension/src/core/preflight.ts`
- Test: `extension/test/preflight.test.ts`

**Interfaces:**
- Consumes: `overlayFlags` output shape (`Record<string, unknown>`).
- Produces: `interface PreflightItem { key: string; label: string; on: boolean }`; `preflightSummary(flags: Record<string, unknown>): PreflightItem[]`.

- [ ] **Step 1: Write the failing test.** Create `extension/test/preflight.test.ts`:

```ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { preflightSummary } from '../src/core/preflight';

test('summarizes the known capture toggles as on/off', () => {
  const items = preflightSummary({
    'stuck.enabled': true,
    'behavior.captureClipboard': false,
    'behavior.captureEditBursts': true,
  });
  const byKey = Object.fromEntries(items.map((i) => [i.key, i]));
  assert.equal(byKey['stuck.enabled'].on, true);
  assert.equal(byKey['stuck.enabled'].label, 'Stuck detection');
  assert.equal(byKey['behavior.captureClipboard'].on, false);
});

test('a toggle absent from the config is reported off', () => {
  const items = preflightSummary({});
  assert.ok(items.every((i) => i.on === false));
  assert.ok(items.length > 0);
});
```

- [ ] **Step 2: Run to verify failure.**
  Run: `cd extension && npx tsx --test test/preflight.test.ts`
  Expected: FAIL — module not found.

- [ ] **Step 3: Implement.** Create `extension/src/core/preflight.ts`:

```ts
/**
 * The "will capture / will not capture" summary shown before a session's clock
 * arms (FR-INST-21). A forgotten toggle is caught here, before any task data is
 * recorded — the hard-wall alternative to mid-session reconfiguration (wall #6).
 */

export interface PreflightItem {
  /** The `cognitiveOverlay.`-stripped flag key. */
  key: string;
  /** Plain-language name for the participant/researcher. */
  label: string;
  on: boolean;
}

/** The capture toggles worth surfacing, in display order. Extend as instruments
 * are added; unknown flags in the config are ignored, missing ones read off. */
const TRACKED: { key: string; label: string }[] = [
  { key: 'stuck.enabled', label: 'Stuck detection' },
  { key: 'behavior.captureEditBursts', label: 'Edit bursts' },
  { key: 'behavior.captureAiLifecycle', label: 'AI suggestion lifecycle' },
  { key: 'behavior.captureClipboard', label: 'Paste events' },
  { key: 'behavior.captureVisibleRanges', label: 'Scroll coverage' },
  { key: 'behavior.captureFocus', label: 'Focus switches' },
  { key: 'behavior.captureHeartbeat', label: 'Active/idle time' },
  { key: 'behavior.captureAttention', label: 'Time-on-code' },
];

export function preflightSummary(flags: Record<string, unknown>): PreflightItem[] {
  return TRACKED.map(({ key, label }) => ({ key, label, on: flags[key] === true }));
}
```

- [ ] **Step 4: Run to verify pass.**
  Run: `cd extension && npx tsx --test test/preflight.test.ts`
  Expected: PASS.

- [ ] **Step 5: Commit.**
  ```bash
  git add extension/src/core/preflight.ts extension/test/preflight.test.ts
  git commit -m "MP-19 B3: capture pre-flight summary (core, FR-INST-21)

Assisted-by: Claude (Opus 4.8)"
  ```

### Task B4: Core — consent gate

**Files:**
- Create: `extension/src/core/consentGate.ts`
- Test: `extension/test/consentGate.test.ts`

**Interfaces:**
- Produces: `class ConsentGate { constructor(statement: string, policy: string); readonly statement: string; readonly policy: string; get accepted(): boolean; acknowledge(): void; assertAccepted(): void }`; `class ConsentNotGivenError extends Error`.

- [ ] **Step 1: Write the failing test.** Create `extension/test/consentGate.test.ts`:

```ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ConsentGate, ConsentNotGivenError } from '../src/core/consentGate';

test('blocks until acknowledged, then allows', () => {
  const g = new ConsentGate('You are joining...', 'metadata-only');
  assert.equal(g.accepted, false);
  assert.throws(() => g.assertAccepted(), ConsentNotGivenError);
  g.acknowledge();
  assert.equal(g.accepted, true);
  assert.doesNotThrow(() => g.assertAccepted());
});

test('carries the statement and policy verbatim', () => {
  const g = new ConsentGate('Statement text', 'redacted');
  assert.equal(g.statement, 'Statement text');
  assert.equal(g.policy, 'redacted');
});
```

- [ ] **Step 2: Run to verify failure.**
  Run: `cd extension && npx tsx --test test/consentGate.test.ts`
  Expected: FAIL — module not found.

- [ ] **Step 3: Implement.** Create `extension/src/core/consentGate.ts`:

```ts
/**
 * The consent acknowledgment gate (FR-ETH-1, FR-AGENT-5). No event may leave
 * the machine until the participant accepts the protocol-derived consent
 * statement and its content policy. Portable core: the adapter renders the
 * statement and calls acknowledge().
 */

export class ConsentNotGivenError extends Error {}

export class ConsentGate {
  private _accepted = false;

  constructor(
    readonly statement: string,
    readonly policy: string,
  ) {}

  get accepted(): boolean {
    return this._accepted;
  }

  acknowledge(): void {
    this._accepted = true;
  }

  assertAccepted(): void {
    if (!this._accepted) {
      throw new ConsentNotGivenError('capture may not start before consent is acknowledged');
    }
  }
}
```

- [ ] **Step 4: Run to verify pass.**
  Run: `cd extension && npx tsx --test test/consentGate.test.ts`
  Expected: PASS.

- [ ] **Step 5: Commit.**
  ```bash
  git add extension/src/core/consentGate.ts extension/test/consentGate.test.ts
  git commit -m "MP-19 B4: consent gate (core, FR-ETH-1/FR-AGENT-5)

Assisted-by: Claude (Opus 4.8)"
  ```

### Task B5: `HttpSink` sends the session credential

**Files:**
- Modify: `extension/src/vscode/sinks.ts` (the `HttpSink` class, ~lines 99-164)
- Test: `extension/test/sinks.test.ts` (append — follow the existing fetch-mock pattern there)

**Interfaces:**
- Consumes: nothing new.
- Produces: `HttpSink` constructor gains a 3rd optional param `credential?: string`; when set, requests carry `authorization: Bearer <credential>`.

- [ ] **Step 1: Write the failing test.** Append to `extension/test/sinks.test.ts` (mirror how existing tests stub `globalThis.fetch`; capture the headers):

```ts
test('HttpSink attaches the session credential as a bearer when set', async () => {
  const seen: Record<string, string> = {};
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (_url: string, init: RequestInit) => {
    Object.assign(seen, init.headers as Record<string, string>);
    return { ok: true, status: 200 } as Response;
  }) as typeof fetch;
  try {
    const sink = new HttpSink('http://x/ingest/events', 5000, 'cred-xyz');
    sink.write({ v: 3, ts: '', mono: 0, sessionId: 's', participantId: 'P01', condition: 'ai-assisted', seq: 0, type: 'session_start', payload: {} });
    await sink.flush();
    assert.equal(seen['authorization'], 'Bearer cred-xyz');
  } finally {
    globalThis.fetch = originalFetch;
  }
});
```

- [ ] **Step 2: Run to verify failure.**
  Run: `cd extension && npx tsx --test test/sinks.test.ts`
  Expected: FAIL — `seen['authorization']` undefined (3rd param ignored).

- [ ] **Step 3: Implement.** In `extension/src/vscode/sinks.ts`, update the `HttpSink` constructor and the `fetch` headers:
  ```ts
    constructor(
      private readonly endpoint: string,
      flushIntervalMs = 5_000,
      private readonly credential?: string,
    ) {
      this.timer = setInterval(() => void this.flush(), flushIntervalMs);
    }
  ```
  In `flush()`, replace the `headers` object in the `fetch` call:
  ```ts
        const headers: Record<string, string> = { 'content-type': 'application/json' };
        if (this.credential) headers['authorization'] = `Bearer ${this.credential}`;
        const res = await fetch(this.endpoint, {
          method: 'POST',
          headers,
          body: JSON.stringify({ source: 'cognitive-overlay', events: batch }),
          signal: ctrl.signal,
        });
  ```

- [ ] **Step 4: Run to verify pass.**
  Run: `cd extension && npx tsx --test test/sinks.test.ts`
  Expected: PASS.

- [ ] **Step 5: Commit.**
  ```bash
  git add extension/src/vscode/sinks.ts extension/test/sinks.test.ts
  git commit -m "MP-19 B5: HttpSink sends the session credential bearer (FR-ING-7)

Assisted-by: Claude (Opus 4.8)"
  ```

### Task B6: Adapter — the `connectToStudy` command + session-boundary apply

**Files:**
- Create: `extension/src/vscode/pairing.ts` (the command + redeem transport + config-apply, using the core modules)
- Modify: `extension/src/vscode/extension.ts` (register the command; on session start, if paired, re-pull `/capture-config` and apply before arming the clock)
- Modify: `extension/package.json` (`contributes.commands`: add `cognitiveOverlay.connectToStudy`)

**Interfaces:**
- Consumes: `decodeConnectionString`, `CaptureConfig`/`overlayFlags`, `preflightSummary`, `ConsentGate`, `HttpSink` (credential param).
- Produces: `registerPairing(context: vscode.ExtensionContext): vscode.Disposable`; persists `credential`, `serverUrl`, resolved `participantId`/`condition`, and `captureConfigVersion` to `context.secrets` / workspace state; writes the resolved join keys + endpoint into the `cognitiveOverlay.*` settings the session reads.

> This is an integration task: VS Code APIs cannot run under `node:test`. Its automated coverage is the core-module tests (B1–B4) plus the build/typecheck gate; behavior is verified by the walkthrough in the final task. Write real, compiling code — no placeholders.

- [ ] **Step 1: Implement the pairing command.** Create `extension/src/vscode/pairing.ts`:

```ts
import * as vscode from 'vscode';
import { decodeConnectionString } from '../core/connectionString';
import { CaptureConfig, overlayFlags, configChanged } from '../core/captureConfig';
import { preflightSummary } from '../core/preflight';
import { ConsentGate } from '../core/consentGate';

const SECRET_CRED = 'cognitiveOverlay.sessionCredential';
const STATE_SERVER = 'cognitiveOverlay.serverUrl';
const STATE_VERSION = 'cognitiveOverlay.captureConfigVersion';

interface RedeemResult {
  participantId: string;
  condition: string;
  sessionCredential: string;
  ingestEndpoint: string;
  captureConfig: CaptureConfig;
  consentStatement: string;
  contentPolicy: string;
}

/** Identity/transport keys resolved from the redeem, NOT from the protocol —
 * applyConfig must never clobber them (else a session-start refresh would
 * reset the paired endpoint to the protocol's example value). */
const IDENTITY_KEYS = new Set(['participantId', 'condition', 'output.httpEndpoint']);

/** Apply a capture config's overlay flags into `cognitiveOverlay.*` settings
 * (workspace scope). Called only at a session boundary (wall #6). */
async function applyConfig(cfg: CaptureConfig): Promise<void> {
  const flags = overlayFlags(cfg);
  const conf = vscode.workspace.getConfiguration('cognitiveOverlay');
  for (const [key, value] of Object.entries(flags)) {
    if (IDENTITY_KEYS.has(key)) continue; // identity/endpoint come from the redeem
    await conf.update(key, value, vscode.ConfigurationTarget.Workspace);
  }
}

/** Re-pull the study's capture config at a session boundary and apply it if the
 * version changed. No-op when unpaired. Returns the credential to use for the
 * session's HttpSink, or undefined when unpaired. */
export async function refreshConfigAtSessionStart(
  context: vscode.ExtensionContext,
): Promise<string | undefined> {
  const cred = await context.secrets.get(SECRET_CRED);
  const server = context.workspaceState.get<string>(STATE_SERVER);
  const studyId = vscode.workspace
    .getConfiguration('cognitiveOverlay')
    .get<string>('studyId');
  if (!cred || !server || !studyId) return cred ?? undefined;
  try {
    const res = await fetch(`${server}/studies/${studyId}/capture-config`, {
      headers: { authorization: `Bearer ${cred}` },
    });
    if (res.ok) {
      const cfg = (await res.json()) as CaptureConfig;
      const applied = context.workspaceState.get<string>(STATE_VERSION);
      if (configChanged(applied, cfg.captureConfigVersion)) {
        await applyConfig(cfg);
        await context.workspaceState.update(STATE_VERSION, cfg.captureConfigVersion);
      }
    }
  } catch {
    // Never block a session on a config refresh — last-applied config stands.
  }
  return cred;
}

export function registerPairing(context: vscode.ExtensionContext): vscode.Disposable {
  return vscode.commands.registerCommand('cognitiveOverlay.connectToStudy', async () => {
    const raw = await vscode.window.showInputBox({
      title: 'Connect to study',
      prompt: 'Paste the connection string your researcher gave you',
      ignoreFocusOut: true,
    });
    if (!raw) return;
    let conn;
    try {
      conn = decodeConnectionString(raw);
    } catch (e) {
      void vscode.window.showErrorMessage((e as Error).message);
      return;
    }
    let result: RedeemResult;
    try {
      const res = await fetch(`${conn.serverUrl}/pair/redeem`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ token: conn.token }),
      });
      if (!res.ok) {
        void vscode.window.showErrorMessage(
          `Could not connect: ${res.status === 410 ? 'this link is invalid, used, or expired.' : `server said ${res.status}.`}`,
        );
        return;
      }
      result = (await res.json()) as RedeemResult;
    } catch {
      void vscode.window.showErrorMessage('Could not reach the study server. Check your connection.');
      return;
    }

    // Consent gate — show the statement + policy, require explicit acceptance.
    const gate = new ConsentGate(result.consentStatement, result.contentPolicy);
    const choice = await vscode.window.showInformationMessage(
      result.consentStatement,
      { modal: true },
      'I consent',
    );
    if (choice !== 'I consent') return;
    gate.acknowledge();

    // Persist identity + credential (SecretStorage for the secret) and apply config.
    await context.secrets.store(SECRET_CRED, result.sessionCredential);
    await context.workspaceState.update(STATE_SERVER, conn.serverUrl);
    await context.workspaceState.update(STATE_VERSION, result.captureConfig.captureConfigVersion);
    const conf = vscode.workspace.getConfiguration('cognitiveOverlay');
    await conf.update('participantId', result.participantId, vscode.ConfigurationTarget.Workspace);
    await conf.update('condition', result.condition, vscode.ConfigurationTarget.Workspace);
    await conf.update('output.httpEndpoint', result.ingestEndpoint, vscode.ConfigurationTarget.Workspace);
    await applyConfig(result.captureConfig);

    // Pre-flight summary (before any session starts).
    const items = preflightSummary(overlayFlags(result.captureConfig));
    const on = items.filter((i) => i.on).map((i) => i.label).join(', ') || 'nothing';
    void vscode.window.showInformationMessage(
      `Connected as ${result.participantId} (${result.condition}). This study will capture: ${on}. Run “Cognitive Overlay: Start session” when you're ready.`,
    );
  });
}
```

- [ ] **Step 2: Register the command + add `studyId` config + wire the session-start refresh.**
  In `extension/package.json` `contributes.commands`, add:
  ```json
  { "command": "cognitiveOverlay.connectToStudy", "title": "Connect to study", "category": "Cognitive Overlay" }
  ```
  In `contributes.configuration.properties`, add:
  ```json
  "cognitiveOverlay.studyId": { "type": "string", "default": "", "description": "The study this IDE is paired to (set automatically when you connect)." }
  ```
  In `extension/src/vscode/extension.ts` `activate()`, register the command:
  ```ts
  import { registerPairing, refreshConfigAtSessionStart } from './pairing';
  // ... inside activate(), alongside the other command registrations:
  context.subscriptions.push(registerPairing(context));
  ```
  In the session-start path (where the `HttpSink` is currently constructed from `output.httpEndpoint` ~`extension.ts:216`), call the refresh first and pass the credential into `HttpSink`:
  ```ts
  const credential = await refreshConfigAtSessionStart(context);
  // ... where HttpSink is constructed:
  const httpSink = endpoint ? new HttpSink(endpoint, 5000, credential) : undefined;
  ```
  (Locate the existing `new HttpSink(endpoint)` call and add the credential arg; keep the endpoint-empty-means-disabled behavior.)
  Also stamp the applied config version onto the session so a live study is
  replicable down to which metrics were on (spec §"How this completes the
  platform loop"). In the existing `environment_snapshot` emission (FR-INST-14,
  ~`extension.ts:185`), add `captureConfigVersion` to its payload:
  ```ts
  captureConfigVersion: context.workspaceState.get<string>('cognitiveOverlay.captureConfigVersion') ?? '',
  ```

- [ ] **Step 3: Typecheck + build gate.**
  Run: `cd extension && npm run check`
  Expected: PASS — typecheck, lint, format, and all `node:test` suites (including B1–B5) green.

- [ ] **Step 4: Commit.**
  ```bash
  git add extension/src/vscode/pairing.ts extension/src/vscode/extension.ts extension/package.json
  git commit -m "MP-19 B6: connectToStudy command + session-boundary config apply (FR-INST-20/21)

Assisted-by: Claude (Opus 4.8)"
  ```

### Task B7: Walkthrough + deep link

**Files:**
- Modify: `extension/package.json` (`contributes.walkthroughs`)
- Modify: `extension/src/vscode/extension.ts` (register a `UriHandler` for `vscode://hpi-research.cognitive-overlay/pair`)
- Modify: `extension/src/vscode/pairing.ts` (extract the redeem+consent+apply into an exported `pairFromConnectionString(context, raw)` the command and the URI handler both call — DRY)

**Interfaces:**
- Produces: `pairFromConnectionString(context: vscode.ExtensionContext, raw: string): Promise<void>`; a registered URI handler that reads `?c=<connectionString>` and calls it.

- [ ] **Step 1: Refactor the command body into a shared function.** In `pairing.ts`, move the body of the `connectToStudy` handler (from `decodeConnectionString` through the pre-flight message) into `export async function pairFromConnectionString(context, raw)`, and have the command call it. (Pure refactor; `npm run check` must stay green.)

- [ ] **Step 2: Register the URI handler.** In `extension/src/vscode/extension.ts` `activate()`:
  ```ts
  context.subscriptions.push(
    vscode.window.registerUriHandler({
      handleUri(uri: vscode.Uri) {
        const params = new URLSearchParams(uri.query);
        const c = params.get('c');
        if (uri.path === '/pair' && c) void pairFromConnectionString(context, c);
      },
    }),
  );
  ```
  Export `pairFromConnectionString` from `pairing.ts` and import it here.

- [ ] **Step 3: Add the walkthrough.** In `extension/package.json` `contributes`, add:
  ```json
  "walkthroughs": [
    {
      "id": "cognitiveOverlay.gettingStarted",
      "title": "Join a study",
      "description": "Connect your editor to a research study in one paste.",
      "steps": [
        {
          "id": "connect",
          "title": "Connect to your study",
          "description": "Paste the connection string your researcher gave you.\n[Connect to study](command:cognitiveOverlay.connectToStudy)",
          "media": { "markdown": "media/walkthrough-connect.md" }
        },
        {
          "id": "start",
          "title": "Start your session",
          "description": "Review what will be captured, then begin.\n[Start session](command:cognitiveOverlay.startSession)",
          "media": { "markdown": "media/walkthrough-start.md" }
        }
      ]
    }
  ]
  ```
  Create the two referenced markdown files `extension/media/walkthrough-connect.md` and `extension/media/walkthrough-start.md` with one short paragraph each (the walkthrough requires a media file per step). Example for `walkthrough-connect.md`:
  ```markdown
  # Connect to your study

  Your researcher will send you a single connection string. Paste it when
  prompted — your editor resolves the rest (who you are in the study, where
  data goes, and exactly what is captured). Nothing is typed by hand.
  ```

- [ ] **Step 4: Build gate.**
  Run: `cd extension && npm run check`
  Expected: PASS.

- [ ] **Step 5: Commit.**
  ```bash
  git add extension/package.json extension/src/vscode/extension.ts extension/src/vscode/pairing.ts extension/media/
  git commit -m "MP-19 B7: getting-started walkthrough + vscode:// deep link (FR-INST-20)

Assisted-by: Claude (Opus 4.8)"
  ```

---

## Part C — Platform (dashboard)

### Task C1: `mint_token` capability + enrollment API client methods

**Files:**
- Modify: `platform/src/lib/capabilities.ts` (add `mint_token`)
- Modify: `platform/src/lib/studyApi.ts` (real client methods) **and** the in-memory fake it falls back to (grep for where `createInvitation`/study methods are faked — add the same methods there so the offline shell works)
- Test: extend the platform verify harness if one exists (`platform/scripts/verify-shell.mjs`); otherwise rely on `npm run build` + the component render in C2.

**Interfaces:**
- Produces (client): `mintEnrollmentTokens(studyId: string, count: number, grain: 'participant' | 'session'): Promise<EnrollmentTokenView[]>`; `listEnrollmentTokens(studyId: string): Promise<EnrollmentTokenView[]>`; `revokeEnrollmentToken(studyId: string, tokenId: string): Promise<void>` (study-scoped path — the revoke route is `DELETE /studies/{studyId}/enrollment/tokens/{tokenId}`, gated by `mint_token`); `type EnrollmentTokenView = { id: string; participantId: string; condition: string; grain: string; status: 'unredeemed' | 'paired' | 'streaming' | 'revoked'; connectionString?: string }`.

- [ ] **Step 1: Add the capability.** In `platform/src/lib/capabilities.ts`, add `"mint_token"` to the `Capability` union and to `MATRIX`:
  ```ts
  export type Capability =
    | "view" | "contribute" | "apply_draft" | "run_recipe"
    | "freeze" | "manage_members" | "delete" | "mint_token";
  ```
  ```ts
  export const MATRIX: Record<Capability, Role> = {
    view: "viewer", contribute: "researcher", apply_draft: "researcher",
    run_recipe: "researcher", freeze: "owner", manage_members: "owner",
    delete: "owner", mint_token: "researcher",
  };
  ```

- [ ] **Step 2: Add the client type + methods.** In `platform/src/lib/studyApi.ts`, add the type and three methods, following the existing `fetch`/bearer pattern in that file:
  ```ts
  export type EnrollmentTokenView = {
    id: string;
    participantId: string;
    condition: string;
    grain: string;
    status: "unredeemed" | "paired" | "streaming" | "revoked";
    connectionString?: string;
  };

  // inside the study API object/class (mirror an existing POST/GET/DELETE method):
  async mintEnrollmentTokens(studyId: string, count: number, grain: "participant" | "session") {
    return this.post<EnrollmentTokenView[]>(`/studies/${studyId}/enrollment/tokens`, { count, grain });
  }
  async listEnrollmentTokens(studyId: string) {
    return this.get<EnrollmentTokenView[]>(`/studies/${studyId}/enrollment/tokens`);
  }
  async revokeEnrollmentToken(studyId: string, tokenId: string) {
    return this.del<{ revoked: string }>(`/studies/${studyId}/enrollment/tokens/${tokenId}`);
  }
  ```
  (Use the exact helper names this file already uses for GET/POST/DELETE — grep the file; do not invent `post`/`get`/`del` if the file names them differently.)

- [ ] **Step 3: Add the same methods to the in-memory fake.** Find the offline/in-memory backend (Phase 14 deviations note: an in-memory backend stands in when `VITE_API_BASE` is unset). Add `mintEnrollmentTokens`/`listEnrollmentTokens`/`revokeEnrollmentToken` returning seeded rows so the shell renders offline. Keep it minimal — a module-level array of `EnrollmentTokenView` with `connectionString` a fake `https://demo#P01`.

- [ ] **Step 4: Build gate.**
  Run: `cd platform && npm run build && npm run lint`
  Expected: PASS.

- [ ] **Step 5: Commit.**
  ```bash
  git add platform/src/lib/capabilities.ts platform/src/lib/studyApi.ts
  git commit -m "MP-19 C1: mint_token capability + enrollment API client (FR-DASH-10)

Assisted-by: Claude (Opus 4.8)"
  ```

### Task C2: The `EnrollmentPanel` component

**Files:**
- Create: `platform/src/components/enrollment/EnrollmentPanel.tsx`
- Create: `platform/src/components/enrollment/MintDialog.tsx`

**Interfaces:**
- Consumes: `useApi()`, `EnrollmentTokenView`, `hasRole`, shadcn `Dialog`/`Button`/`Input`, the `Copy`/`Check` icons.
- Produces: `EnrollmentPanel({ studyId, role }: { studyId: string; role: Role | null })`.

- [ ] **Step 1: Implement `MintDialog`.** Create `platform/src/components/enrollment/MintDialog.tsx` (mirror `InviteDialog`'s copy-link structure; the copy affordance copies the `connectionString`):

```tsx
import { useState } from "react";
import { Copy, Check } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useApi } from "@/lib/session";
import type { EnrollmentTokenView } from "@/lib/studyApi";
import { cn } from "@/lib/cn";

/* Mint pairing tokens for a study. Copy-link (here: copy connection string) is
 * the primary affordance — the participant pastes it into their IDE once. */
export function MintDialog({ studyId, onMinted }: { studyId: string; onMinted: () => void }) {
  const api = useApi();
  const [open, setOpen] = useState(false);
  const [count, setCount] = useState(1);
  const [grain, setGrain] = useState<"participant" | "session">("participant");
  const [minted, setMinted] = useState<EnrollmentTokenView[]>([]);
  const [copied, setCopied] = useState<string | null>(null);

  const submit = async () => {
    const rows = await api.mintEnrollmentTokens(studyId, count, grain);
    setMinted(rows);
    onMinted();
  };
  const copy = async (s: string, id: string) => {
    await navigator.clipboard.writeText(s);
    setCopied(id);
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) setMinted([]); }}>
      <DialogTrigger asChild>
        <Button size="sm" data-agent="mint-tokens">Mint links</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>Mint enrollment links</DialogTitle>
        <DialogDescription>
          Each participant pastes one link into their IDE to join the study. A
          participant link is reusable across their sessions; a session link is
          single-use.
        </DialogDescription>
        {minted.length === 0 ? (
          <div className="mt-4 flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="count">How many</Label>
              <Input id="count" type="number" min={1} max={100} value={count}
                onChange={(e) => setCount(Math.max(1, Number(e.target.value)))} />
            </div>
            <div className="flex flex-col gap-1">
              <Label>Grain</Label>
              <div className="flex gap-2">
                {(["participant", "session"] as const).map((g) => (
                  <button key={g} type="button" onClick={() => setGrain(g)}
                    className={cn("rounded-input border px-3 py-1 text-sm transition-colors duration-fast",
                      grain === g ? "border-accent bg-accent-soft text-accent" : "border-border text-text hover:bg-accent-soft")}>
                    {g === "participant" ? "Participant (reusable)" : "Session (single-use)"}
                  </button>
                ))}
              </div>
            </div>
            <Button onClick={submit} className="mt-1 self-start">Mint {count} link{count > 1 ? "s" : ""}</Button>
          </div>
        ) : (
          <div className="mt-4 flex flex-col gap-2">
            {minted.map((t) => (
              <div key={t.id} className="flex items-center gap-2 rounded-input border border-border bg-bg px-2 py-1.5">
                <span className="w-16 shrink-0 font-mono text-xs text-text">{t.participantId}</span>
                <span className="truncate font-mono text-xs text-text-muted">{t.connectionString}</span>
                <Button size="sm" variant="subtle" className="ml-auto shrink-0"
                  onClick={() => copy(t.connectionString ?? "", t.id)}>
                  {copied === t.id ? <Check aria-hidden /> : <Copy aria-hidden />}
                  {copied === t.id ? "Copied" : "Copy"}
                </Button>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Implement `EnrollmentPanel`.** Create `platform/src/components/enrollment/EnrollmentPanel.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useApi } from "@/lib/session";
import { hasRole, type Role } from "@/lib/capabilities";
import type { EnrollmentTokenView } from "@/lib/studyApi";
import { Button } from "@/components/ui/button";
import { MintDialog } from "./MintDialog";
import { cn } from "@/lib/cn";

const STATUS_STYLE: Record<string, string> = {
  unredeemed: "text-text-muted",
  paired: "text-accent",
  streaming: "text-accent",
  revoked: "text-unsourced line-through",
};

/* The study's enrollment surface (FR-DASH-10): mint pairing links, see who has
 * paired / is streaming, revoke. Lives inside the study workspace — running a
 * study is part of the study, not a separate tool. */
export function EnrollmentPanel({ studyId, role }: { studyId: string; role: Role | null }) {
  const api = useApi();
  const [rows, setRows] = useState<EnrollmentTokenView[]>([]);
  const canMint = hasRole(role, "mint_token");

  const load = () => void api.listEnrollmentTokens(studyId).then(setRows);
  useEffect(load, [studyId]);

  return (
    <div className="flex flex-col gap-4 p-4" data-agent="enrollment-panel">
      <div className="flex items-center gap-3">
        <h2 className="font-display text-lg text-text">Participants</h2>
        {canMint && <MintDialog studyId={studyId} onMinted={load} />}
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-text-muted">
          Mint a link for each participant; they paste it once and their editor joins the study.
        </p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-text-muted">
              <th className="py-1 font-medium">Participant</th>
              <th className="py-1 font-medium">Condition</th>
              <th className="py-1 font-medium">Grain</th>
              <th className="py-1 font-medium">Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.id} className="border-t border-border">
                <td className="py-1.5 font-mono">{t.participantId}</td>
                <td className="py-1.5">{t.condition}</td>
                <td className="py-1.5">{t.grain}</td>
                <td className={cn("py-1.5", STATUS_STYLE[t.status])}>{t.status}</td>
                <td className="py-1.5 text-right">
                  {canMint && t.status !== "revoked" && (
                    <Button size="sm" variant="ghost"
                      onClick={() => void api.revokeEnrollmentToken(studyId, t.id).then(load)}>
                      Revoke
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Build gate.**
  Run: `cd platform && npm run build && npm run lint`
  Expected: PASS (no-raw-literal rule green — all colors are tokens).

- [ ] **Step 4: Commit.**
  ```bash
  git add platform/src/components/enrollment/
  git commit -m "MP-19 C2: EnrollmentPanel + MintDialog (FR-DASH-10)

Assisted-by: Claude (Opus 4.8)"
  ```

### Task C3: Wire the Enrollment tab into the study workspace

**Files:**
- Modify: `platform/src/pages/StudyHome.tsx`

**Interfaces:**
- Consumes: `EnrollmentPanel`; the caller's `role` (grep how `StudyHome`/`Shell` obtains the current membership role — Phase 14 exposes it via `GET /me`/session; reuse that. If `StudyHome` has no role in scope, thread it from the session hook used elsewhere).

- [ ] **Step 1: Add the tab.** In `platform/src/pages/StudyHome.tsx`:
  - Add `UserPlus` to the lucide import.
  - Extend the `Tab` type: `type Tab = "conversation" | "library" | "data" | "lifecycle" | "enrollment";`
  - Add to `TABS`: `{ id: "enrollment", label: "Participants", icon: UserPlus },`
  - Import: `import { EnrollmentPanel } from "@/components/enrollment/EnrollmentPanel";`
  - Add the render branch alongside the others:
    ```tsx
    {tab === "enrollment" && <EnrollmentPanel studyId={id} role={role} />}
    ```
    where `role` is the current user's role on the project (obtain it from the same session/membership source the shell already uses; if unavailable in this component, pass `null` — the panel then hides mint/revoke controls, which is the safe default).

- [ ] **Step 2: Build gate.**
  Run: `cd platform && npm run build && npm run lint`
  Expected: PASS.

- [ ] **Step 3: Commit.**
  ```bash
  git add platform/src/pages/StudyHome.tsx
  git commit -m "MP-19 C3: Participants (enrollment) tab in the study workspace (FR-DASH-10)

Assisted-by: Claude (Opus 4.8)"
  ```

---

## Part E — Integration verification & tracker flip

### Task E1: End-to-end walkthrough + flip the trackers

**Files:**
- Modify: `docs/roadmap/README.md` (Phase 19 status → built)
- Modify: `requirements/traceability.md` (four rows → status per result)
- Modify: `docs/roadmap/19-live-capture-link.md` (Deviations log — record what landed vs the spec)

- [ ] **Step 1: Full gates.**
  Run: `uv run pytest -q && uv run ruff check .`
  Run: `cd extension && npm run check`
  Run: `cd platform && npm run build && npm run lint`
  Expected: all PASS.

- [ ] **Step 2: Manual end-to-end walkthrough (record it).** With `docker compose up` (or `middleware` + `platform` dev servers) and the extension in an Extension Development Host:
  1. In the dashboard, on a study that has cleared its ethics gate, open **Participants** → **Mint links** → copy P01's connection string.
  2. In a clean VS Code, run **Cognitive Overlay: Connect to study** → paste → consent (modal) → see the pre-flight capture summary.
  3. **Start session** → confirm events arrive; the dashboard status flips `unredeemed → paired`.
  4. Confirm the stored events carry `participantId: P01` (server-stamped) even if the extension's local `participantId` setting is wrong.
  5. Flip a capture toggle in the protocol/config while the session runs → confirm the **current** session is unchanged and the new config only applies on the next session's pre-flight (wall #6).
  Note any deviation in the spec's Deviations log.

- [ ] **Step 3: Flip the trackers (only after Steps 1–2 pass).**
  - `docs/roadmap/README.md`: Phase 19 row status `⬜ specced` → `✅ built` (or `🔶` with the pending item named).
  - `requirements/traceability.md`: FR-INST-20/21, FR-ING-7, FR-DASH-10 → `✅` (or `🔶` with a note).
  - `docs/roadmap/19-live-capture-link.md`: fill the Deviations log.

- [ ] **Step 4: Commit.**
  ```bash
  git add docs/roadmap/README.md requirements/traceability.md docs/roadmap/19-live-capture-link.md
  git commit -m "MP-19 E1: live capture link verified end-to-end; trackers flipped

Assisted-by: Claude (Opus 4.8)"
  ```

---

## Notes for the implementer

- **Concurrency hazard:** this repo is edited by multiple agents at once. Before each task, `git status` to confirm you're not sweeping up unrelated changes; stage only the files each task names.
- **Test-runner command:** the extension's exact test invocation is in `extension/package.json` `scripts` (`npm run check` runs the full gate). The `npx tsx --test` form in the B-tasks is the single-file shortcut; if the repo uses a different single-file runner, use that — do not add a test dependency.
- **Fixtures:** the middleware route tests need a study with ethics approval. Reuse the existing `test_evolution*.py` setup (compile a draft → `/approve` → `/ethics-approval`); do not fabricate a shortcut that bypasses the real gate, or the ethics-gate tests become meaningless.
- **Do not bump `SCHEMA_VERSION`** and do not adopt any dependency. If either seems necessary, stop — the design says neither is.
