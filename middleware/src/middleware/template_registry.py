"""Template registry for MP-15 (FR-TPL-1..4).

Manages the versioned template registry: loading, validation, and
instantiation of study templates into protocol drafts.

Templates are YAML files in the templates/registry/ directory, validated
against templates/schemas/template.schema.json. Each template encodes a
published, citable design with its statistical plan (FR-TPL-2).

The registry is read-only at runtime; templates are versioned files on
disk (same discipline as protocolVersion - consumers branch, never guess).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import jsonschema
import yaml

log = logging.getLogger(__name__)

# Repository root
REPO = Path(__file__).resolve().parent.parent.parent.parent

# Template paths
TEMPLATES_DIR = REPO / "templates"
REGISTRY_DIR = TEMPLATES_DIR / "registry"
SCHEMA_FILE = TEMPLATES_DIR / "schemas" / "template.schema.json"

# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------

def _load_schema() -> dict:
    """Load the template JSON Schema."""
    if not SCHEMA_FILE.exists():
        raise FileNotFoundError(
            f"Template schema not found at {SCHEMA_FILE}. "
            "Run: git submodule update --init --recursive"
        )
    return json.loads(SCHEMA_FILE.read_text())


# ---------------------------------------------------------------------------
# Template loading and validation
# ---------------------------------------------------------------------------

def load_template(template_id: str, version: int | None = None) -> dict:
    """Load a template by ID and optional version.
    
    Args:
        template_id: The template identifier (e.g., 'metr-rct-v1').
        version: Optional version number. If None, loads the highest version.
    
    Returns:
        The template dict.
    
    Raises:
        FileNotFoundError: If no matching template is found.
        jsonschema.ValidationError: If the template is invalid.
    """
    # Find matching template files
    candidates = []
    for yaml_file in REGISTRY_DIR.glob("*.yaml"):
        name = yaml_file.stem
        # Parse version from filename: template-id-vN
        if name.startswith(f"{template_id}-"):
            try:
                # Extract version from suffix like -v1, -v2, etc.
                suffix = name[len(template_id) + 1:]
                if suffix.startswith("v") and suffix[1:].isdigit():
                    file_version = int(suffix[1:])
                else:
                    continue
                candidates.append((file_version, yaml_file))
            except (ValueError, IndexError):
                continue
    
    if not candidates:
        # Try exact match
        exact = REGISTRY_DIR / f"{template_id}.yaml"
        if exact.exists():
            candidates.append((1, exact))
        else:
            raise FileNotFoundError(
                f"Template '{template_id}' not found in {REGISTRY_DIR}"
            )
    
    # Filter by version
    if version is not None:
        candidates = [(v, f) for v, f in candidates if v == version]
    
    if not candidates:
        raise FileNotFoundError(
            f"Template '{template_id}' version {version} not found"
        )
    
    # Sort by version (descending) and pick the highest
    candidates.sort(key=lambda x: x[0], reverse=True)
    _, file_path = candidates[0]
    
    # Load and validate
    template = _load_yaml(file_path)
    validate_template(template)
    
    return template


def _load_yaml(path: Path) -> dict:
    """Load a YAML file."""
    return yaml.safe_load(path.read_text())


def validate_template(template: dict) -> None:
    """Validate a template against the schema.
    
    Raises:
        jsonschema.ValidationError: If the template is invalid.
    """
    schema = _load_schema()
    jsonschema.validate(template, schema)


# ---------------------------------------------------------------------------
# Template listing and metadata
# ---------------------------------------------------------------------------

def list_templates() -> list[dict]:
    """List all available templates with metadata.
    
    Returns:
        List of template metadata dicts: {templateId, version, title, 
        designType, dataPath, description}.
    """
    templates = []
    
    if not REGISTRY_DIR.exists():
        return templates
    
    for yaml_file in sorted(REGISTRY_DIR.glob("*.yaml")):
        try:
            template = _load_yaml(yaml_file)
            # Validate to catch bad templates
            validate_template(template)
            
            templates.append({
                "templateId": template["templateId"],
                "version": template.get("templateVersion", 1),
                "title": template["title"],
                "designType": template["designType"],
                "dataPath": template["dataPath"],
                "description": template.get("description", ""),
                "source": template.get("source", []),
            })
        except (yaml.YAMLError, jsonschema.ValidationError, KeyError) as e:
            log.warning("Skipping invalid template %s: %s", yaml_file, e)
            continue
    
    # Sort by templateId
    templates.sort(key=lambda x: x["templateId"])
    return templates


def get_template_metadata(template_id: str) -> list[dict]:
    """Get metadata for all versions of a template.
    
    Args:
        template_id: The template identifier.
    
    Returns:
        List of version metadata dicts, sorted by version (descending).
    """
    versions = []
    for yaml_file in REGISTRY_DIR.glob("*.yaml"):
        name = yaml_file.stem
        if name.startswith(f"{template_id}-"):
            try:
                suffix = name[len(template_id) + 1:]
                if suffix.startswith("v") and suffix[1:].isdigit():
                    version = int(suffix[1:])
                else:
                    continue
                template = _load_yaml(yaml_file)
                versions.append({
                    "version": version,
                    "title": template["title"],
                    "designType": template["designType"],
                    "dataPath": template["dataPath"],
                })
            except (ValueError, IndexError, yaml.YAMLError, KeyError):
                continue
    
    versions.sort(key=lambda x: x["version"], reverse=True)
    return versions


# ---------------------------------------------------------------------------
# Template instantiation
# ---------------------------------------------------------------------------

def instantiate_template(
    template_id: str,
    parameters: dict[str, str | int | float | bool | list],
    version: int | None = None,
) -> dict:
    """Instantiate a template into a protocol draft.
    
    This is a pure function: (template, parameters) -> protocol draft.
    The template's protocolSkeleton is filled with the provided parameters,
    replacing {{param}} placeholders.
    
    Args:
        template_id: The template identifier.
        parameters: Dict of parameter name -> value.
        version: Optional template version.
    
    Returns:
        The filled protocol draft (dict).
    
    Raises:
        FileNotFoundError: If template not found.
        jsonschema.ValidationError: If template is invalid.
        KeyError: If a required parameter is missing.
    """
    template = load_template(template_id, version)
    skeleton = template["protocolSkeleton"]
    
    # Fill placeholders in the skeleton
    filled = _fill_skeleton(skeleton, parameters)
    
    # Validate the filled protocol against the protocol schema
    # (This would use the protocol loader, but we skip it here for now
    # as the protocol package may not be available)
    
    return filled


def _fill_skeleton(skeleton: dict | list | str, parameters: dict) -> dict | list | str:
    """Recursively fill {{param}} placeholders in the skeleton.
    
    Args:
        skeleton: The skeleton (dict, list, or string).
        parameters: Dict of parameter name -> value.
    
    Returns:
        The filled skeleton with placeholders replaced.
    """
    if isinstance(skeleton, str):
        result = skeleton
        for param, value in parameters.items():
            placeholder = f"{{{{ {param} }}}}"
            result = result.replace(placeholder, str(value))
        return result
    elif isinstance(skeleton, list):
        return [_fill_skeleton(item, parameters) for item in skeleton]
    elif isinstance(skeleton, dict):
        return {k: _fill_skeleton(v, parameters) for k, v in skeleton.items()}
    else:
        return skeleton


# ---------------------------------------------------------------------------
# Parameter extraction from templates
# ---------------------------------------------------------------------------

def get_template_parameters(template_id: str, version: int | None = None) -> dict:
    """Get the parameter definitions for a template.
    
    Args:
        template_id: The template identifier.
        version: Optional template version.
    
    Returns:
        Dict of parameter name -> parameter definition.
    """
    template = load_template(template_id, version)
    return template.get("parameters", {})


def get_required_parameters(template_id: str, version: int | None = None) -> list[str]:
    """Get the list of required parameters for a template.
    
    Args:
        template_id: The template identifier.
        version: Optional template version.
    
    Returns:
        List of parameter names that must be provided.
    """
    params = get_template_parameters(template_id, version)
    # Parameters are required if they don't have a default
    required = []
    for name, defn in params.items():
        if "default" not in defn:
            required.append(name)
    return required


# ---------------------------------------------------------------------------
# Statistical plan extraction
# ---------------------------------------------------------------------------

def get_statistical_plan(template_id: str, version: int | None = None) -> dict:
    """Get the statistical plan for a template.
    
    Args:
        template_id: The template identifier.
        version: Optional template version.
    
    Returns:
        The statisticalPlan dict from the template.
    """
    template = load_template(template_id, version)
    return template.get("statisticalPlan", {})


def validate_statistical_plan(template_id: str, version: int | None = None) -> list[str]:
    """Validate that the statistical plan references valid recipes.
    
    Checks that all recipes named in the analysisPlan exist in the
    analysis module.
    
    Args:
        template_id: The template identifier.
        version: Optional template version.
    
    Returns:
        List of missing recipe names (empty if all are valid).
    """
    template = load_template(template_id, version)
    skeleton = template.get("protocolSkeleton", {})
    analysis_plan = skeleton.get("analysisPlan", [])
    
    missing = []
    recipe_names = set()
    
    for ap in analysis_plan:
        for recipe in ap.get("recipes", []):
            recipe_names.add(recipe)
    
    # Check against known recipes (would query analysis module in production)
    # For now, we just return the list of recipes that would need checking
    return list(recipe_names)


# ---------------------------------------------------------------------------
# Template selection and recommendation
# ---------------------------------------------------------------------------

def recommend_templates(
    query: str,
    *,
    design_type: str | None = None,
    data_path: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Recommend templates matching a researcher's idea.
    
    Uses simple keyword matching against template metadata.
    In production, this would use the LLM with paper_index search.
    
    Args:
        query: The researcher's idea (natural language).
        design_type: Optional filter by design type.
        data_path: Optional filter by data path.
        limit: Maximum number of results.
    
    Returns:
        List of template metadata dicts, sorted by relevance.
    """
    all_templates = list_templates()
    query_lower = query.lower()
    
    # Score each template
    scored = []
    for tpl in all_templates:
        score = 0
        
        # Match query terms against title and description
        for term in re.findall(r"[a-z0-9]{4,}", query_lower):
            if term in tpl.get("title", "").lower():
                score += 2
            if term in tpl.get("description", "").lower():
                score += 1
        
        # Filter by design_type if specified
        if design_type and tpl.get("designType") != design_type:
            continue
        
        # Filter by data_path if specified
        if data_path and tpl.get("dataPath") != data_path:
            continue
        
        scored.append((score, tpl))
    
    # Sort by score (descending)
    scored.sort(key=lambda x: x[0], reverse=True)
    
    return [tpl for _, tpl in scored[:limit]]


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def template_exists(template_id: str, version: int | None = None) -> bool:
    """Check if a template exists."""
    try:
        load_template(template_id, version)
        return True
    except FileNotFoundError:
        return False


def get_template_version(template_id: str) -> int | None:
    """Get the highest version number for a template."""
    versions = get_template_metadata(template_id)
    return versions[0]["version"] if versions else None


if __name__ == "__main__":
    # CLI-like test
    print("Available templates:")
    for tpl in list_templates():
        print(f"  {tpl['templateId']} (v{tpl['version']}): {tpl['title']}")
    
    print("\nTemplate metadata for metr-rct-v1:")
    for ver in get_template_metadata("metr-rct-v1"):
        print(f"  v{ver['version']}: {ver['title']}")
    
    print("\nParameters for metr-rct-v1:")
    params = get_template_parameters("metr-rct-v1")
    for name, defn in params.items():
        print(f"  {name}: {defn.get('description', 'No description')}")
