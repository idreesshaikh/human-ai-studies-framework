"""``analysis paper`` - write the draft to disk (FR-ANA-6)."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import matplotlib.pyplot as plt

from analysis.dataset import Dataset
from analysis.paper import build_paper


def _fetch_papers(server: str, study_id: str) -> list[dict]:
    """Ingested-paper metadata for related work + bib; [] when offline."""
    try:
        url = f"{server.rstrip('/')}/studies/{study_id}/papers"
        with urllib.request.urlopen(url, timeout=5) as res:
            return json.loads(res.read())
    except OSError:
        return []


def write_paper(
    protocol: dict,
    dataset: Dataset,
    study_id: str,
    out_dir: Path,
    *,
    papers: list[dict] | None = None,
) -> tuple[Path, list[dict]]:
    """Build and persist the draft; returns (out_dir, specification findings)."""
    draft = build_paper(protocol, dataset, study_id, papers=papers)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "draft.md").write_text(draft.markdown)
    (out_dir / "draft.tex").write_text(draft.latex)
    (out_dir / "references.bib").write_text(draft.bib)
    if draft.figures:
        fig_dir = out_dir / "figures"
        fig_dir.mkdir(exist_ok=True)
        for name, fig in draft.figures.items():
            for ext in ("pdf", "png"):
                fig.savefig(
                    fig_dir / f"{name}.{ext}",
                    dpi=150,
                    facecolor=fig.get_facecolor(),
                    bbox_inches="tight",
                )
            plt.close(fig)
    return out_dir, draft.findings


def cmd_paper(protocol: dict, dataset: Dataset, study_id: str, args) -> int:
    server = None if args.dataset else args.server
    papers = _fetch_papers(server, study_id) if server else None
    out_dir = Path(args.out) / study_id / "paper"
    out_dir, findings = write_paper(protocol, dataset, study_id, out_dir, papers=papers)
    print(f"paper draft: {out_dir / 'draft.tex'} (+ draft.md, references.bib)")
    if findings:
        print(
            f"warning: {len(findings)} specification defect(s) - the methods "
            "section has TODO gaps (logged as RQ-F1 findings, FR-META-1):"
        )
        for f in findings:
            print(f"  - {f['message']}")
        if server:
            _record(server, findings)
    print(f"compile: cd {out_dir} && pdflatex draft && bibtex draft && pdflatex draft")
    return 2 if findings else 0


def _record(server: str, findings: list[dict]) -> None:
    for finding in findings:
        try:
            req = urllib.request.Request(
                f"{server.rstrip('/')}/findings",
                data=json.dumps(finding).encode(),
                headers={"content-type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except OSError:
            return
