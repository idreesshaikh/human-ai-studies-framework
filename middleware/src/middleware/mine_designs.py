"""Mine the corpus for recurring design signatures and draft templates."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from middleware import matching, template_registry
from middleware.db import CORPUS_STUDY_ID, Paper

log = logging.getLogger(__name__)

# Common design vocabulary from research methodology literature
DESIGN_KEYWORDS = {
    # Between-subjects designs
    "between-subjects": ["between subjects", "between-subject", "independent groups"],
    "control group": ["control group", "control condition", "untreated control"],
    "treatment group": ["treatment group", "treatment condition", "experimental group"],
    "randomly assigned": ["randomly assigned", "random assignment", "randomized"],

    # Within-subjects designs
    "within-subjects": ["within subjects", "within-subject", "repeated measures"],
    "counterbalanced": ["counterbalanced", "counterbalancing", "counterbalance order"],
    "crossover": ["crossover", "cross-over"],

    # Study types
    "observational": [
        "observational study",
        "observational research",
        "non-experimental",
    ],
    "field study": ["field study", "field research", "naturalistic"],
    "survey": ["survey study", "questionnaire", "self-report"],
    "experiment": ["experiment", "experimental", "controlled experiment"],

    # Sample sizes/designs
    "single-arm": ["single arm", "single-arm", "single group"],
    "benchmark": ["benchmark evaluation", "benchmark study"],
    "multi-arm": ["multi-arm", "multi arm", "multiple arms"],

    # Measurement/instrumentation
    "behavioral": ["behavioral data", "user behavior", "logging"],
    "telemetry": ["telemetry", "event logging", "event capture"],
    "self-report": ["self-report", "self report", "questionnaire"],
    "assessment": ["assessment", "measuring", "measurement"],

    # Analysis types
    "qualitative": ["qualitative", "thematic analysis", "coding"],
    "quantitative": ["quantitative", "statistical analysis", "hypothesis testing"],
    "mixed-methods": ["mixed methods", "mixed-method"],
    "descriptive": ["descriptive", "descriptive statistics"],

    # Data properties
    "longitudinal": ["longitudinal", "over time", "time series"],
    "cross-sectional": ["cross-sectional", "cross section"],
    "replicated": ["replicated", "replication", "replicate"],
}

# Flatten into a single searchable set
DESIGN_PHRASES = set()
for variants in DESIGN_KEYWORDS.values():
    DESIGN_PHRASES.update(variants)


def extract_design_phrases(text: str) -> set[str]:
    """Find all recognized design phrases in a text (title + abstract)."""
    text_lower = text.lower()
    found = set()
    for phrase in DESIGN_PHRASES:
        # Whole-token match only
        pattern = rf"(?<![a-z0-9])({re.escape(phrase)})(?![a-z0-9])"
        if re.search(pattern, text_lower):
            found.add(phrase)
    return found


def cluster_papers_by_designs(s: Session) -> dict[frozenset[str], list[dict]]:
    """Group corpus papers by their design characteristics."""
    # Load all corpus papers
    papers = s.execute(
        select(Paper.paper_ref, Paper.title, Paper.abstract, Paper.score).where(
            Paper.study_id == CORPUS_STUDY_ID
        )
    ).all()

    clusters: dict[frozenset[str], list[dict]] = {}
    for ref, title, abstract, score in papers:
        text = f"{title or ''} {abstract or ''}".lower()
        phrases = extract_design_phrases(text)
        if not phrases:
            continue

        cluster_key = frozenset(phrases)
        if cluster_key not in clusters:
            clusters[cluster_key] = []
        clusters[cluster_key].append({
            "ref": ref,
            "title": title or "",
            "confidence": matching.paper_confidence(score),
        })

    return clusters


def identify_top_clusters(
    clusters: dict[frozenset[str], list[dict]], min_papers: int = 3
) -> list[tuple[frozenset[str], int]]:
    """Rank clusters by paper count, filter by minimum support."""
    ranked = [
        (phrases, len(papers))
        for phrases, papers in clusters.items()
        if len(papers) >= min_papers
    ]
    ranked.sort(key=lambda x: -x[1])
    return ranked


def infer_design_type(phrases: frozenset[str]) -> str:
    """Guess a designType slug based on the phrase set."""
    # Hierarchical inference
    if any(
        p in phrases
        for p in ["between subjects", "between-subject", "independent groups"]
    ):
        if any(p in phrases for p in ["randomly assigned", "randomized", "rct"]):
            return "rct-between-subjects"
        return "observational-between-subjects"

    if any(
        p in phrases for p in ["within subjects", "within-subject", "repeated measures"]
    ):
        if "crossover" in phrases:
            return "crossover-design"
        return "repeated-measures"

    if any(p in phrases for p in ["observational", "field study", "naturalistic"]):
        return "observational-field"

    if any(p in phrases for p in ["survey", "questionnaire", "self-report"]):
        return "survey-design"

    if any(p in phrases for p in ["single arm", "single-arm", "single group"]):
        return "single-arm-design"

    if any(p in phrases for p in ["benchmark", "benchmark evaluation"]):
        return "benchmark-evaluation"

    return "empirical-study"


def infer_analysis_recipe(phrases: frozenset[str]) -> str:
    """Guess a recipe ID based on the phrase set."""
    # Map to known recipes (these must exist in analysis/src/analysis/recipes/)
    # Prioritize most specific patterns first

    # Multi-arm/complex designs
    if any(p in phrases for p in ["multi arm", "multi-arm", "multiple arms"]):
        return "two-group-nonparametric"

    # Between-subjects (two-group default)
    if any(
        p in phrases for p in ["between subjects", "between-subject", "control group"]
    ):
        if any(p in phrases for p in ["randomly assigned", "rct", "randomized"]):
            return "two-group-nonparametric"
        return "two-group-nonparametric"

    # Within-subjects / repeated measures
    if any(
        p in phrases for p in ["within subjects", "within-subject", "repeated measures"]
    ):
        if "crossover" in phrases:
            return "paired-nonparametric"
        return "paired-nonparametric"

    # Paired/matched designs
    if "crossover" in phrases or "paired" in phrases:
        return "paired-nonparametric"

    # Observational / correlational
    if any(p in phrases for p in ["observational", "field study", "naturalistic"]):
        return "paired-nonparametric"

    # Survey / self-report
    if any(p in phrases for p in ["survey", "questionnaire", "self-report"]):
        return "two-group-nonparametric"

    # Default to a safe fallback
    return "two-group-nonparametric"


def draft_template_yaml(
    cluster_id: str,
    phrases: frozenset[str],
    papers: list[dict],
    design_type: str,
    recipe: str,
) -> dict:
    """Generate a draft template YAML structure."""
    title = f"{design_type.replace('-', ' ').title()} Design"
    description = f"A study design characterized by: {', '.join(sorted(phrases)[:5])}"

    # Use the highest-confidence paper as the primary source
    papers_sorted = sorted(papers, key=lambda p: p["confidence"], reverse=True)
    primary_source = papers_sorted[0] if papers_sorted else None

    source_entry = {}
    if primary_source:
        source_entry = {
            "paperRef": primary_source["ref"],
            "role": "primary-design",
        }

    return {
        "templateVersion": 1,
        "templateId": cluster_id,
        "title": title,
        "description": description,
        "designType": design_type,
        "designSignature": sorted(phrases)[:10],  # Top 10 phrases
        "dataPath": "archive",  # Could be 'live' for active data collection
        "source": [source_entry] if source_entry else [],
        "parameters": {
            "studyId": {
                "type": "string",
                "default": cluster_id,
            },
            "title": {
                "type": "string",
                "default": title,
            },
            "participants": {
                "type": "participants",
                "default": 20,
                "min": 1,
            },
        },
        "measures": [
            {
                "id": "primary-outcome",
                "leg": "behavioral",
                "elements": ["task_outcome"],
                "description": "Study outcome measurement",
            }
        ],
        "statisticalPlan": {
            "unit": "participant",
            "perRQ": [
                {
                    "rq": "RQ-1",
                    "outcome": "primary measure",
                    "test": recipe,
                    "effectSize": "cohens-d",
                }
            ],
        },
        "threats": [],
        "protocolSkeleton": {
            "protocolVersion": 4,
            "study": {
                "id": "{{ studyId }}",
                "title": "{{ title }}",
                "researchers": ["Researcher"],
                "ethicsRef": "pending: not yet obtained",
            },
            "researchQuestions": [
                {
                    "id": "RQ-1",
                    "text": "What are the outcomes of this study?",
                }
            ],
            "conditions": ["control", "treatment"],
            "participants": {
                "planned": "{{ participants }}",
                "design": "between-subjects",
                "counterbalanced": False,
            },
            "session": {
                "durationMinutes": 60,
                "taskDescription": "Research task",
            },
            "instruments": {},
            "phases": [
                {"name": "design", "gates": []},
                {"name": "ethics", "gates": []},
                {"name": "data-collection", "gates": []},
                {"name": "analysis", "gates": []},
            ],
            "analysisPlan": [
                {
                    "rq": "RQ-1",
                    "recipes": [recipe],
                }
            ],
        },
    }


def mine_and_draft(
    s: Session, output_dir: Path | None = None, write_files: bool = True
) -> list[dict]:
    """Mine the corpus and generate draft templates."""
    if output_dir is None:
        root = Path(__file__).resolve().parent.parent.parent
        output_dir = root / "templates" / "drafts"

    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    log.info("Clustering papers by design characteristics...")
    clusters = cluster_papers_by_designs(s)
    log.info(f"Found {len(clusters)} unique design phrase combinations")

    log.info("Ranking clusters by paper count...")
    top_clusters = identify_top_clusters(clusters, min_papers=3)
    log.info(f"Top {len(top_clusters)} clusters have 3+ papers")

    drafts = []
    for i, (phrases, count) in enumerate(top_clusters):
        cluster_id = f"mined-design-{i+1:02d}-v1"
        design_type = infer_design_type(phrases)
        recipe = infer_analysis_recipe(phrases)
        papers = clusters[phrases]

        draft = draft_template_yaml(cluster_id, phrases, papers, design_type, recipe)

        # Validate
        problems = template_registry.validate_template(draft)
        status = "✓" if not problems else "✗"
        log.info(f"{status} {cluster_id}: {count} papers, {len(phrases)} phrases")
        if problems:
            log.warning(f"  Problems: {problems}")

        drafts.append({
            "id": cluster_id,
            "count": count,
            "phrases": sorted(phrases),
            "template": draft,
            "valid": len(problems) == 0,
            "problems": problems,
        })

        # Write draft YAML file if requested
        if write_files:
            yaml_path = output_dir / f"{cluster_id}.yaml"
            try:
                import yaml
                yaml.dump(
                    draft,
                    yaml_path.open("w"),
                    default_flow_style=False,
                    sort_keys=False,
                )
                log.info(f"  → {yaml_path.name}")
            except ImportError:
                log.warning(
                    f"  PyYAML not available; skipping file write for {cluster_id}"
                )

    return drafts


def report_drafts(drafts: list[dict]) -> str:
    """Generate a summary report of drafted templates."""
    lines = [
        "# Corpus Mining Report",
        "",
        f"Generated {len(drafts)} draft templates from corpus clusters.",
        "",
        "## Summary by Validity",
        "",
    ]

    valid_count = sum(1 for d in drafts if d["valid"])
    invalid_count = len(drafts) - valid_count

    lines.append(f"- Valid: {valid_count}")
    lines.append(f"- Invalid: {invalid_count}")
    lines.append("")

    lines.append("## Drafts (sorted by paper count)")
    lines.append("")

    for draft in sorted(drafts, key=lambda d: -d["count"]):
        status = "✓ valid" if draft["valid"] else "✗ invalid"
        lines.append(
            f"- **{draft['id']}**: {draft['count']} papers {status}"
        )
        lines.append(f"  Phrases: {', '.join(draft['phrases'][:5])}…")
        if draft["problems"]:
            for problem in draft["problems"][:2]:
                lines.append(f"  - {problem}")

    return "\n".join(lines)
