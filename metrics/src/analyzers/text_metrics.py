"""Plain-text metrics (file-level): visual layout signals that need no parser."""

from statistics import pstdev

TAB_WIDTH = 4


def _leading_whitespace(line: str) -> int:
    """Leading whitespace width with tabs expanded to TAB_WIDTH spaces."""
    expanded = line.expandtabs(TAB_WIDTH)
    return len(expanded) - len(expanded.lstrip(" "))


def get_indentation_variance(source: str) -> float:
    """
    Population standard deviation of leading-whitespace width over all non-blank lines,
    rounded to 2 decimals.
    """
    widths = [_leading_whitespace(line) for line in source.splitlines() if line.strip()]
    if len(widths) < 2:
        return 0.0
    return round(pstdev(widths), 2)


def get_line_width_bounds(source: str) -> dict:
    """
    Max and mean character width per line (tabs expanded); blank lines are excluded from
    the mean.
    """
    lines = [line.expandtabs(TAB_WIDTH) for line in source.splitlines()]
    non_blank = [len(line) for line in lines if line.strip()]
    if not non_blank:
        return {"max_line_width": 0, "mean_line_width": 0.0}
    return {
        "max_line_width": max(len(line) for line in lines),
        "mean_line_width": round(sum(non_blank) / len(non_blank), 2),
    }
