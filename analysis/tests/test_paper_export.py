"""
Paper draft export (FR-ANA-6): golden file, determinism, protocol-derived methods,
results embedding, and specification-defect logging (FR-META-1).
"""

import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import analysis.recipes  # noqa: F401 - register recipes
import matplotlib.pyplot as plt
import pytest
import yaml
from analysis.dataset import Dataset
from analysis.paper import build_paper
from analysis.paper_cli import write_paper
from protocol.loader import load_protocol
from tests_support import synthetic_rows

REPO = Path(__file__).resolve().parents[2]
PILOT = REPO / "protocol" / "examples" / "pilot-study.yaml"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _close_figures():
    # build_paper returns drafts holding open figures; only write_paper closes them, so
    # tests that never write would accumulate past pyplot's 20-figure warning threshold.
    yield
    plt.close("all")


def _protocol() -> dict:
    return load_protocol(PILOT)


def test_golden_draft_is_byte_identical():
    draft = build_paper(_protocol(), Dataset(rows=[]), "pilot-2026")
    assert draft.markdown == (FIXTURES / "golden-draft.md").read_text()
    assert draft.latex == (FIXTURES / "golden-draft.tex").read_text()
    assert draft.bib == (FIXTURES / "golden-references.bib").read_text()


def test_regeneration_is_identical():
    """FR-ANA-6 / NFR-6: same protocol + dataset -> identical draft."""
    ds = Dataset(rows=synthetic_rows())
    a = build_paper(_protocol(), ds, "pilot-2026")
    b = build_paper(_protocol(), ds, "pilot-2026")
    assert a.markdown == b.markdown
    assert a.latex == b.latex
    assert a.bib == b.bib


def test_methods_carry_real_probe_intervals_and_metric_definitions():
    draft = build_paper(_protocol(), Dataset(rows=[]), "pilot-2026")
    tex = draft.latex
    assert "15 minutes" in tex
    assert "90 seconds" in tex
    assert "Parameter count" in tex and "Miller" in tex
    assert "\\citep{miller1956}" in tex
    assert "within-subjects" in tex and "counterbalanced" in tex


def test_every_rq_and_trace_tag_is_present():
    draft = build_paper(_protocol(), Dataset(rows=[]), "pilot-2026")
    for rq in ("RQ-P1", "RQ-P2", "RQ-P3", "RQ-P4", "RQ-P5"):
        assert f"%% trace: {rq}" in draft.latex or rq in draft.latex
    assert draft.latex.count("%% trace:") >= 10
    assert "Threats to validity" in draft.latex


def test_results_embed_recipe_summary_and_figures_with_data():
    ds = Dataset(rows=synthetic_rows())
    draft = build_paper(_protocol(), ds, "pilot-2026")
    assert "fatigue-by-condition" in draft.latex
    assert "\\includegraphics" in draft.latex
    assert any(name.startswith("fatigue-by-condition_") for name in draft.figures)
    assert "\\toprule" in draft.latex and "\\bottomrule" in draft.latex


def test_missing_protocol_field_is_logged_as_specification_defect():
    doc = yaml.safe_load(PILOT.read_text())
    del doc["conditions"]
    draft = build_paper(doc, Dataset(rows=[]), "pilot-2026")
    kinds = {f["kind"] for f in draft.findings}
    assert "protocol-validation" in kinds
    assert any(f["requirementId"] == "FR-PROT-1" for f in draft.findings)
    # The gap is visible in the draft, not silently dropped.
    assert "TODO" in draft.markdown


def test_latex_environments_and_braces_balanced():
    ds = Dataset(rows=synthetic_rows())
    tex = build_paper(_protocol(), ds, "pilot-2026").latex
    assert "\\documentclass" in tex
    assert "\\begin{document}" in tex and "\\end{document}" in tex
    assert "\\usepackage{booktabs}" in tex and "\\usepackage{natbib}" in tex
    begins = Counter(re.findall(r"\\begin\{(\w+\*?)\}", tex))
    ends = Counter(re.findall(r"\\end\{(\w+\*?)\}", tex))
    assert begins == ends, (begins - ends, ends - begins)
    body = "\n".join(ln for ln in tex.splitlines() if not ln.lstrip().startswith("%"))
    assert body.count("{") == body.count("}")


def test_draft_compiles_to_pdf_when_a_tex_engine_is_present(tmp_path):
    """
    Acceptance (FR-ANA-6): the emitted draft.tex compiles to a real PDF. Skips where no
    TeX engine is installed (CI, dev boxes without TeX) - the structural-validity test
    above stands in there.
    """
    engine = shutil.which("tectonic") or shutil.which("pdflatex")
    if not engine:
        pytest.skip("no TeX engine (tectonic/pdflatex) on PATH")

    out = tmp_path / "paper"
    write_paper(_protocol(), Dataset(rows=synthetic_rows()), "pilot-2026", out)
    tex = out / "draft.tex"

    if engine.endswith("tectonic"):
        cmd = [engine, "--outdir", str(out), str(tex)]
    else:
        subprocess.run(
            [engine, "-interaction=nonstopmode", "draft.tex"],
            cwd=out,
            capture_output=True,
        )
        subprocess.run(
            [shutil.which("bibtex") or "bibtex", "draft"], cwd=out, capture_output=True
        )
        subprocess.run(
            [engine, "-interaction=nonstopmode", "draft.tex"],
            cwd=out,
            capture_output=True,
        )
        cmd = [engine, "-interaction=nonstopmode", "draft.tex"]

    result = subprocess.run(cmd, cwd=out, capture_output=True, text=True)
    pdf = out / "draft.pdf"
    assert pdf.is_file() and pdf.stat().st_size > 0, result.stderr[-2000:]


def test_related_work_and_bib_from_protocol_literature():
    draft = build_paper(_protocol(), Dataset(rows=[]), "pilot-2026")
    assert "arxiv_2302_06590" in draft.bib
    assert "\\citep{arxiv_2302_06590}" in draft.latex
    assert "@misc{miller1956" in draft.bib


def test_curated_threats_record_injected():
    """
    FR-CUR-3 F3.1: a curated dataset's validity-threats record is injected verbatim into
    the paper's threats section, with heuristic citations.
    """
    record = {
        "samplingFrame": {
            "query": "repo:example/app is:merged",
            "window": {"start": "2025-01-01", "end": "2025-06-30"},
            "actorUnit": "developer",
            "contentPolicy": "metadata-only",
        },
        "heuristics": [
            {
                "id": "bot-suffix",
                "version": 1,
                "cite": "aidev-ai-coding-agents-github",
                "knownFailureModes": ["renamed bots"],
            }
        ],
        "biases": [
            {
                "description": "merged-only conditioning",
                "direction": "over-states agent success",
                "mitigation": "report unmerged coverage",
            }
        ],
        "coverage": {
            "requested": 6,
            "retrieved": 5,
            "dropped": {"excluded-by-inclusion-rule": 1},
        },
    }
    draft = build_paper(
        _protocol(), Dataset(rows=[]), "pilot-2026", threats_record=record
    )
    md = draft.markdown
    assert "Data provenance (curated dataset)" in md
    assert "repo:example/app is:merged" in md
    assert "bot-suffix" in md and "aidev-ai-coding-agents-github" in md
    assert "excluded-by-inclusion-rule" in md
    plain = build_paper(_protocol(), Dataset(rows=[]), "pilot-2026").markdown
    assert "Data provenance (curated dataset)" not in plain
