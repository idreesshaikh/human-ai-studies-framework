"""Paper draft export (FR-ANA-6): golden file, determinism, protocol-derived
methods, results embedding, and specification-defect logging (FR-META-1)."""

import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import analysis.recipes  # noqa: F401 - register recipes
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


def _protocol() -> dict:
    return load_protocol(PILOT)


# --- golden file (empty dataset -> purely protocol-derived, deterministic) ---


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


# --- methods synthesised from the protocol -----------------------------------


def test_methods_carry_real_probe_intervals_and_metric_definitions():
    draft = build_paper(_protocol(), Dataset(rows=[]), "pilot-2026")
    tex = draft.latex
    # Real probe interval (15 min) + stuck threshold (90 s) from the protocol.
    assert "15 minutes" in tex
    assert "90 seconds" in tex
    # Metric definitions from the declared cognitive-load-9 set, with cites.
    assert "Parameter count" in tex and "Miller" in tex
    assert "\\citep{miller1956}" in tex
    # Counterbalancing + within-subjects design synthesised from the protocol.
    assert "within-subjects" in tex and "counterbalanced" in tex


def test_every_rq_and_trace_tag_is_present():
    draft = build_paper(_protocol(), Dataset(rows=[]), "pilot-2026")
    for rq in ("RQ-P1", "RQ-P2", "RQ-P3", "RQ-P4", "RQ-P5"):
        assert f"%% trace: {rq}" in draft.latex or rq in draft.latex
    assert draft.latex.count("%% trace:") >= 10
    assert "Threats to validity" in draft.latex


# --- results embed the recipe outputs ----------------------------------------


def test_results_embed_recipe_summary_and_figures_with_data():
    ds = Dataset(rows=synthetic_rows())
    draft = build_paper(_protocol(), ds, "pilot-2026")
    # fatigue-by-condition runs on the synthetic data: its summary + figure
    # land in the RQ-P1 results, and the figure file is emitted.
    assert "fatigue-by-condition" in draft.latex
    assert "\\includegraphics" in draft.latex
    assert any(name.startswith("fatigue-by-condition_") for name in draft.figures)
    # Booktabs tables appear.
    assert "\\toprule" in draft.latex and "\\bottomrule" in draft.latex


# --- specification-defect logging (FR-META-1 / RQ-F1) ------------------------


def test_missing_protocol_field_is_logged_as_specification_defect():
    doc = yaml.safe_load(PILOT.read_text())
    del doc["conditions"]  # a field the methods section needs
    draft = build_paper(doc, Dataset(rows=[]), "pilot-2026")
    kinds = {f["kind"] for f in draft.findings}
    assert "protocol-validation" in kinds
    assert any(f["requirementId"] == "FR-PROT-1" for f in draft.findings)
    # The gap is visible in the draft, not silently dropped.
    assert "TODO" in draft.markdown


# --- LaTeX is structurally valid (pdflatex proxy) ----------------------------


def test_latex_environments_and_braces_balanced():
    ds = Dataset(rows=synthetic_rows())
    tex = build_paper(_protocol(), ds, "pilot-2026").latex
    assert "\\documentclass" in tex
    assert "\\begin{document}" in tex and "\\end{document}" in tex
    assert "\\usepackage{booktabs}" in tex and "\\usepackage{natbib}" in tex
    begins = Counter(re.findall(r"\\begin\{(\w+\*?)\}", tex))
    ends = Counter(re.findall(r"\\end\{(\w+\*?)\}", tex))
    assert begins == ends, (begins - ends, ends - begins)
    body = "\n".join(
        ln for ln in tex.splitlines() if not ln.lstrip().startswith("%")
    )
    assert body.count("{") == body.count("}")


# --- real compilation (acceptance: run a TeX engine to prove it) -------------


def test_draft_compiles_to_pdf_when_a_tex_engine_is_present(tmp_path):
    """Acceptance (FR-ANA-6): the emitted draft.tex compiles to a real PDF.

    Skips where no TeX engine is installed (CI, dev boxes without TeX) - the
    structural-validity test above stands in there. ``tectonic`` is preferred
    (self-contained, runs the full bib pipeline); ``pdflatex`` is the fallback
    the acceptance criterion names verbatim."""
    engine = shutil.which("tectonic") or shutil.which("pdflatex")
    if not engine:
        pytest.skip("no TeX engine (tectonic/pdflatex) on PATH")

    out = tmp_path / "paper"
    write_paper(_protocol(), Dataset(rows=synthetic_rows()), "pilot-2026", out)
    tex = out / "draft.tex"

    if engine.endswith("tectonic"):
        # Tectonic drives latex + bib + xdvipdfmx itself; fetches only the
        # packages the preamble needs.
        cmd = [engine, "--outdir", str(out), str(tex)]
    else:
        # Two pdflatex passes bracket bibtex so \citep resolves; run in the
        # paper dir so the relative figures/ + references.bib paths resolve.
        subprocess.run([engine, "-interaction=nonstopmode", "draft.tex"],
                       cwd=out, capture_output=True)
        subprocess.run([shutil.which("bibtex") or "bibtex", "draft"],
                       cwd=out, capture_output=True)
        subprocess.run([engine, "-interaction=nonstopmode", "draft.tex"],
                       cwd=out, capture_output=True)
        cmd = [engine, "-interaction=nonstopmode", "draft.tex"]

    result = subprocess.run(cmd, cwd=out, capture_output=True, text=True)
    pdf = out / "draft.pdf"
    assert pdf.is_file() and pdf.stat().st_size > 0, result.stderr[-2000:]


def test_related_work_and_bib_from_protocol_literature():
    draft = build_paper(_protocol(), Dataset(rows=[]), "pilot-2026")
    # The three literature refs become cite keys + bib entries.
    assert "arxiv_2302_06590" in draft.bib
    assert "\\citep{arxiv_2302_06590}" in draft.latex
    # Metric citation stubs are present so \citep resolves under pdflatex.
    assert "@misc{miller1956" in draft.bib
