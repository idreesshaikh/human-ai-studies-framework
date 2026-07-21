"""Paper draft export (FR-ANA-6) - the write-up phase as a build artifact.

``analysis paper <protocol.yaml>`` synthesises a Markdown + LaTeX draft from
the *frozen protocol* and the *recipe results* - deterministically, with **no
LLM in the pipeline** (NFR-6: reproducibility is the point; the golden-file
test regenerates an identical draft). The retrospective (Part C) is where
Claude drafts *proposals*; the paper is pure templating.

Section provenance:

- **Methods** are *synthesised from the protocol, not hand-written*:
  participants plan, conditions, counterbalancing, session structure, the
  instruments with their exact configs (probe intervals, thresholds), the
  metric set with definitions + citations, and the ethics/consent procedure.
  If a field the methods section needs is absent, the protocol was
  incomplete - that is an **RQ-F1 specification defect**, logged as a
  finding (FR-META-1), and the draft carries a visible ``\\todo`` gap.
- **Results** come per-RQ from the recipes: each recipe's methods text, its
  summary (exact tests + effect sizes + per-cell n, NFR-8 verbatim), its
  tables (booktabs), and its figures (``\\includegraphics``).
- **Related work** is seeded from the protocol's literature links (FR-LIT-3),
  grouped by what each paper justifies, with a generated ``references.bib``.

Every generated claim carries a trace comment (``%% trace: RQ / recipe /
requirement``) so a reader can walk protocol -> data field -> claim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd
from matplotlib.figure import Figure

from analysis.core import REGISTRY, RecipeResult, validate_plan
from analysis.dataset import Dataset

# The cognitive-load-9 metric set (metrics/docs/static_code_metrics.md): the
# framework's own definitions + the elicitation source each traces to. Keyed
# by the metric-set name the protocol declares, so the methods section stays
# protocol-driven (the *set* is named in the protocol; the definitions are
# framework knowledge).
METRIC_SETS: dict[str, list[tuple[str, str, str]]] = {
    "cognitive-load-9": [
        (
            "Nesting penalty",
            "weighted count of nested control structures",
            "nejmeh1988",
        ),
        (
            "Cognitive complexity",
            "SonarSource cognitive-complexity score",
            "campbell2018",
        ),
        (
            "Parameter count",
            "arity vs Miller's 7+/-2 working-memory bound",
            "miller1956",
        ),
        (
            "Halstead effort",
            "Halstead's effort measure over operators/operands",
            "halstead1977",
        ),
        (
            "Scope distance",
            "mean lines between a name's definition and use",
            "nejmeh1988",
        ),
        (
            "Indentation variance",
            "variance of leading-whitespace depth per file",
            "hindle2008",
        ),
        ("Line width", "mean/bounded source line length", "hindle2008"),
        ("Identifier length", "mean identifier character length", "lawrie2006"),
        ("Comment ratio", "comment lines / source lines", "nejmeh1988"),
    ],
}

#: ``\todo{...}`` fallbacks kept out of f-string expression parts (literal
#: braces in an f-string expression are a parse hazard).
_TODO = {k: "\\todo{" + k + "}" for k in ("n", "conditions", "duration", "ref")}
_TODO["q"] = "\\todo{?}"
_TODO["verify"] = "\\todo{verify}"


@dataclass
class PaperDraft:
    """The generated draft: Markdown + LaTeX bodies, a ``references.bib``, the
    recipe figures to write, and any specification defects found (FR-META-1)."""

    markdown: str
    latex: str
    bib: str
    figures: dict[str, Figure] = field(default_factory=dict)
    findings: list[dict] = field(default_factory=list)


def build_paper(
    protocol: dict,
    dataset: Dataset,
    study_id: str,
    *,
    papers: list[dict] | None = None,
    threats_record: dict | None = None,
) -> PaperDraft:
    """Assemble the draft. ``papers`` is the study's ingested-paper metadata
    (from the middleware ``/papers`` endpoint) for richer related-work + bib;
    when absent, the protocol's ``literature:`` list is used (still
    deterministic). ``threats_record`` is a curated dataset's validity-threats
    record (FR-CUR-3); when present its provenance detail — sampling frame,
    the authorship heuristics with their citations, declared biases, and
    coverage — is injected verbatim into the threats section (F3.1)."""
    findings: list[dict] = []
    results, figures = _run_recipes(dataset, protocol)
    lit = _literature(protocol, papers)

    md: list[str] = []
    tex: list[str] = _tex_preamble(protocol)

    _title(protocol, dataset, md, tex, findings)
    _intro(protocol, md, tex)
    _related_work(lit, md, tex)
    _methods(protocol, md, tex, findings)
    _results(protocol, results, figures, md, tex)
    _threats(md, tex, threats_record)

    tex.append("\\bibliographystyle{plainnat}")
    tex.append("\\bibliography{references}")
    tex.append("\\end{document}")

    return PaperDraft(
        markdown="\n".join(md) + "\n",
        latex="\n".join(tex) + "\n",
        bib=_bib(lit),
        figures={name: fig for name, fig in figures.items()},
        findings=findings,
    )


# ------------------------------------------------------------- recipe runs


def _run_recipes(
    dataset: Dataset, protocol: dict
) -> tuple[dict[str, RecipeResult], dict[str, Figure]]:
    """Run every satisfiable recipe the plan names, once. Figures are keyed
    ``<recipe>_<figname>`` for stable, collision-free filenames."""
    plan = protocol.get("analysisPlan", [])
    results: dict[str, RecipeResult] = {}
    figures: dict[str, Figure] = {}
    ran: set[str] = set()
    for check in validate_plan(plan, dataset):
        if not check.ok or check.recipe_id in ran:
            continue
        ran.add(check.recipe_id)
        try:
            result = REGISTRY[check.recipe_id].run(dataset)
        except Exception:  # noqa: BLE001 - a broken recipe never kills the draft
            continue
        results[check.recipe_id] = result
        for name, fig in result.figures.items():
            figures[f"{check.recipe_id}_{name}"] = fig
    return results, figures


# --------------------------------------------------------------- sections


def _title(
    protocol: dict, dataset: Dataset, md: list, tex: list, findings: list
) -> None:
    study = protocol.get("study", {})
    title = study.get("title") or f"Study {study.get('id', '')}"
    authors = study.get("researchers", []) or ["Anonymous"]
    conditions = protocol.get("conditions", [])
    planned = protocol.get("participants", {}).get("planned")
    n_actual = _participant_count(dataset)

    trace = "RQ-F1 / protocol.study / FR-PROT-1"
    md += [
        f"<!-- trace: {trace} -->",
        f"# {title}",
        "",
        "**" + "; ".join(authors) + "**",
        "",
    ]
    tex += [
        f"%% trace: {trace}",
        f"\\title{{{_tex(title)}}}",
        "\\author{" + " \\and ".join(_tex(a) for a in authors) + "}",
        "\\date{}",
        "\\begin{document}",
        "\\maketitle",
        "",
    ]

    n_str = f"{n_actual} of a planned {planned}" if planned else f"{n_actual}"
    conds = ", ".join(conditions) if conditions else _TODO["conditions"]
    abstract = (
        f"We report a within-subjects study of {conds} with {n_str} "
        f"participants. {_TODO['verify']} State the headline effect size and "
        f"exact test per research question from the Results section."
    )
    md += ["## Abstract", "", f"<!-- trace: {trace} -->", _md_todo(abstract), ""]
    tex += [
        "\\begin{abstract}",
        f"%% trace: {trace}",
        _tex_keep_todo(abstract),
        "\\end{abstract}",
        "",
    ]


def _intro(protocol: dict, md: list, tex: list) -> None:
    md += ["## Introduction and research questions", ""]
    tex += ["\\section{Introduction and research questions}", ""]
    for rq in protocol.get("researchQuestions", []):
        rid = rq.get("id", "")
        text = " ".join((rq.get("text") or "").split())
        md += [f"<!-- trace: {rid} -->", f"**{rid}.** {text}", ""]
        tex += [f"%% trace: {rid}", f"\\paragraph{{{rid}.}} {_tex(text)}", ""]


def _related_work(lit: list[dict], md: list, tex: list) -> None:
    md += ["## Related work", ""]
    tex += ["\\section{Related work}", ""]
    if not lit:
        md += ["`TODO: no linked literature (FR-LIT-3).`", ""]
        tex += ["\\todo{no linked literature (FR-LIT-3)}", ""]
        return
    # Group by the first thing each paper justifies (deterministic order).
    by_group: dict[str, list[dict]] = {}
    for entry in lit:
        group = (entry["justifies"] or ["general"])[0]
        by_group.setdefault(group, []).append(entry)
    for group in sorted(by_group):
        md += [f"### Grounding {group}", ""]
        tex += [f"\\subsection{{Grounding {_tex(group)}}}", ""]
        for entry in by_group[group]:
            key = entry["citeKey"]
            just = ", ".join(entry["justifies"]) or "the study design"
            claim = f"{entry['label']} motivates {just}."
            md += [
                f"<!-- trace: FR-LIT-3 / {entry['ref']} -->",
                f"{claim} [@{key}] `TODO: summarise contribution and contrast.`",
                "",
            ]
            tex += [
                f"%% trace: FR-LIT-3 / {entry['ref']}",
                f"{_tex(claim)} \\citep{{{key}}} "
                "\\todo{summarise contribution and contrast}",
                "",
            ]


def _methods(protocol: dict, md: list, tex: list, findings: list) -> None:
    md += ["## Methodology", ""]
    tex += ["\\section{Methodology}", ""]

    def need(value, field_name: str, req: str) -> object:
        if value in (None, "", [], {}):
            findings.append(
                {
                    "source": "analysis/paper",
                    "kind": "protocol-validation",
                    "requirementId": req,
                    "message": f"methods section cannot be generated: protocol "
                    f"field {field_name!r} is missing or empty",
                    "context": {"field": field_name},
                }
            )
            return None
        return value

    parts = protocol.get("participants", {})
    session = protocol.get("session", {})
    instruments = protocol.get("instruments", {})
    conditions = need(protocol.get("conditions"), "conditions", "FR-PROT-1")
    planned = need(parts.get("planned"), "participants.planned", "FR-PROT-1")
    duration = need(
        session.get("durationMinutes"), "session.durationMinutes", "FR-PROT-1"
    )

    # Participants + design (precompute \todo fallbacks to keep the braces
    # out of the f-string expression parts).
    design = parts.get("design", "within-subjects")
    cb = "counterbalanced" if parts.get("counterbalanced") else "fixed-order"
    cond_str = ", ".join(conditions) if conditions else _TODO["conditions"]
    planned_str = str(planned) if planned else _TODO["n"]
    p_txt = (
        f"We plan {planned_str} participants in a {design}, {cb} "
        f"design across the conditions {cond_str}."
    )
    _para(md, tex, "FR-PROT-1 / participants", p_txt)

    # Session.
    duration_str = str(duration) if duration else _TODO["duration"]
    task = " ".join((session.get("taskDescription") or "").split())
    s_txt = f"Each session lasts {duration_str} minutes. {task}"
    _para(md, tex, "FR-PROT-1 / session", s_txt)

    # Instruments with exact configs.
    md += ["### Instruments", ""]
    tex += ["\\subsection{Instruments}", ""]
    overlay = instruments.get("tern", {})
    fatigue = overlay.get("fatigue", {})
    stuck = overlay.get("stuck", {})
    if fatigue or stuck:
        q = _TODO["q"]
        interval = fatigue.get("intervalMinutes", q)
        pause = fatigue.get("waitForPauseSeconds", q)
        thresh = stuck.get("thresholdSeconds", q)
        i_txt = (
            f"TERN samples fatigue every {interval} minutes "
            f"(after a {pause}-second typing pause) and detects stuck episodes "
            f"after {thresh} seconds of inactivity (FR-INST-1/2)."
        )
        _para(md, tex, "FR-INST-1 / FR-INST-2 / tern", i_txt)
    agent = instruments.get("agentCapture")
    if agent:
        a_txt = (
            f"In the AI condition the agent interaction is captured via "
            f"{agent.get('adapter', 'claude-code')} under a "
            f"{agent.get('contentPolicy', 'metadata-only')} content policy "
            f"(FR-AGENT-2/5)."
        )
        _para(md, tex, "FR-AGENT-2 / FR-AGENT-5 / agentCapture", a_txt)

    # Metrics with definitions + citations.
    metric_set = instruments.get("metrics", {}).get("metricSet")
    defs = METRIC_SETS.get(metric_set or "")
    if defs:
        md += [
            f"### Static code metrics ({metric_set})",
            "",
            "<!-- trace: FR-INST-4 / metrics -->",
            "| Metric | Definition | Source |",
            "| --- | --- | --- |",
        ]
        tex += [
            f"\\subsection{{Static code metrics ({_tex(metric_set)})}}",
            "%% trace: FR-INST-4 / metrics",
            "\\begin{tabular}{lll}",
            "\\toprule",
            "Metric & Definition & Source \\\\",
            "\\midrule",
        ]
        for name, definition, cite in defs:
            md.append(f"| {name} | {definition} | [@{cite}] |")
            tex.append(f"{_tex(name)} & {_tex(definition)} & \\citep{{{cite}}} \\\\")
        md += [""]
        tex += ["\\bottomrule", "\\end{tabular}", ""]

    # Ethics.
    ethics_ref = protocol.get("study", {}).get("ethicsRef") or _TODO["ref"]
    e_txt = (
        f"Ethics reference: {ethics_ref}. Consent is matched to the declared "
        f"content policy (FR-ETH-2/FR-AGENT-5)."
    )
    _para(md, tex, "FR-ETH-1 / FR-ETH-2 / ethics", e_txt)


def _results(
    protocol: dict,
    results: dict[str, RecipeResult],
    figures: dict[str, Figure],
    md: list,
    tex: list,
) -> None:
    md += ["## Results", ""]
    tex += ["\\section{Results}", ""]
    for entry in protocol.get("analysisPlan", []):
        rq = entry["rq"]
        md += [f"### {rq}", ""]
        tex += [f"\\subsection{{{rq}}}", ""]
        for rid in entry.get("recipes", []):
            result = results.get(rid)
            answers = ",".join(REGISTRY[rid].answers) if rid in REGISTRY else "?"
            trace = f"{rq} / {rid} / {answers}"
            if result is None:
                md += [
                    f"<!-- trace: {trace} -->",
                    f"**{rid}.** `TODO: recipe did not run (missing data or error).`",
                    "",
                ]
                tex += [
                    f"%% trace: {trace}",
                    f"\\paragraph{{{_tex(rid)}.}} \\todo{{recipe did not run}}",
                    "",
                ]
                continue
            md += [
                f"<!-- trace: {trace} -->",
                f"**{rid}.** {result.summary}",
                "",
                f"*Methods.* {result.methods}",
                "",
            ]
            tex += [
                f"%% trace: {trace}",
                f"\\paragraph{{{_tex(rid)}.}} {_tex(result.summary)}",
                "",
                f"\\emph{{Methods.}} {_tex(result.methods)}",
                "",
            ]
            _tables(rid, result, md, tex)
            for fname in sorted(figures):
                if fname.startswith(f"{rid}_"):
                    md += [f"![{rid}](figures/{fname}.png)", ""]
                    tex += [
                        "\\begin{figure}[h]",
                        "\\centering",
                        f"\\includegraphics[width=0.8\\linewidth]{{figures/{fname}.pdf}}",
                        f"\\caption{{{_tex(rid)}}}",
                        "\\end{figure}",
                        "",
                    ]


def _tables(rid: str, result: RecipeResult, md: list, tex: list) -> None:
    """Render each result table as Markdown + a booktabs tabular. Tables are
    small (per-condition summaries, test rows); floats fixed to 3 dp for a
    reproducible draft."""
    for name, df in result.tables.items():
        if df.empty:
            continue
        show = df.head(12).copy()
        for col in show.columns:
            if pd.api.types.is_float_dtype(show[col]):
                show[col] = show[col].map(lambda v: "" if pd.isna(v) else f"{v:.3f}")
        cols = list(show.columns)
        md += [
            f"*Table: {name}*",
            "",
            "| " + " | ".join(map(str, cols)) + " |",
            "| " + " | ".join(["---"] * len(cols)) + " |",
        ]
        for _, row in show.iterrows():
            md.append("| " + " | ".join(_md(str(row[c])) for c in cols) + " |")
        md += [""]
        tex += [
            f"\\begin{{table}}[h]\\centering\\caption{{{_tex(name)}}}",
            "\\begin{tabular}{" + "l" * len(cols) + "}",
            "\\toprule",
            " & ".join(_tex(str(c)) for c in cols) + " \\\\",
            "\\midrule",
        ]
        for _, row in show.iterrows():
            tex.append(" & ".join(_tex(str(row[c])) for c in cols) + " \\\\")
        tex += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]


def _threats(md: list, tex: list, threats_record: dict | None = None) -> None:
    # Known framework limitations (adaptation-notes.md; scope discipline in
    # docs/VISION.md), pre-filled for the researcher to extend.
    items = [
        (
            "Origin-classification blind spots",
            "edit-provenance is a debounced "
            "heuristic (typed vs AI-injected vs pasted); rapid interleaving can "
            "misattribute a burst - the agent-leg correlation strengthens but "
            "does not eliminate this (FR-INST-10, FR-AGENT-3).",
        ),
        (
            "Small-n framing",
            "pilot samples are hypothesis-generating; exact "
            "nonparametric tests and effect sizes are reported with per-cell n, "
            "and no claim rests on a bare p-value (NFR-8).",
        ),
        (
            "Single-IDE, single-agent scope",
            "capture is VS Code + Claude Code; "
            "generality to other editors/agents is by design, not demonstration "
            "(scope discipline; FR-AGENT-4 extension point).",
        ),
        (
            "Self-report instruments",
            "fatigue and stuck probes are Likert "
            "self-reports subject to the usual response biases.",
        ),
    ]
    md += ["## Threats to validity", ""]
    tex += ["\\section{Threats to validity}", ""]
    for head, body in items:
        _para(
            md, tex, "threats / scope-discipline", f"**{head}.** {body}", bold_head=head
        )
    if threats_record:
        _curated_threats(md, tex, threats_record)


def _curated_threats(md: list, tex: list, record: dict) -> None:
    """Inject a curated dataset's validity-threats record verbatim (FR-CUR-3
    F3.1): the data's provenance travels into the paper's threats section."""
    frame = record.get("samplingFrame", {})
    window = frame.get("window", {})
    md += ["", "### Data provenance (curated dataset)", ""]
    tex += ["\\subsection{Data provenance (curated dataset)}", ""]
    _para(
        md,
        tex,
        "threats / provenance (FR-CUR-3)",
        f"**Sampling frame.** Mined under the query `{frame.get('query', '')}` "
        f"over {window.get('start', '?')}–{window.get('end', '?')}; actor unit "
        f"= {frame.get('actorUnit', 'developer')}; content policy = "
        f"{frame.get('contentPolicy', 'metadata-only')}.",
        bold_head="Sampling frame",
    )
    for h in record.get("heuristics", []):
        modes = "; ".join(h.get("knownFailureModes", []))
        _para(
            md,
            tex,
            "threats / heuristic (FR-CUR-3)",
            f"**Authorship heuristic `{h.get('id')}` (v{h.get('version')}).** "
            f"Cited to {h.get('cite')}. Known failure modes: {modes}.",
            bold_head=f"Heuristic {h.get('id')}",
        )
    for b in record.get("biases", []):
        disp = b.get("mitigation") or (f"accepted: {b.get('accepted')}")
        _para(
            md,
            tex,
            "threats / declared-bias (FR-CUR-3)",
            f"**Declared bias.** {b.get('description')} "
            f"(direction: {b.get('direction')}; {disp}).",
            bold_head="Declared bias",
        )
    cov = record.get("coverage", {})
    dropped = ", ".join(f"{k}: {v}" for k, v in (cov.get("dropped") or {}).items())
    _para(
        md,
        tex,
        "threats / coverage (FR-CUR-3)",
        f"**Coverage.** Requested {cov.get('requested', 0)}, retrieved "
        f"{cov.get('retrieved', 0)}" + (f"; dropped — {dropped}." if dropped else "."),
        bold_head="Coverage",
    )


# ---------------------------------------------------------------- helpers


def _para(
    md: list, tex: list, trace: str, text: str, *, bold_head: str | None = None
) -> None:
    md += [f"<!-- trace: {trace} -->", _md_todo(text), ""]
    tex += [f"%% trace: {trace}", _tex_keep_todo(text), ""]


def _literature(protocol: dict, papers: list[dict] | None) -> list[dict]:
    """Normalise literature links to ``{ref, citeKey, label, justifies}``.
    Prefers ingested-paper metadata (richer label + bib); falls back to the
    protocol's ``literature:`` list (deterministic, offline)."""
    by_ref: dict[str, dict] = {}
    for entry in protocol.get("literature", []):
        ref = entry.get("paperRef", "")
        by_ref[ref] = {
            "ref": ref,
            "citeKey": _cite_key(ref),
            "label": ref,
            "justifies": list(entry.get("justifies", [])),
            "meta": None,
        }
    for p in papers or []:
        ref = p.get("paperRef", "")
        rec = by_ref.setdefault(
            ref,
            {
                "ref": ref,
                "citeKey": _cite_key(ref),
                "label": ref,
                "justifies": list(p.get("links", [])),
                "meta": None,
            },
        )
        if p.get("title"):
            first_author = (p.get("authors") or ["?"])[0].split()[-1]
            year = p.get("year") or ""
            rec["label"] = f"{first_author} ({year})" if year else p["title"]
        rec["meta"] = p
        if p.get("links"):
            rec["justifies"] = sorted(set(rec["justifies"]) | set(p["links"]))
    return [by_ref[k] for k in sorted(by_ref)]


def _bib(lit: list[dict]) -> str:
    """A minimal ``references.bib``. Ingested papers get real fields; a
    protocol-only ref gets a ``@misc`` stub keyed by its paperRef."""
    # Metric-definition citation stubs so \citep resolves and pdflatex is clean.
    stub_keys = {c for defs in METRIC_SETS.values() for _, _, c in defs}
    entries = [
        f"@misc{{{key},\n  title = {{{{{key}}}}},\n  note = {{metric-set citation "
        f"stub, fill in}}\n}}"
        for key in sorted(stub_keys)
    ]
    for entry in lit:
        meta = entry["meta"]
        key = entry["citeKey"]
        if meta and meta.get("title"):
            authors = " and ".join(meta.get("authors", []) or ["Unknown"])
            year = meta.get("year") or "n.d."
            entries.append(
                f"@article{{{key},\n  title = {{{{{_bibval(meta['title'])}}}}},\n"
                f"  author = {{{_bibval(authors)}}},\n  year = {{{year}}},\n"
                f"  note = {{{entry['ref']}}}\n}}"
            )
        else:
            entries.append(
                f"@misc{{{key},\n  title = {{{{{entry['ref']}}}}},\n"
                f"  note = {{linked in the protocol; enrich via the "
                f"knowledge layer}}\n}}"
            )
    return "\n\n".join(entries) + "\n"


def _tex_preamble(protocol: dict) -> list[str]:
    return [
        "%% Generated by `analysis paper` (FR-ANA-6) - deterministic, no LLM.",
        "%% Regenerating from the same protocol + dataset yields an identical file.",
        "\\documentclass[11pt]{article}",
        "\\usepackage[utf8]{inputenc}",
        "\\usepackage{natbib}",
        "\\usepackage{booktabs}",
        "\\usepackage{graphicx}",
        "\\usepackage{xcolor}",
        "\\newcommand{\\todo}[1]{\\textcolor{red}{[TODO: #1]}}",
        "",
    ]


_CITE_BAD = re.compile(r"[^A-Za-z0-9]+")


def _cite_key(ref: str) -> str:
    return _CITE_BAD.sub("_", ref).strip("_").lower() or "ref"


def _participant_count(dataset: Dataset) -> int:
    ids = {r.get("participantId") for r in dataset.rows if r.get("participantId")}
    return len(ids)


_TEX_ESCAPES = {
    "&": "\\&",
    "%": "\\%",
    "$": "\\$",
    "#": "\\#",
    "_": "\\_",
    "{": "\\{",
    "}": "\\}",
    "~": "\\textasciitilde{}",
    "^": "\\textasciicircum{}",
}
#: Common non-ASCII glyphs recipe summaries emit -> pdflatex-safe LaTeX, so a
#: draft compiles without extra packages regardless of the study's text.
_TEX_UNICODE = {
    "—": "---",
    "–": "--",
    "→": "$\\rightarrow$",
    "≥": "$\\geq$",
    "≤": "$\\leq$",
    "±": "$\\pm$",
    "×": "$\\times$",
    "²": "$^2$",
    "·": "$\\cdot$",
    "…": "...",
    "’": "'",
    "‘": "'",
    "“": "``",
    "”": "''",
    "α": "$\\alpha$",
    "β": "$\\beta$",
    "Δ": "$\\Delta$",
    "≈": "$\\approx$",
    " ": " ",
}
_TODO_RE = re.compile(r"\\todo\{([^}]*)\}")


def _tex(text: str) -> str:
    """Escape body text for LaTeX so a draft compiles with pdflatex.

    Order matters: stash literal backslashes, escape the reserved ASCII
    characters (``{``/``}`` before ``~``/``^`` so their introduced braces
    aren't double-escaped), restore backslashes as ``\\textbackslash{}``,
    THEN transliterate unicode glyphs into intentional LaTeX (which must not
    be re-escaped), and finally drop any remaining non-ASCII."""
    text = text.replace("\\", "\x00")
    for ch, rep in _TEX_ESCAPES.items():
        text = text.replace(ch, rep)
    text = text.replace("\x00", "\\textbackslash{}")
    for ch, rep in _TEX_UNICODE.items():
        text = text.replace(ch, rep)
    return "".join(c for c in text if ord(c) < 128)


def _tex_keep_todo(text: str) -> str:
    """Escape body text but preserve ``\\todo{...}`` commands (their argument
    is escaped, the command is not)."""
    parts = []
    last = 0
    for m in _TODO_RE.finditer(text):
        parts.append(_tex(text[last : m.start()]))
        parts.append("\\todo{" + _tex(m.group(1)) + "}")
        last = m.end()
    parts.append(_tex(text[last:]))
    return "".join(parts)


def _md_todo(text: str) -> str:
    return _TODO_RE.sub(lambda m: f"`TODO: {m.group(1)}`", text)


def _md(text: str) -> str:
    return text.replace("|", "\\|")


def _bibval(text: str) -> str:
    return text.replace("{", "").replace("}", "")
