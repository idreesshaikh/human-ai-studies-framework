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

DESIGN_KEYWORDS = {
    "between-subjects": ["between subjects", "between-subject", "independent groups"],
    "control group": ["control group", "control condition", "untreated control"],
    "treatment group": ["treatment group", "treatment condition", "experimental group"],
    "randomly assigned": ["randomly assigned", "random assignment", "randomized"],
    "within-subjects": ["within subjects", "within-subject", "repeated measures"],
    "counterbalanced": ["counterbalanced", "counterbalancing", "counterbalance order"],
    "crossover": ["crossover", "cross-over"],
    "observational": [
        "observational study",
        "observational research",
        "non-experimental",
    ],
    "field study": ["field study", "field research", "naturalistic"],
    "survey": ["survey study", "questionnaire", "self-report"],
    "experiment": ["experiment", "experimental", "controlled experiment"],
    "single-arm": ["single arm", "single-arm", "single group"],
    "benchmark": ["benchmark evaluation", "benchmark study"],
    "multi-arm": ["multi-arm", "multi arm", "multiple arms"],
    "behavioral": ["behavioral data", "user behavior", "logging"],
    "telemetry": ["telemetry", "event logging", "event capture"],
    "self-report": ["self-report", "self report", "questionnaire"],
    "assessment": ["assessment", "measuring", "measurement"],
    "qualitative": ["qualitative", "thematic analysis", "coding"],
    "quantitative": ["quantitative", "statistical analysis", "hypothesis testing"],
    "mixed-methods": ["mixed methods", "mixed-method"],
    "descriptive": ["descriptive", "descriptive statistics"],
    "longitudinal": ["longitudinal", "over time", "time series"],
    "cross-sectional": ["cross-sectional", "cross section"],
    "replicated": ["replicated", "replication", "replicate"],
}

DESIGN_PHRASES = set()
for variants in DESIGN_KEYWORDS.values():
    DESIGN_PHRASES.update(variants)


def extract_design_phrases(text: str) -> set[str]:
    """Find all recognized design phrases in a text (title + abstract)."""
    text_lower = text.lower()
    found = set()
    for phrase in DESIGN_PHRASES:
        pattern = rf"(?<![a-z0-9])({re.escape(phrase)})(?![a-z0-9])"
        if re.search(pattern, text_lower):
            found.add(phrase)
    return found


_METHOD_HEADS = (
    "study",
    "studies",
    "experiment",
    "trial",
    "evaluation",
    "analysis",
    "comparison",
    "survey",
    "review",
    "deployment",
)

_NOT_A_METHOD = (
    "code review",
    "peer review",
    "the review",
    "this review",
    "literature review",
    "systematic review",
    "scoping review",
    "comprehensive review",
    "critical review",
    "narrative review",
    "umbrella review",
    "meta-analysis",
    "comprehensive survey",
    "systematic survey",
)

_PHRASE_RE = re.compile(r"[a-z][a-z0-9-]*(?:\s+[a-z][a-z0-9-]*){0,2}")

_LEADING_NOISE = (
    "a",
    "an",
    "the",
    "this",
    "that",
    "our",
    "its",
    "their",
    "these",
    "those",
    "and",
    "or",
    "of",
    "for",
    "with",
    "in",
    "on",
    "to",
    "from",
    "by",
    "as",
    "we",
    "is",
    "was",
    "are",
    "were",
    "present",
    "presents",
    "propose",
)


def _normalise_phrase(phrase: str) -> str:
    """Drop leading articles/connectives; "" when nothing meaningful is left."""
    words = phrase.split()
    while words and words[0] in _LEADING_NOISE:
        words.pop(0)
    return " ".join(words) if len(words) >= 2 else ""


def uncovered_methodology_phrases(
    s: Session, *, min_papers: int = 5, limit: int = 40
) -> list[dict]:
    """
    Methodology phrases the corpus uses that **no registry template claims**.

    This is the registry's blind-spot report: for each candidate phrase it
    returns how many corpus papers describe themselves with it, so a human can
    see at a glance which real design archetypes the repertoire has no shape
    for. It is the automated form of the manual scan that found
    ``field-experiment-v1`` and ``cognitive-load-comparison-v1``  -  both of
    which had real support and matched none of the then-13 templates.

    Deliberately *not* wired into template drafting: a phrase is evidence that
    a design exists in the literature, not a design. Authoring the shape it
    implies (its statistics, its instruments, its threats) is human work.
    """
    covered: set[str] = set()
    for tpl in template_registry.list_templates():
        for phrase in tpl.get("designSignature", []) or []:
            covered.add(str(phrase).strip().lower())

    papers = s.execute(
        select(Paper.paper_ref, Paper.title, Paper.abstract).where(
            Paper.study_id == CORPUS_STUDY_ID
        )
    ).all()

    counts: dict[str, int] = {}
    for _ref, title, abstract in papers:
        text = f"{title or ''} {abstract or ''}".lower()
        seen_here: set[str] = set()
        for match in _PHRASE_RE.finditer(text):
            phrase = match.group(0).strip()
            if not phrase.endswith(_METHOD_HEADS):
                continue
            phrase = _normalise_phrase(phrase)

            if not phrase:
                continue
            if phrase in covered or any(bad in phrase for bad in _NOT_A_METHOD):
                continue
            seen_here.add(phrase)
        for phrase in seen_here:
            counts[phrase] = counts.get(phrase, 0) + 1

    ranked = [
        {"phrase": phrase, "papers": n}
        for phrase, n in counts.items()
        if n >= min_papers
    ]
    ranked.sort(key=lambda r: (-r["papers"], r["phrase"]))
    return ranked[:limit]


def cluster_papers_by_designs(s: Session) -> dict[frozenset[str], list[dict]]:
    """Group corpus papers by their design characteristics."""

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
        clusters[cluster_key].append(
            {
                "ref": ref,
                "title": title or "",
                "confidence": matching.paper_confidence(score),
            }
        )

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

    if any(
        p in phrases
        for p in ["between subjects", "between-subject", "independent groups"]
    ):
        if any(p in phrases for p in ["randomly assigned", "randomized", "rct"]):
            return "rct-between-subjects"
        return "observational"

    if any(
        p in phrases for p in ["within subjects", "within-subject", "repeated measures"]
    ):
        if "crossover" in phrases:
            return "rct-within-subjects"
        return "quasi-experiment"

    if any(p in phrases for p in ["observational", "field study", "naturalistic"]):
        return "observational"

    if any(p in phrases for p in ["survey", "questionnaire", "self-report"]):
        return "survey"

    if any(p in phrases for p in ["single arm", "single-arm", "single group"]):
        return "case-study"

    if any(p in phrases for p in ["benchmark", "benchmark evaluation"]):
        return "case-study"

    return "lab-experiment"


_TEST_FOR_RECIPE = {
    "two-group-nonparametric": ("mann-whitney-u", "cliffs-delta"),
    "paired-nonparametric": ("wilcoxon-signed-rank", "matched-pairs rank-biserial"),
}


def infer_analysis_recipe(phrases: frozenset[str]) -> str:
    """Guess a recipe ID based on the phrase set."""

    if any(p in phrases for p in ["multi arm", "multi-arm", "multiple arms"]):
        return "two-group-nonparametric"

    if any(
        p in phrases for p in ["between subjects", "between-subject", "control group"]
    ):
        if any(p in phrases for p in ["randomly assigned", "rct", "randomized"]):
            return "two-group-nonparametric"
        return "two-group-nonparametric"

    if any(
        p in phrases for p in ["within subjects", "within-subject", "repeated measures"]
    ):
        if "crossover" in phrases:
            return "paired-nonparametric"
        return "paired-nonparametric"

    if "crossover" in phrases or "paired" in phrases:
        return "paired-nonparametric"

    if any(p in phrases for p in ["observational", "field study", "naturalistic"]):
        return "paired-nonparametric"

    if any(p in phrases for p in ["survey", "questionnaire", "self-report"]):
        return "two-group-nonparametric"

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
    test, effect_size = _TEST_FOR_RECIPE.get(recipe, ("mann-whitney-u", "cliffs-delta"))

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
        "designSignature": sorted(phrases)[:10],
        "dataPath": "live",
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
                    "test": test,
                    "effectSize": effect_size,
                    "smallN": "hypothesis-generating",
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
        cluster_id = f"mined-design-{i + 1:02d}-v1"
        design_type = infer_design_type(phrases)
        recipe = infer_analysis_recipe(phrases)
        papers = clusters[phrases]

        draft = draft_template_yaml(cluster_id, phrases, papers, design_type, recipe)

        problems = template_registry.validate_template(draft)
        status = "✓" if not problems else "✗"
        log.info(f"{status} {cluster_id}: {count} papers, {len(phrases)} phrases")
        if problems:
            log.warning(f"  Problems: {problems}")

        drafts.append(
            {
                "id": cluster_id,
                "count": count,
                "phrases": sorted(phrases),
                "template": draft,
                "valid": len(problems) == 0,
                "problems": problems,
            }
        )

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
        lines.append(f"- **{draft['id']}**: {draft['count']} papers {status}")
        lines.append(f"  Phrases: {', '.join(draft['phrases'][:5])}…")
        if draft["problems"]:
            for problem in draft["problems"][:2]:
                lines.append(f"  - {problem}")

    return "\n".join(lines)


def write_drafts(drafts: list[dict], output_dir: Path | None = None) -> list[Path]:
    """
    Write mined draft templates to ``templates/drafts/`` as YAML files, for review
    as a diff before anything reaches ``templates/registry/``.

    Mining never writes into the registry itself. A mined draft is a proposal, and
    promoting one is a human decision made the same way every other change to the
    repertoire is made  -  by reading the YAML and committing it. Only drafts that
    validated are written; a draft with problems is left for the mining report to
    surface rather than dropped into the tree for someone to trip over.
    """
    import yaml

    if output_dir is None:
        root = Path(__file__).resolve().parent.parent.parent.parent
        output_dir = root / "templates" / "drafts"
    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for draft in drafts:
        if not draft["valid"]:
            continue
        dest = output_dir / f"{draft['id']}.yaml"
        dest.write_text(
            yaml.safe_dump(draft["template"], sort_keys=False, default_flow_style=False)
        )
        written.append(dest)
    return written
