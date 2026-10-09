"""Meta API routes."""

import logging

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
)
from protocol.measure_catalog import CATALOG_VERSION, catalog_digest, measure_catalog
from sqlalchemy import text as sqltext

from middleware import (
    auth,
    template_registry,
)
from middleware.route_helpers import (
    KNOWN_EVENT_SCHEMA_VERSIONS,
)
from middleware.routes.deps import ApiDeps

log = logging.getLogger("middleware.app")


def register(app: FastAPI, deps: ApiDeps):
    @app.get("/measure-catalog", dependencies=[Depends(deps.authz["resolve_identity"])])
    def list_measure_catalog() -> dict:
        return {
            "version": CATALOG_VERSION,
            "digest": catalog_digest(),
            "measures": measure_catalog(),
        }

    @app.get("/schemas/event")
    def event_schema() -> dict:
        """Return the machine-readable event contract for integrations."""
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://masters-project.local/schemas/event.schema.json",
            "title": "Study Event",
            "description": "Machine-readable schema for study events.",
            "type": "object",
            "required": [
                "v",
                "ts",
                "mono",
                "sessionId",
                "participantId",
                "condition",
                "seq",
                "type",
                "payload",
            ],
            "additionalProperties": False,
            "properties": {
                "v": {
                    "description": (
                        "Event schema version. Versions 2-4 cover live capture; "
                        "version 5 covers the isolated archive vocabulary; "
                        "version 6 adds declared surveys and pre-task covariates."
                    ),
                    "type": "integer",
                    "minimum": min(KNOWN_EVENT_SCHEMA_VERSIONS),
                    "maximum": max(KNOWN_EVENT_SCHEMA_VERSIONS),
                },
                "ts": {
                    "description": "ISO-8601 wall-clock timestamp with ms precision.",
                    "type": "string",
                    "format": "date-time",
                },
                "mono": {
                    "description": (
                        "Monotonic milliseconds since session start. "
                        "Immune to NTP jumps and manual clock changes."
                    ),
                    "type": "number",
                    "minimum": 0,
                },
                "sessionId": {
                    "description": "Unique session identifier.",
                    "type": "string",
                    "minLength": 1,
                },
                "participantId": {
                    "description": "Participant identifier.",
                    "type": "string",
                    "minLength": 1,
                },
                "condition": {
                    "description": "Condition name declared in the study protocol.",
                    "type": "string",
                    "minLength": 1,
                },
                "seq": {
                    "description": (
                        "Monotonic per-session sequence number, for ordering "
                        "and gap detection."
                    ),
                    "type": "integer",
                    "minimum": 0,
                },
                "type": {
                    "description": (
                        "Event type, e.g., 'session_start', 'fatigue_response', "
                        "'stuck_response'."
                    ),
                    "type": "string",
                    "minLength": 1,
                },
                "payload": {
                    "description": "Event-specific payload data.",
                    "type": "object",
                    "additionalProperties": True,
                },
                "source": {
                    "description": (
                        "Producer stream; falls back to DEFAULT_SOURCE "
                        "('tern') if not provided."
                    ),
                    "type": "string",
                    "default": "tern",
                },
            },
        }

    @app.get("/schemas/protocol")
    def protocol_schema() -> dict:
        """Return the machine-readable study protocol contract."""
        protocol_schema_path = (
            template_registry.REPO
            / "protocol"
            / "src"
            / "protocol"
            / "schema"
            / "study-protocol.schema.json"
        )
        if protocol_schema_path.exists():
            import json

            return json.loads(protocol_schema_path.read_text())
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Study Protocol",
            "description": "Machine-readable requirements specification of a study.",
            "type": "object",
            "required": [
                "protocolVersion",
                "study",
                "researchQuestions",
                "conditions",
                "participants",
                "session",
                "instruments",
                "phases",
                "analysisPlan",
            ],
            "properties": {"protocolVersion": {"type": "integer", "const": 1}},
        }

    @app.get("/schemas/template")
    def template_schema() -> dict:
        """Return the machine-readable study-template contract."""
        template_schema_path = (
            template_registry.REPO / "templates" / "schemas" / "template.schema.json"
        )
        if template_schema_path.exists():
            import json

            return json.loads(template_schema_path.read_text())
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Study Template",
            "description": "Machine-readable template for a published study design.",
            "type": "object",
            "required": [
                "templateVersion",
                "templateId",
                "title",
                "source",
                "designType",
                "dataPath",
                "parameters",
                "measures",
                "statisticalPlan",
                "protocolSkeleton",
            ],
            "properties": {"templateVersion": {"type": "integer", "minimum": 1}},
        }

    @app.get("/health")
    def health() -> dict:
        try:
            with deps.session_factory() as s:
                s.execute(sqltext("SELECT 1"))
            db_ok = True
        except Exception:  # noqa: BLE001 - /health reports degraded, never raises
            db_ok = False
        payload = {
            "status": "ok" if db_ok else "degraded",
            "database": "ok" if db_ok else "unreachable",
            "studyId": deps.check.study_id,
            "protocolLoaded": deps.protocol_loaded(),
            "knownEventSchemaVersions": sorted(KNOWN_EVENT_SCHEMA_VERSIONS),
            "web": {
                "available": deps.web_index.is_file(),
                "buildHash": deps.web_hash.hexdigest()
                if deps.web_index.is_file()
                else None,
            },
        }
        if not db_ok:
            raise HTTPException(status_code=503, detail=payload)
        return payload

    @app.get("/auth/config")
    def auth_config() -> dict:
        """Which sign-in surface the platform should render (FR-OPS-5)."""
        return auth.public_config(deps.settings)
