"""Descriptive indicators from screened, sourced full-text extraction rows."""

from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path

from analysis.power import minimum_detectable_d
from scipy.stats import binomtest

NUMERIC = ("n_total_analysed", "n_per_arm_analysed")
PROPORTIONS = (
    "a_priori_power_analysis",
    "effect_size_reported",
    "ci_reported",
    "preregistered",
    "tool_and_version_reported",
)


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as file:
        return list(csv.DictReader(file))


def _integer(row: dict, field: str) -> int | None:
    raw = row.get(field, "").strip()
    if not raw:
        return None
    value = int(raw)
    if value < 1:
        raise ValueError(f"{row['id']}: {field} must be positive or blank")
    return value


def _numeric(values: list[int], count: int) -> dict:
    quartiles = (
        statistics.quantiles(values, method="inclusive")
        if len(values) > 1
        else values * 3
    )
    return {
        "n": len(values),
        "missing": count - len(values),
        "median": statistics.median(values) if values else None,
        "q1": quartiles[0] if quartiles else None,
        "q3": quartiles[2] if quartiles else None,
    }


def _proportion(rows: list[dict], field: str) -> dict:
    allowed = (
        {"yes", "no", "partial"}
        if field == "tool_and_version_reported"
        else {"yes", "no"}
    )
    known = [row[field] for row in rows if row.get(field) in allowed]
    successes = known.count("yes")
    interval = (
        binomtest(successes, len(known)).proportion_ci(method="exact")
        if known
        else None
    )
    return {
        "yes": successes,
        "n": len(known),
        "missing": len(rows) - len(known),
        "share": successes / len(known) if known else None,
        "ci": [interval.low, interval.high] if interval else None,
    }


def summarise(extraction: Path, screening: Path) -> dict:
    """Keep screening decisions and abstract-only records out of the denominators."""
    included = {row["id"] for row in _read(screening) if row["decision"] == "include"}
    selected = [row for row in _read(extraction) if row["id"] in included]
    rows = []
    abstract_only = 0
    for row in selected:
        if row.get("abstract_only", "").lower() not in {"true", "false"}:
            raise ValueError(f"{row['id']}: abstract_only must be true or false")
        if row["abstract_only"].lower() == "true":
            abstract_only += 1
            continue
        if not row.get("coder") or not row.get("page_or_table_reference"):
            raise ValueError(
                f"{row['id']}: full-text extraction needs a coder and page/table"
            )
        rows.append(row)
    numeric = {}
    for field in NUMERIC:
        values = [_integer(row, field) for row in rows]
        numeric[field] = _numeric(
            [value for value in values if value is not None], len(rows)
        )
    proportions = {field: _proportion(rows, field) for field in PROPORTIONS}
    eligible = []
    eligibility_unknown = 0
    for row in rows:
        comparisons = _integer(row, "n_primary_comparisons")
        if comparisons is None:
            eligibility_unknown += 1
        elif comparisons > 1:
            eligible.append(row)
    correction = _proportion(eligible, "multiple_comparison_correction")
    correction["eligibility_unknown"] = eligibility_unknown
    proportions["multiple_comparison_correction"] = correction
    thresholds = []
    skipped_design = missing_n = unreachable = 0
    for row in rows:
        design = row.get("design")
        if design not in {"between", "within"}:
            skipped_design += 1
            continue
        field = "n_per_arm_analysed" if design == "between" else "n_total_analysed"
        n = _integer(row, field)
        if n is None:
            missing_n += 1
            continue
        threshold = minimum_detectable_d(n, design)
        if threshold is None:
            unreachable += 1
        else:
            thresholds.append(threshold)
    return {
        "studies": len(rows),
        "included": len(included),
        "not_extracted": len(included - {row["id"] for row in selected}),
        "abstract_only": abstract_only,
        "numeric": numeric,
        "proportions": proportions,
        "sensitivity": {
            "n": len(thresholds),
            "skipped_design": skipped_design,
            "missing_n": missing_n,
            "unreachable": unreachable,
            "median": statistics.median(thresholds) if thresholds else None,
            "range": [min(thresholds), max(thresholds)] if thresholds else None,
        },
    }


def markdown(result: dict) -> str:
    text = [
        "# Power re-measurement indicators",
        "",
        f"Included studies: {result['included']}; "
        f"full-text extractions: {result['studies']}; "
        f"abstract-only: {result['abstract_only']}; "
        f"awaiting extraction: {result['not_extracted']}.",
        "",
        "Unknown values are excluded from each denominator and counted as missing.",
        "",
        "| Sample size | Known | Missing | Median | Q1–Q3 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for field, values in result["numeric"].items():
        median = values["median"] if values["median"] is not None else "pending"
        iqr = f"{values['q1']}–{values['q3']}" if values["n"] else "pending"
        text.append(
            f"| {field} | {values['n']} | {values['missing']} | {median} | {iqr} |"
        )
    text += [
        "",
        "| Indicator | Yes / known | Missing | Share | Exact 95% interval |",
        "| --- | --- | --- | --- | --- |",
    ]
    for field, values in result["proportions"].items():
        share = f"{values['share']:.1%}" if values["share"] is not None else "pending"
        interval = (
            f"[{values['ci'][0]:.3f}, {values['ci'][1]:.3f}]"
            if values["ci"]
            else "pending"
        )
        text.append(
            f"| {field} | {values['yes']} / {values['n']} | {values['missing']} "
            f"| {share} | {interval} |"
        )
    sensitivity = result["sensitivity"]
    unknown = result["proportions"]["multiple_comparison_correction"][
        "eligibility_unknown"
    ]
    text += [
        "",
        "Correction eligibility requires explicitly reported multiple primary "
        f"comparisons; eligibility is unknown for {unknown} studies.",
        "",
        "Sensitivity uses two-sided t-tests at alpha 0.05 and 80% power, equal "
        "arms for between designs and the standardized within-person difference "
        "for paired designs. It never uses observed effects.",
        "",
        f"Sensitivity estimates: {sensitivity['n']}; "
        f"median d: {sensitivity['median']}; "
        f"range: {sensitivity['range']}; "
        f"unsupported designs: {sensitivity['skipped_design']}; "
        f"missing n: {sensitivity['missing_n']}; "
        f"unreachable through d=5: {sensitivity['unreachable']}.",
    ]
    if not result["studies"]:
        text += [
            "",
            "Extraction is pending. These tables contain no empirical conclusions.",
        ]
    return "\n".join(text) + "\n"


def main() -> None:
    base = Path(__file__).parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extraction", type=Path, default=base / "extraction.csv")
    parser.add_argument("--screening", type=Path, default=base / "screening.csv")
    parser.add_argument("--output", type=Path, default=base / "indicators.md")
    args = parser.parse_args()
    output = markdown(summarise(args.extraction, args.screening))
    args.output.write_text(output)
    print(output, end="")


if __name__ == "__main__":
    main()
