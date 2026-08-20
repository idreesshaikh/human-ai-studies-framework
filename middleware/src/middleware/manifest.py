"""Platform manifest generator for (FR-AGF-1)."""

from __future__ import annotations

import json
import logging
import os
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from fastapi.applications import FastAPI

log = logging.getLogger(__name__)


@dataclass
class PlatformInfo:
    """Platform identity section."""

    name: str
    version: str
    deployment: str


@dataclass
class APIInfo:
    """API surface section."""

    openapi: str
    auth: dict[str, str]


@dataclass
class SchemaInfo:
    """Schema reference."""

    versions: list[int]
    url: str


@dataclass
class SchemasSection:
    """All schemas the platform exposes."""

    event: SchemaInfo
    protocol: SchemaInfo
    template: SchemaInfo | None = None


@dataclass
class TemplatesSection:
    """Template registry info."""

    index: str
    count: int


@dataclass
class CorpusSection:
    """Corpus info."""

    index: str
    count: int
    tierA: int
    tierB: int


@dataclass
class PlatformManifest:
    """Complete platform manifest."""

    platform: PlatformInfo
    capabilities: list[str]
    api: APIInfo
    schemas: SchemasSection
    templates: TemplatesSection
    corpus: CorpusSection

    generatedAt: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    generator: str = "middleware.manifest"

    def to_dict(self, *, deterministic: bool = False) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result = {
            "platform": asdict(self.platform),
            "capabilities": self.capabilities,
            "api": asdict(self.api),
            "schemas": asdict(self.schemas),
            "templates": asdict(self.templates),
            "corpus": asdict(self.corpus),
            "generator": self.generator,
        }
        if not deterministic:
            result["generatedAt"] = self.generatedAt
        return result

    def to_json(self, indent: int = 2) -> str:
        """Render as pretty JSON."""
        return json.dumps(self.to_dict(), indent=indent)


def _discover_event_schema_versions(repo: Path) -> list[int]:
    """Discover available event schema versions from the extension."""
    try:
        from middleware.app import KNOWN_EVENT_SCHEMA_VERSIONS

        return sorted(KNOWN_EVENT_SCHEMA_VERSIONS)
    except ImportError:
        return [2, 3, 4]


def _discover_protocol_schema_versions(repo: Path) -> list[int]:
    """Discover supported protocol schema versions from the schema itself."""
    schema_path = (
        repo / "protocol" / "src" / "protocol" / "schema" / "study-protocol.schema.json"
    )
    if schema_path.exists():
        with suppress(Exception):
            schema = json.loads(schema_path.read_text())
            pv = schema.get("properties", {}).get("protocolVersion", {})
            if isinstance(pv.get("enum"), list):
                return sorted(int(v) for v in pv["enum"])
            if pv.get("const") is not None:
                return [int(pv["const"])]
    return [1]


def _discover_template_schema_versions(repo: Path) -> list[int] | None:
    """Discover template schema versions from existing template files."""
    registry = repo / "templates" / "registry"
    if registry.exists():
        with suppress(Exception):
            import yaml

            versions = set()
            for template_file in registry.glob("*.yaml"):
                with open(template_file) as f:
                    template_data = yaml.safe_load(f)
                    if "templateVersion" in template_data:
                        versions.add(template_data["templateVersion"])
            if versions:
                return sorted(versions)

    schema_path = repo / "templates" / "schemas" / "template.schema.json"
    if schema_path.exists():
        with suppress(Exception):
            import json

            json.loads(schema_path.read_text())
            return [1]
    return None


def _count_templates(repo: Path) -> int:
    """Count available templates in the registry."""
    registry = repo / "templates" / "registry"
    if not registry.exists():
        return 0
    return len(list(registry.glob("*.yaml")))


def _count_corpus(repo: Path) -> tuple[int, int, int]:
    """
    Count corpus papers: total, tierA, tierB. Returns: (total, tierA_count, tierB_count)
    """
    corpus_index = repo / "docs" / "papers" / "corpus-index.json"
    if not corpus_index.exists():
        return (0, 0, 0)

    try:
        import json

        data = json.loads(corpus_index.read_text())
        tier_a_count = data.get("tierA", {}).get("count", 0)
        tier_b = data.get("tierB", [])
        tier_b_count = len(tier_b)
        return (tier_a_count + tier_b_count, tier_a_count, tier_b_count)
    except Exception:  # noqa: BLE001 - corpus counts are best-effort; 0 is honest
        return (0, 0, 0)


if TYPE_CHECKING:
    from fastapi.applications import FastAPI


def generate_manifest(
    app: FastAPI | None = None,
    repo: Path | None = None,
    deployment: str = "hosted",
    auth_mode: str = "none",
) -> PlatformManifest:
    """Generate the platform manifest from documents of record."""
    if repo is None:
        repo = Path(__file__).resolve().parent.parent.parent.parent

    platform_info = _generate_platform_info(repo, deployment)

    capabilities = _generate_capabilities(repo)

    api_info = _generate_api_info(app, repo, deployment, auth_mode)

    schemas = _generate_schemas_section(repo)

    templates = _generate_templates_section(repo)

    corpus = _generate_corpus_section(repo)

    return PlatformManifest(
        platform=platform_info,
        capabilities=capabilities,
        api=api_info,
        schemas=schemas,
        templates=templates,
        corpus=corpus,
    )


def _generate_platform_info(repo: Path, deployment: str) -> PlatformInfo:
    """Generate platform identity from package metadata."""
    version = "0.1.0"
    pyproject = repo / "pyproject.toml"
    if pyproject.exists():
        with suppress(Exception):
            import tomllib

            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
                version = (
                    data.get("tool", {})
                    .get("poetry", {})
                    .get("version", data.get("project", {}).get("version", "0.1.0"))
                )

    middleware_pyproject = repo / "middleware" / "pyproject.toml"
    if middleware_pyproject.exists():
        with suppress(Exception):
            import tomllib

            with open(middleware_pyproject, "rb") as f:
                data = tomllib.load(f)
                version = data.get("project", {}).get("version", version)

    env_deployment = os.environ.get("DEPLOYMENT_MODE", deployment)
    if env_deployment in ("hosted", "demo"):
        deployment = env_deployment

    return PlatformInfo(
        name="Framework for Conducting Human-AI Studies",
        version=version,
        deployment=deployment,
    )


def _generate_capabilities(repo: Path) -> list[str]:
    """Generate capabilities list from available features."""
    capabilities = ["conversation", "protocol-compilation"]

    templates_dir = repo / "templates" / "registry"
    if templates_dir.exists() and len(list(templates_dir.glob("*.yaml"))) > 0:
        capabilities.append("templates")

    corpus_index = repo / "docs" / "papers" / "corpus-index.json"
    if corpus_index.exists():
        capabilities.append("corpus")
        capabilities.append("paper-matching")

    analysis_dir = repo / "analysis" / "src" / "analysis"
    if analysis_dir.exists():
        capabilities.append("analysis-recipes")

    # Guard against a missing tree so the generator is robust when pointed at a partial
    # checkout (feature detection, never a crash).
    mining_dir = repo / "middleware" / "src" / "middleware"
    if (mining_dir / "mining.py").exists() or (repo / "curated").exists():
        capabilities.append("curated-datasets")

    return sorted(capabilities)


def _generate_api_info(
    app: FastAPI | None, repo: Path, deployment: str, auth_mode: str = "none"
) -> APIInfo:
    """Generate API info section."""
    how = {
        "none": "No authentication — single facilitator (NFR-5).",
        "token": "Bearer token (MIDDLEWARE_TOKEN) on platform-facing routes; "
        "ingest stays open (NFR-1).",
        "clerk": "Clerk-issued session JWT with project-scoped roles (FR-PLAT-2).",
    }
    return APIInfo(
        openapi="/openapi.json",
        auth={"mode": auth_mode, "how": how.get(auth_mode, how["none"])},
    )


def _generate_schemas_section(repo: Path) -> SchemasSection:
    """Generate schemas section from available schema files."""
    event_versions = _discover_event_schema_versions(repo)
    event_url = "/schemas/event"

    protocol_versions = _discover_protocol_schema_versions(repo)
    protocol_url = "/schemas/protocol"

    template_versions = _discover_template_schema_versions(repo)
    template_info = None
    if template_versions:
        template_info = SchemaInfo(versions=template_versions, url="/schemas/template")

    return SchemasSection(
        event=SchemaInfo(versions=event_versions, url=event_url),
        protocol=SchemaInfo(versions=protocol_versions, url=protocol_url),
        template=template_info,
    )


def _generate_templates_section(repo: Path) -> TemplatesSection:
    """Generate templates section from registry."""
    count = _count_templates(repo)
    return TemplatesSection(index="/templates", count=count)


def _generate_corpus_section(repo: Path) -> CorpusSection:
    """Generate corpus section from corpus-index.json."""
    total, tier_a, tier_b = _count_corpus(repo)
    return CorpusSection(index="/papers/index", count=total, tierA=tier_a, tierB=tier_b)


# Module-level cache, keyed by (deployment, auth_mode) so two deployments in one process
# (e.g. across tests) don't leak each other's auth mode.
_manifest_cache: dict[tuple[str, str], PlatformManifest] = {}


def get_manifest(
    app: FastAPI | None = None,
    repo: Path | None = None,
    deployment: str | None = None,
    auth_mode: str = "none",
    force_refresh: bool = False,
) -> PlatformManifest:
    """Get the platform manifest, cached per (deployment, auth_mode)."""
    depl = deployment or os.environ.get("DEPLOYMENT_MODE", "hosted")
    key = (depl, auth_mode)
    if force_refresh or key not in _manifest_cache:
        _manifest_cache[key] = generate_manifest(app, repo, depl, auth_mode)
        log.info("Platform manifest generated for %s", key)
    return _manifest_cache[key]


def refresh_manifest() -> PlatformManifest:
    """Clear the cache (next request regenerates)."""
    _manifest_cache.clear()
    return get_manifest(force_refresh=True)


def setup_manifest_route(app: FastAPI, auth_mode: str = "none") -> None:
    """Add the /.well-known/platform-manifest route to a FastAPI app."""
    router = APIRouter(prefix="/.well-known")

    @router.get("/platform-manifest")
    async def platform_manifest(request: Request) -> JSONResponse:
        """Platform manifest for AI agents (FR-AGF-1)."""
        manifest = get_manifest(
            app=request.app,
            deployment=os.environ.get("DEPLOYMENT_MODE", "hosted"),
            auth_mode=auth_mode,
        )
        manifest_dict = manifest.to_dict()
        base_url = str(request.base_url)
        if not base_url.endswith("/"):
            base_url += "/"
        manifest_dict["baseUrl"] = base_url
        return JSONResponse(content=manifest_dict)

    app.include_router(router)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Platform manifest generator (FR-AGF-1)"
    )
    parser.add_argument(
        "--deployment",
        choices=["hosted", "demo"],
        default="hosted",
        help="Deployment mode",
    )
    parser.add_argument(
        "--output", type=str, default=None, help="Output file (default: stdout)"
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")

    args = parser.parse_args()

    repo = Path(__file__).resolve().parent.parent.parent.parent
    manifest = generate_manifest(None, repo, args.deployment)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(manifest.to_dict(), f, indent=2 if args.pretty else None)
        print(f"Manifest written to {args.output}")
    else:
        indent = 2 if args.pretty else None
        print(manifest.to_json(indent=indent))
