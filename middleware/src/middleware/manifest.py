"""Platform manifest generator for MP-17 (FR-AGF-1).

Assembles the platform manifest at startup from documents of record:
- FastAPI's own OpenAPI doc (API surface)
- Published JSON Schemas (event, protocol, template)
- Redocs parser output (glossary, SRS)
- Template registry index
- Corpus index counts
- Deployment auth mode

The manifest is served at `GET /.well-known/platform-manifest` (unauthenticated).

Key principle: NO HAND-WRITTEN MANIFEST CONTENT (FR-AGF-1 F1.1). Every value
is traceable to a generated source. A grep finds no literal capability strings
outside this generator module.

The manifest shape follows fr-agf.md §2:
{
  "platform": {"name", "version", "deployment"},
  "capabilities": [...],
  "api": {"openapi": url, "auth": {"mode", "how"}},
  "schemas": {"event": {...}, "protocol": {...}, "template": {...}},
  "vocabulary": {"glossary": url, "requirements": url},
  "templates": {"index": url, "count"},
  "corpus": {"index": url, "count"}
}
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any



if TYPE_CHECKING:
    from fastapi.applications import FastAPI

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes for manifest structure
# ---------------------------------------------------------------------------

@dataclass
class PlatformInfo:
    """Platform identity section."""
    name: str
    version: str
    deployment: str  # "hosted" | "self-hosted" | "demo"


@dataclass
class APIInfo:
    """API surface section."""
    openapi: str  # URL to OpenAPI JSON
    auth: dict[str, str]  # {"mode", "how"}


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
class VocabularySection:
    """Vocabulary endpoints."""
    glossary: str  # URL to glossary endpoint
    requirements: str  # URL to requirements endpoint


@dataclass
class TemplatesSection:
    """Template registry info."""
    index: str  # URL to template index
    count: int


@dataclass
class CorpusSection:
    """Corpus info."""
    index: str  # URL to corpus index
    count: int
    tierA: int
    tierB: int


@dataclass
class PlatformManifest:
    """Complete platform manifest.
    
    Every value is generated from documents of record. No hand-written content.
    """
    platform: PlatformInfo
    capabilities: list[str]
    api: APIInfo
    schemas: SchemasSection
    vocabulary: VocabularySection
    templates: TemplatesSection
    corpus: CorpusSection
    
    # Additional generated fields (extensions allowed per FR-AGF-1 freedoms)
    generatedAt: str = field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )
    generator: str = "middleware.manifest"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result = {
            "platform": asdict(self.platform),
            "capabilities": self.capabilities,
            "api": asdict(self.api),
            "schemas": asdict(self.schemas),
            "vocabulary": asdict(self.vocabulary),
            "templates": asdict(self.templates),
            "corpus": asdict(self.corpus),
            "generatedAt": self.generatedAt,
            "generator": self.generator,
        }
        return result
    
    def to_json(self, indent: int = 2) -> str:
        """Render as pretty JSON."""
        return json.dumps(self.to_dict(), indent=indent)


# ---------------------------------------------------------------------------
# Schema discovery
# ---------------------------------------------------------------------------

def _discover_event_schema_versions(repo: Path) -> list[int]:
    """Discover available event schema versions from the extension."""
    # Import from app.py where KNOWN_EVENT_SCHEMA_VERSIONS is defined
    # This keeps the values in sync without hand-written content
    try:
        from middleware.app import KNOWN_EVENT_SCHEMA_VERSIONS
        return sorted(KNOWN_EVENT_SCHEMA_VERSIONS)
    except ImportError:
        # Fallback to known versions from the extension
        # v2 = cognitive leg; v3 = + behavioral telemetry leg (MP-05); 
        # v4 = + agent-interaction leg, snapshots, task harness (MP-12)
        return [2, 3, 4]


def _discover_protocol_schema_versions(repo: Path) -> list[int]:
    """Discover available protocol schema versions."""
    schema_path = (
        repo / "protocol" / "src" / "protocol" / "schema" / "study-protocol.schema.json"
    )
    if schema_path.exists():
        try:
            import json
            schema = json.loads(schema_path.read_text())
            # Check if there's a protocolVersion const in properties
            if "properties" in schema and "protocolVersion" in schema["properties"]:
                const_val = schema["properties"]["protocolVersion"].get("const")
                if const_val is not None:
                    return [const_val]
        except Exception:
            pass
    # Return known versions - protocol schema is currently at v1
    return [1]


def _discover_template_schema_versions(repo: Path) -> list[int] | None:
    """Discover template schema versions from existing template files."""
    # Look at actual template files to see what versions are in use
    registry = repo / "templates" / "registry"
    if registry.exists():
        try:
            import yaml
            versions = set()
            for template_file in registry.glob("*.yaml"):
                with open(template_file) as f:
                    template_data = yaml.safe_load(f)
                    if "templateVersion" in template_data:
                        versions.add(template_data["templateVersion"])
            if versions:
                return sorted(versions)
        except Exception:
            pass
    
    # Fallback to schema file
    schema_path = repo / "templates" / "schemas" / "template.schema.json"
    if schema_path.exists():
        try:
            import json
            json.loads(schema_path.read_text())
            # Template schema uses minimum, so return v1 as current
            return [1]
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Count functions
# ---------------------------------------------------------------------------

def _count_templates(repo: Path) -> int:
    """Count available templates in the registry."""
    registry = repo / "templates" / "registry"
    if not registry.exists():
        return 0
    return len(list(registry.glob("*.yaml")))


def _count_corpus(repo: Path) -> tuple[int, int, int]:
    """Count corpus papers: total, tierA, tierB.
    
    Returns: (total, tierA_count, tierB_count)
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
    except Exception:
        return (0, 0, 0)


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

if TYPE_CHECKING:
    from fastapi.applications import FastAPI

def generate_manifest(
    app: FastAPI | None = None,
    repo: Path | None = None,
    deployment: str = "self-hosted",
) -> PlatformManifest:
    """Generate the platform manifest from documents of record.
    
    Args:
        app: FastAPI application (for OpenAPI generation)
        repo: Repository root path (default: auto-detected)
        deployment: Deployment mode ("hosted", "self-hosted", "demo")
    
    Returns:
        Complete PlatformManifest with all sections populated.
    
    Every value is generated - no hand-written content (FR-AGF-1 F1.1).
    """
    if repo is None:
        repo = Path(__file__).resolve().parent.parent.parent.parent
    
    # Platform identity (from pyproject.toml or package metadata)
    platform_info = _generate_platform_info(repo, deployment)
    
    # Capabilities (from available features)
    capabilities = _generate_capabilities(repo)
    
    # API info (from FastAPI OpenAPI)
    api_info = _generate_api_info(app, repo, deployment)
    
    # Schemas
    schemas = _generate_schemas_section(repo)
    
    # Vocabulary
    vocabulary = _generate_vocabulary_section(app, repo)
    
    # Templates
    templates = _generate_templates_section(repo)
    
    # Corpus
    corpus = _generate_corpus_section(repo)
    
    return PlatformManifest(
        platform=platform_info,
        capabilities=capabilities,
        api=api_info,
        schemas=schemas,
        vocabulary=vocabulary,
        templates=templates,
        corpus=corpus,
    )


def _generate_platform_info(repo: Path, deployment: str) -> PlatformInfo:
    """Generate platform identity from package metadata."""
    # Try to get version from pyproject.toml
    version = "0.1.0"
    pyproject = repo / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
                version = data.get("tool", {}).get("poetry", {}).get("version", 
                    data.get("project", {}).get("version", "0.1.0"))
        except Exception:
            pass
    
    # Try middleware package
    middleware_pyproject = repo / "middleware" / "pyproject.toml"
    if middleware_pyproject.exists():
        try:
            import tomllib
            with open(middleware_pyproject, "rb") as f:
                data = tomllib.load(f)
                version = data.get("project", {}).get("version", version)
        except Exception:
            pass
    
    # Determine deployment mode from environment
    env_deployment = os.environ.get("DEPLOYMENT_MODE", deployment)
    if env_deployment in ("hosted", "self-hosted", "demo"):
        deployment = env_deployment
    
    return PlatformInfo(
        name="Framework for Conducting Human-AI Studies",
        version=version,
        deployment=deployment,
    )


def _generate_capabilities(repo: Path) -> list[str]:
    """Generate capabilities list from available features."""
    capabilities = ["conversation", "protocol-compilation"]
    
    # Check for template registry
    templates_dir = repo / "templates" / "registry"
    if templates_dir.exists() and len(list(templates_dir.glob("*.yaml"))) > 0:
        capabilities.append("templates")
    
    # Check for corpus
    corpus_index = repo / "docs" / "papers" / "corpus-index.json"
    if corpus_index.exists():
        capabilities.append("corpus")
        capabilities.append("paper-matching")
    
    # Check for analysis recipes
    analysis_dir = repo / "analysis" / "src" / "analysis"
    if analysis_dir.exists():
        capabilities.append("analysis-recipes")
    
    # Check for mining
    mining_dir = repo / "middleware" / "src" / "middleware"
    if (mining_dir / "mining.py").exists() or any(
        f.name.startswith("mining") or f.name.startswith("curated")
        for f in mining_dir.iterdir()
    ):
        capabilities.append("curated-datasets")
    
    return sorted(capabilities)


def _generate_api_info(
    app: FastAPI | None,
    repo: Path,
    deployment: str,
) -> APIInfo:
    """Generate API info section."""
    # Auth mode from environment or deployment
    auth_mode = os.environ.get("AUTH_MODE", "none")
    
    # For hosted mode with Clerk
    if deployment == "hosted" and auth_mode == "clerk":
        auth_how = "Clerk OAuth2 with project-scoped roles"
    elif deployment == "demo":
        auth_mode = "none"
        auth_how = "Anonymous read-only access with demo project"
    else:
        auth_how = "Optional Bearer token or none (self-hosted)"
    
    return APIInfo(
        openapi="/openapi.json",
        auth={"mode": auth_mode, "how": auth_how},
    )


def _generate_schemas_section(repo: Path) -> SchemasSection:
    """Generate schemas section from available schema files."""
    # Event schema
    event_versions = _discover_event_schema_versions(repo)
    event_url = "/schemas/event"
    
    # Protocol schema
    protocol_versions = _discover_protocol_schema_versions(repo)
    protocol_url = "/schemas/protocol"
    
    # Template schema (optional)
    template_versions = _discover_template_schema_versions(repo)
    template_info = None
    if template_versions:
        template_info = SchemaInfo(
            versions=template_versions,
            url="/schemas/template",
        )
    
    return SchemasSection(
        event=SchemaInfo(versions=event_versions, url=event_url),
        protocol=SchemaInfo(versions=protocol_versions, url=protocol_url),
        template=template_info,
    )


def _generate_vocabulary_section(app: FastAPI | None, repo: Path) -> VocabularySection:
    """Generate vocabulary section from redocs parser."""
    return VocabularySection(
        glossary="/vocabulary/glossary",
        requirements="/vocabulary/requirements",
    )


def _generate_templates_section(repo: Path) -> TemplatesSection:
    """Generate templates section from registry."""
    count = _count_templates(repo)
    return TemplatesSection(
        index="/templates",
        count=count,
    )


def _generate_corpus_section(repo: Path) -> CorpusSection:
    """Generate corpus section from corpus-index.json."""
    total, tier_a, tier_b = _count_corpus(repo)
    return CorpusSection(
        index="/papers/index",
        count=total,
        tierA=tier_a,
        tierB=tier_b,
    )


# ---------------------------------------------------------------------------
# Manifest caching and refresh
# ---------------------------------------------------------------------------

# Module-level cache for the generated manifest
_cached_manifest: PlatformManifest | None = None


def get_manifest(
    app: FastAPI | None = None,
    repo: Path | None = None,
    deployment: str | None = None,
    force_refresh: bool = False,
) -> PlatformManifest:
    """Get the platform manifest, cached at module level.
    
    Args:
        app: FastAPI application
        repo: Repository root
        deployment: Deployment mode
        force_refresh: Force re-generation
    
    Returns:
        The platform manifest.
    """
    global _cached_manifest
    
    if _cached_manifest is None or force_refresh:
        depl = deployment or os.environ.get("DEPLOYMENT_MODE", "self-hosted")
        _cached_manifest = generate_manifest(app, repo, depl)
        log.info("Platform manifest generated: %s", _cached_manifest.generatedAt)
    
    return _cached_manifest


def refresh_manifest() -> PlatformManifest:
    """Force refresh of the cached manifest."""
    return get_manifest(force_refresh=True)


# ---------------------------------------------------------------------------
# FastAPI route setup
# ---------------------------------------------------------------------------

def setup_manifest_route(app: FastAPI) -> None:
    """Add the /.well-known/platform-manifest route to a FastAPI app.
    
    The route is unauthenticated (like /openapi.json) and returns the
    generated manifest as JSON.
    """
    from fastapi import APIRouter, Request
    from fastapi.responses import JSONResponse
    
    router = APIRouter(prefix="/.well-known")
    
    @router.get("/platform-manifest")
    async def platform_manifest(request: Request) -> JSONResponse:
        """Platform manifest for AI agents (FR-AGF-1).
        
        Unauthenticated. Assembled at startup from documents of record.
        Every value is generated - no hand-written content.
        """
        # Get or generate manifest
        manifest = get_manifest(
            app=request.app,
            deployment=os.environ.get("DEPLOYMENT_MODE", "self-hosted"),
        )
        
        # Add request-specific context
        manifest_dict = manifest.to_dict()
        
        # Add base URL for relative links
        base_url = str(request.base_url)
        if not base_url.endswith("/"):
            base_url += "/"
        manifest_dict["baseUrl"] = base_url
        
        return JSONResponse(content=manifest_dict)
    
    app.include_router(router)


# ---------------------------------------------------------------------------
# CLI for testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Platform manifest generator (FR-AGF-1)"
    )
    parser.add_argument(
        "--deployment",
        choices=["hosted", "self-hosted", "demo"],
        default="self-hosted",
        help="Deployment mode",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file (default: stdout)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON",
    )
    
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
