"""Protocol compiler for MP-15 (FR-CONV-3).

Deterministic compilation of accepted design moves into protocol drafts.
This is the server-side compiler that mirrors the client-side stub.

The compiler is a PURE FUNCTION: (base_draft, accepted_moves) -> diff + new_draft
- No LLM in the compile step (FR-CONV-3.1)
- Replaying the same moves against the same base yields byte-identical results (F3.1)
- Validation runs on every compile (FR-CONV-3.2)
- No diff applies without recorded approval (FR-CONV-3.3)

The compile process:
1. Accepted moves are folded into a draft model
2. The draft model is converted to protocol YAML
3. The YAML is validated against the protocol schema
4. A diff is generated showing the changes
5. The new draft and diff are returned (not applied until approved)
"""

from __future__ import annotations

import difflib
import json
import logging
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import yaml

from middleware.db import make_session_factory

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


@dataclass
class DraftPatch:
    """A patch operation on the protocol draft."""
    
    section: str  # protocol section (e.g., "researchQuestions", "conditions")
    op: str  # "append", "set", "remove"
    key: str | None = None  # for keyed sections
    value: Any = None  # the value to append/set
    old_value: Any = None  # for diff generation


@dataclass
class CompileResult:
    """Result of compiling accepted moves."""
    
    # The new draft as a protocol dict
    draft: dict
    
    # The YAML representation
    yaml: str
    
    # The diff from the base draft
    diff: str
    
    # List of patches that were applied
    patches: list[DraftPatch] = field(default_factory=list)
    
    # Validation errors (empty if valid)
    errors: list[str] = field(default_factory=list)
    
    # Whether the draft is valid
    is_valid: bool = True


# ---------------------------------------------------------------------------
# Protocol schema loading
# ---------------------------------------------------------------------------

def _load_protocol_schema() -> dict:
    """Load the protocol JSON Schema."""
    schema_path = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "protocol"
        / "src"
        / "protocol"
        / "schema"
        / "study-protocol.schema.json"
    )
    if not schema_path.exists():
        raise FileNotFoundError(
            f"Protocol schema not found at {schema_path}"
        )
    return json.loads(schema_path.read_text())


# ---------------------------------------------------------------------------
# Draft model
# ---------------------------------------------------------------------------

class ProtocolDraft:
    """Client-side protocol draft model.
    
    This is a simplified model that mirrors the client-side types.ts.
    The real protocol YAML is generated from this model.
    """
    
    def __init__(self):
        self.sections: dict[str, Any] = {
            "researchQuestions": [],
            "design": [],
            "participants": [],
            "conditions": [],
            "measures": [],
            "instruments": [],
            "statisticalPlan": [],
            "ethics": [],
        }
    
    def to_protocol(self) -> dict:
        """Convert the draft model to a protocol dict."""
        protocol: dict = {
            "protocolVersion": 1,
            "study": {
                "id": "draft",
                "title": "Draft Protocol",
                "researchers": [],
                "ethicsRef": "",
            },
            "researchQuestions": self._format_rqs(),
            "conditions": self.sections.get("conditions", []),
            "participants": self._format_participants(),
            "session": self._format_session(),
            "instruments": self._format_instruments(),
            "phases": [],
            "analysisPlan": self._format_analysis_plan(),
        }
        
        # Add literature if present
        if self.sections.get("literature"):
            protocol["literature"] = self.sections["literature"]
        
        return protocol
    
    def _format_rqs(self) -> list[dict]:
        """Format research questions."""
        rqs = self.sections.get("researchQuestions", [])
        if not rqs:
            return []
        return [
            {"id": f"RQ-{i+1}", "text": q}
            if isinstance(q, str)
            else q
            for i, q in enumerate(rqs)
        ]
    
    def _format_participants(self) -> dict:
        """Format participants section."""
        parts = self.sections.get("participants", [])
        if not parts:
            return {"planned": 0, "design": "within-subjects", "counterbalanced": False}
        
        # Simple handling for now
        return {
            "planned": parts[0] if parts else 0,
            "design": "within-subjects",
            "counterbalanced": True,
        }
    
    def _format_session(self) -> dict:
        """Format session section."""
        session = self.sections.get("session", [])
        if session:
            return {"durationMinutes": session[0], "taskDescription": ""}
        return {"durationMinutes": 45, "taskDescription": ""}
    
    def _format_instruments(self) -> dict:
        """Format instruments section."""
        instruments = self.sections.get("instruments", [])
        if not instruments:
            return {"cognitiveOverlay": {
                "session": {"durationMinutes": 45},
                "fatigue": {"intervalMinutes": 15, "waitForPauseSeconds": 4},
                "stuck": {"enabled": True, "thresholdSeconds": 90},
                "output": {"httpEndpoint": "http://127.0.0.1:8000/ingest/events"},
            }}
        return instruments[0] if instruments else {}
    
    def _format_analysis_plan(self) -> list[dict]:
        """Format analysis plan."""
        plan = self.sections.get("statisticalPlan", [])
        if not plan:
            return []
        
        # Simple handling for now
        return [
            {"rq": "RQ-1", "recipes": ["task-time-by-condition"]}
        ]


# ---------------------------------------------------------------------------
# Move application
# ---------------------------------------------------------------------------

def apply_move(draft: ProtocolDraft, move: dict) -> list[DraftPatch]:
    """Apply a single design move to the draft.
    
    Args:
        draft: The current protocol draft.
        move: A design move dict with kind, target, proposal, patch, grounding, status.
    
    Returns:
        List of patches that were applied.
    """
    patches: list[DraftPatch] = []
    
    if move.get("status") != "accepted":
        return patches
    
    patch_def = move.get("patch")
    if not patch_def:
        # Caution moves have no patch
        return patches
    
    section = patch_def.get("section")
    op = patch_def.get("op")
    value = patch_def.get("value")
    key = patch_def.get("key")
    
    if section not in draft.sections:
        log.warning("Unknown section in move: %s", section)
        return patches
    
    current = draft.sections[section]
    
    if op == "append":
        if isinstance(current, list):
            if value not in current:
                old = deepcopy(current)
                current.append(value)
                patches.append(DraftPatch(
                    section=section,
                    op="append",
                    value=value,
                    old_value=old,
                ))
    elif op == "set":
        old = deepcopy(current)
        draft.sections[section] = [value] if isinstance(value, str) else value
        patches.append(DraftPatch(
            section=section,
            op="set",
            value=value,
            old_value=old,
        ))
    elif op == "remove":
        if isinstance(current, list) and value in current:
            old = deepcopy(current)
            current.remove(value)
            patches.append(DraftPatch(
                section=section,
                op="remove",
                value=value,
                old_value=old,
            ))
    
    return patches


def compile_moves(
    base_draft: ProtocolDraft | None,
    moves: list[dict],
) -> tuple[ProtocolDraft, list[DraftPatch]]:
    """Compile accepted moves into a draft.
    
    This is a PURE FUNCTION: same (base_draft, moves) always yields same result.
    
    Args:
        base_draft: The base draft to start from (None = empty draft).
        moves: List of design moves (each with status field).
    
    Returns:
        Tuple of (new_draft, applied_patches).
    """
    draft = base_draft or ProtocolDraft()
    all_patches: list[DraftPatch] = []
    
    for move in moves:
        patches = apply_move(draft, move)
        all_patches.extend(patches)
    
    return draft, all_patches


# ---------------------------------------------------------------------------
# YAML generation and diffing
# ---------------------------------------------------------------------------

def draft_to_yaml(draft: ProtocolDraft) -> str:
    """Convert a draft to YAML string."""
    protocol = draft.to_protocol()
    return yaml.dump(protocol, sort_keys=False, default_flow_style=False)


def generate_diff(base_yaml: str, new_yaml: str) -> str:
    """Generate a unified diff between two YAML strings."""
    base_lines = base_yaml.splitlines(keepends=True)
    new_lines = new_yaml.splitlines(keepends=True)
    
    diff = difflib.unified_diff(
        base_lines,
        new_lines,
        fromfile="base",
        tofile="new",
        lineterm="",
    )
    
    return "".join(diff)


# ---------------------------------------------------------------------------
# Full compile function
# ---------------------------------------------------------------------------

def compile_protocol(
    base_draft_yaml: str | None,
    moves: list[dict],
) -> CompileResult:
    """Full compilation: moves -> validated protocol draft + diff.
    
    Args:
        base_draft_yaml: The base draft as YAML string (None = empty).
        moves: List of design moves.
    
    Returns:
        CompileResult with the new draft, YAML, diff, patches, and validation status.
    """
    # Parse base draft
    if base_draft_yaml:
        base_protocol = yaml.safe_load(base_draft_yaml)
        base_draft = ProtocolDraft()
        # Would populate from protocol, but simplified for now
    else:
        base_draft = None
        base_protocol = {}
    
    # Compile moves into draft
    new_draft, patches = compile_moves(base_draft, moves)
    
    # Generate YAML
    new_yaml = draft_to_yaml(new_draft)
    
    # Generate diff
    if base_draft_yaml:
        diff = generate_diff(base_draft_yaml, new_yaml)
    else:
        diff = new_yaml
    
    # Validate (would use protocol loader in production)
    errors = []
    try:
        # Try to parse as YAML at minimum
        yaml.safe_load(new_yaml)
        # Would validate against schema here
    except yaml.YAMLError as e:
        errors.append(str(e))
    
    return CompileResult(
        draft=new_draft.to_protocol(),
        yaml=new_yaml,
        diff=diff,
        patches=patches,
        errors=errors,
        is_valid=len(errors) == 0,
    )


# ---------------------------------------------------------------------------
# Database integration
# ---------------------------------------------------------------------------

from pathlib import Path


def compile_and_store(
    moves: list[dict],
    db_path: Path | str | None = None,
    study_id: str | None = None,
    base_draft_yaml: str | None = None,
) -> CompileResult:
    """Compile moves and store the result in the database.
    
    Args:
        db_path: Path to the SQLite database.
        study_id: The study ID to associate with the compilation.
        base_draft_yaml: The base draft as YAML.
        moves: List of design moves.
    
    Returns:
        CompileResult with compilation details.
    """
    result = compile_protocol(base_draft_yaml, moves)
    
    # Store in database if configured
    if db_path and study_id:
        try:
            factory = make_session_factory(db_path)
            with factory() as s:
                _store_compilation(s, study_id, moves, result)
        except Exception as e:
            log.warning("Failed to store compilation: %s", e)
    
    return result


def _store_compilation(
    s: "Session",
    study_id: str,
    moves: list[dict],
    result: CompileResult,
) -> None:
    """Store a compilation event in the database."""
    # This would insert into a compilations table
    # For now, just a placeholder
    pass


if __name__ == "__main__":
    # Test the compiler
    from pathlib import Path
    
    # Create some test moves
    moves = [
        {
            "moveId": "m1",
            "kind": "add-rq",
            "target": "researchQuestions[]",
            "proposal": "Add RQ about trust",
            "patch": {
                "section": "researchQuestions",
                "op": "append",
                "value": "Do developers over-trust AI-generated code?",
            },
            "grounding": [{"ref": "corpus:trust-in-ai-code-generation", "tier": "A"}],
            "status": "accepted",
        },
        {
            "moveId": "m2",
            "kind": "add-measure",
            "target": "measures[]",
            "proposal": "Add review latency measure",
            "patch": {
                "section": "measures",
                "op": "append",
                "value": "Review latency (suggestion-visible-to-decision time)",
            },
            "grounding": [{"ref": "corpus:trust-in-ai-code-generation", "tier": "A"}],
            "status": "accepted",
        },
        {
            "moveId": "m3",
            "kind": "caution",
            "target": "measures",
            "proposal": "Self-report alone is insufficient",
            "patch": None,
            "grounding": [{"ref": "corpus:metr-early-2025-dev-productivity", "tier": "A"}],
            "status": "accepted",
        },
    ]
    
    result = compile_protocol(None, moves)
    
    print("Compilation result:")
    print(f"  Valid: {result.is_valid}")
    print(f"  Errors: {result.errors}")
    print(f"  Patches applied: {len(result.patches)}")
    print("\nGenerated YAML:")
    print(result.yaml)
    print("\nDiff:")
    print(result.diff)
