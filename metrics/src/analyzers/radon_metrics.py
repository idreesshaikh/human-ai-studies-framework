"""Radon-based metrics: Halstead mental effort and comment-to-code ratio.

Part of the 9-metric cognitive-load matrix (metrics/docs/static_code_metrics.md):
Halstead effort approximates the mental effort to (re)derive the code from its
operator/operand vocabulary ("Working Memory & Volume"); the comment ratio is
the documentation-vs-logic balance ("Visual & Semantic Friction").

Adopted per decision D6 (requirements/build-vs-adopt.md): parsers/analyzers
are adopted, the metric selection is ours.
"""

from radon.metrics import h_visit
from radon.raw import analyze


def get_halstead_effort(source: str) -> dict:
    """File-total and per-function Halstead effort.

    Returns {"total": float, "functions": {name: effort}}. Duplicate function
    names (e.g. same-named methods in two classes) keep the first occurrence -
    a known limitation shared with the tree-sitter name join in main.py.
    Syntactically invalid source returns zero/empty rather than raising.
    """
    try:
        report = h_visit(source)
    except SyntaxError:
        return {"total": 0.0, "functions": {}}
    functions: dict[str, float] = {}
    for name, func_report in report.functions:
        functions.setdefault(name, round(func_report.effort, 2))
    return {"total": round(report.total.effort, 2), "functions": functions}


def get_comment_ratio(source: str) -> float:
    """(comment lines + multi-line-string doc lines) / source lines of code,
    rounded to 2 decimals; 0.0 when there is no code to comment."""
    try:
        raw = analyze(source)
    except SyntaxError:
        return 0.0
    if raw.sloc == 0:
        return 0.0
    return round((raw.comments + raw.multi) / raw.sloc, 2)
