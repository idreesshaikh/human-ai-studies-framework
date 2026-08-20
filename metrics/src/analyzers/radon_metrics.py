"""Radon-based metrics: Halstead mental effort and comment-to-code ratio."""

from radon.metrics import h_visit
from radon.raw import analyze


def get_halstead_effort(source: str) -> dict:
    """File-total and per-function Halstead effort."""
    try:
        report = h_visit(source)
    except SyntaxError:
        return {"total": 0.0, "functions": {}}
    functions: dict[str, float] = {}
    for name, func_report in report.functions:
        functions.setdefault(name, round(func_report.effort, 2))
    return {"total": round(report.total.effort, 2), "functions": functions}


def get_comment_ratio(source: str) -> float:
    """
    (comment lines + multi-line-string doc lines) / source lines of code, rounded to 2
    decimals; 0.0 when there is no code to comment.
    """
    try:
        raw = analyze(source)
    except SyntaxError:
        return 0.0
    if raw.sloc == 0:
        return 0.0
    return round((raw.comments + raw.multi) / raw.sloc, 2)
