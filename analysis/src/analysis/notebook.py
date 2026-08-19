"""Starter-notebook generation: the curated handoff (analysis `notebook`).

The platform's scope ends where the researcher's analysis begins. What a
researcher needs at that boundary is not a raw dataset but a *loaded,
documented dataframe*: every column named, every recipe importable, every
prescribed test stated — with nothing run. That is what this module emits:

``analysis notebook <protocol.yaml>`` writes two artifacts under
``results/<study>/``:

- ``notebook.ipynb`` — a Jupyter notebook with the data dictionary as
  markdown, the dataset loaded in one cell, one section per research
  question, and each planned recipe imported (never executed) with its
  prescription row stated. The researcher's own analysis starts at the
  final cell.
- ``data-dictionary.md`` — the same dictionary standalone, for the data-
  availability statement.

Deterministic like every other protocol-derived artifact here: the same
protocol plus dataset always produce the same notebook, byte for byte, no
model in the loop. The dictionary documents only columns that actually
exist in the dataset, and payload keys only for event types that actually
appear — an honest dictionary, not a schema's wish list.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import analysis.recipes  # noqa: F401 - registers the built-in recipes
from analysis.core import REGISTRY
from analysis.dataset import Dataset
from analysis.prescribe import design_shapes, prescribe, shape_to_recipe_id

#: Human names for the columns the platform itself stamps. Anything not
#: listed is a payload key and is documented as "payload key on <type> events"
#: (or a metric column, where the numeric value is its own meaning).
_COLUMN_MEANINGS: dict[str, str] = {
    "sessionId": "the session this row belongs to; joins the timeline",
    "participantId": "anonymized participant id (P01, P02, ...)",
    "condition": "the condition this session ran under",
    "ts": "UTC timestamp (ISO-8601, millisecond precision)",
    "type": "event type — what the row records",
    "seq": "per-session sequence number on the producer's stream",
    "source": "producer stream (tern, agent-capture, task-harness, metrics, ...)",
    "flags": "integrity flags the middleware stamped on ingest (empty = clean)",
    "score": "fatigue response on a 1-5 Likert scale",
    "latencyMs": "response latency in milliseconds",
    "evidenceMs": "stuck detector's accumulated evidence before the probe (ms)",
    "charCount": "paste size in characters (content is never recorded)",
    "passed": "task-harness verdict: did the acceptance suite pass",
    "firstGreenMs": "milliseconds from session start to the first passing run",
    "responseChars": "agent response size in characters (metadata-only policy)",
    "action": "ai_suggestion lifecycle: shown, accepted, or dismissed",
    "visibleMs": "milliseconds a suggestion was visible before the choice",
    "suggestionId": "suggestion identifier within the session",
    "file": "path of the focused file (line numbers only, never text)",
    "role": "agent conversation role (user/assistant)",
    "turnIndex": "agent conversation turn position in the session",
    "level": "metric level: function_metrics or file_metrics",
    "mentalDemand": "NASA-TLX subscale rating",
    "effort": "NASA-TLX subscale rating",
    "frustration": "NASA-TLX subscale rating",
}

#: Design shape -> built-in recipe that runs its prescribed test. The
#: reverse of ``prescribe.shape_to_recipe_id``; built from the public API so
#: the two cannot drift apart.
_SHAPE_BY_RECIPE: dict[str, str] = {
    rid: shape
    for shape in design_shapes()
    if (rid := shape_to_recipe_id(shape)) is not None
}


def _cell_id(cell_type: str, source: str, index: int) -> str:
    """A short, stable cell id.

    nbformat 4.5+ requires one (``nbformat.validate`` still only warns today,
    but names it a coming hard error) - a hand-rolled cell dict that skipped
    it validated against nothing stronger than this module's own shape
    assumptions, which is exactly how the missing ``execution_count`` field
    went unnoticed until a real ``nbformat.validate()`` call caught it.
    Derived from content + position rather than random, so the notebook's
    byte-reproducibility guarantee extends to the ids too - a random uuid
    would make :func:`build_notebook` non-deterministic on its own.
    """
    digest = hashlib.sha256(f"{index}:{cell_type}:{source}".encode()).hexdigest()
    return digest[:8]


def _markdown_cell(source: str, index: int) -> dict:
    return {
        "cell_type": "markdown",
        "id": _cell_id("markdown", source, index),
        "metadata": {},
        "source": source,
    }


def _code_cell(source: str, index: int) -> dict:
    return {
        "cell_type": "code",
        "id": _cell_id("code", source, index),
        "metadata": {},
        # None, not omitted: a code cell that has never run reports no
        # execution count, and nbformat requires the key to be present even
        # when its value is null.
        "execution_count": None,
        "source": source,
        "outputs": [],
    }


def _event_payload_keys(dataset: Dataset) -> dict[str, list[str]]:
    """Per event type, the payload keys actually present in the data."""
    out: dict[str, list[str]] = {}
    for row in dataset.rows:
        if row.get("source") == "metrics":
            continue
        keys = {k for k in (row.get("payload") or {}) if k != "timestamp"}
        if keys:
            out.setdefault(row.get("type", ""), set()).update(keys)
    return {t: sorted(ks) for t, ks in sorted(out.items()) if t}


def _dictionary_rows(dataset: Dataset) -> list[tuple[str, str, str]]:
    """``(column, dtype, meaning)`` rows: stamped columns first, then the
    per-type payload keys, then metric columns."""
    rows: list[tuple[str, str, str]] = []
    events = dataset.events
    fixed = [c for c in events.columns if c != "payload"]
    for column in fixed:
        dtype = str(events[column].dtype) if not events.empty else "object"
        meaning = _COLUMN_MEANINGS.get(column, "event-row attribute stamped at ingest")
        rows.append((column, dtype, meaning))
    for type_, keys in _event_payload_keys(dataset).items():
        for key in keys:
            rows.append((f"payload.{key}", "any", f"payload key on {type_} events"))
    # Sorted, never the set's raw iteration order: metric_columns is a set,
    # and set iteration order is per-process hash-randomized — an unsorted
    # pass would make the dictionary (and with it every cell id, which is
    # content-derived) drift between runs of the same pipeline.
    for column in sorted(dataset.metric_columns):
        rows.append(
            (
                column,
                "numeric",
                _COLUMN_MEANINGS.get(column, "static code metric over the workspace"),
            )
        )
    return rows


def data_dictionary_markdown(dataset: Dataset) -> str:
    """The data dictionary as a Markdown table (standalone artifact)."""
    rows = _dictionary_rows(dataset)
    lines = [
        "## Data dictionary",
        "",
        "Every column in the exported dataset, one row each. A payload key "
        "is documented only if events of that type actually appear in the "
        "data.",
        "",
        "| Column | Type | Meaning |",
        "| --- | --- | --- |",
    ]
    lines += [f"| `{c}` | {d} | {m} |" for c, d, m in rows]
    lines.append("")
    return "\n".join(lines)


def _provenance_markdown(protocol: dict, dataset: Dataset, study_id: str) -> str:
    study = protocol.get("study") or {}
    participants = protocol.get("participants") or {}
    plan = protocol.get("analysisPlan") or []
    recipe_ids = sorted({rid for entry in plan for rid in entry.get("recipes", [])})
    lines = [
        f"# {study.get('title', study_id)} — starter notebook",
        "",
        "Generated by `analysis notebook` — the curated handoff. The dataset "
        "is loaded and every column is documented below; each planned recipe "
        "is imported and its prescribed test stated. **Nothing has been run "
        "yet** — your analysis starts at the last cell.",
        "",
        "## Provenance",
        "",
        f"- Study: `{study_id}`  ",
        f"- Protocol version: {protocol.get('protocolVersion', '?')}  ",
        f"- Conditions: {', '.join(protocol.get('conditions') or [])}  ",
        f"- Participants: {participants.get('planned', '?')} "
        f"({participants.get('design', '?')}, "
        f"{_counterbalancing_text(participants)})  ",
        f"- Dataset rows: {len(dataset.rows)} "
        f"({len(dataset.events)} events, "
        f"{len(dataset.metrics)} metric rows)  ",
        f"- Planned recipes: {', '.join(recipe_ids) or 'none'}",
        "",
    ]
    return "\n".join(lines)


def _counterbalancing_text(participants: dict) -> str:
    if participants.get("counterbalanced"):
        return "counterbalanced"
    return "fixed order"


def _prescription_markdown(recipe_id: str) -> str:
    """The prescription row for a recipe, if its design shape is mapped."""
    shape = _SHAPE_BY_RECIPE.get(recipe_id)
    if shape is None:
        return ""
    row = prescribe(shape)
    if row is None:
        return ""
    return (
        f"Prescribed analysis for the **{shape}** shape: **{row.test}** "
        f"(effect size: {row.effect_size}; correction: {row.correction}; "
        f"sample guidance: {row.sample_size_guidance})."
    )


def _recipe_cells(dataset: Dataset, entry: dict, cells: list[dict]) -> None:
    """Append this entry's per-recipe markdown + import cells onto ``cells``.

    Appends in place (rather than returning a fresh list) so each cell's id
    is derived from its real position in the whole notebook, not a position
    local to this one research question - two different RQs whose recipe
    lists happen to match character-for-character must still get distinct
    cells, and they do, because they land at different indices.
    """
    for rid in entry.get("recipes", []):
        rec = REGISTRY.get(rid)
        module = rid.replace("-", "_")
        importable = module
        extra = ""
        if rec is None:
            importable = ""
            extra = " **not registered** — check `analysis list`."
        else:
            missing = rec.requires.missing(dataset)
            if missing:
                extra = (
                    " **Missing from this dataset:** "
                    + ", ".join(missing)
                    + " — the recipe will not run until these arrive."
                )
            else:
                extra = " (requirements satisfied by this dataset)"
        text = f"### `{rid}`{extra}"
        if rec is not None:
            text += f"\n\n{rec.title}."
            pres = _prescription_markdown(rid)
            if pres:
                text += f"\n\n{pres}"
        cells.append(_markdown_cell(text + "\n", len(cells)))
        if importable:
            source = (
                f"from analysis.recipes import {module}\n"
                f"\n"
                f"result = {module}.run(dataset)\n"
                f"result.summary\n"
            )
        else:
            source = f"# {rid} is not registered; see `analysis list`.\n"
        cells.append(_code_cell(source, len(cells)))


def build_notebook(protocol: dict, dataset: Dataset, study_id: str) -> dict:
    """The starter notebook as an ``.ipynb`` document (JSON, nbformat 4)."""
    plan = protocol.get("analysisPlan") or []
    rq_text = {
        rq.get("id"): rq.get("text", "")
        for rq in protocol.get("researchQuestions") or []
    }

    cells: list[dict] = []
    cells.append(
        _markdown_cell(_provenance_markdown(protocol, dataset, study_id), len(cells))
    )
    cells.append(_markdown_cell(data_dictionary_markdown(dataset), len(cells)))
    cells.append(
        _code_cell(
            "from analysis.dataset import Dataset\n"
            "\n"
            "# Point this at your dataset export, or start the middleware\n"
            '# and use Dataset.fetch("http://127.0.0.1:8000", "' + study_id + '").\n'
            'dataset = Dataset.from_json("dataset.json")\n',
            len(cells),
        )
    )
    # The one-glance session picture (P2-1): what a session recorded, as a
    # printable figure — before any recipe, so the researcher sees the shape
    # of the data (and any integrity flags) first.
    cells.append(
        _markdown_cell(
            "## Session timeline\n"
            "\n"
            "One glance at what a session records: every event on a shared "
            "timeline, a lane per event type, minutes from the session's "
            "first event. Open diamonds mark rows the middleware flagged at "
            "ingest (integrity marks).\n",
            len(cells),
        )
    )
    cells.append(
        _code_cell(
            "from analysis import figures\n"
            "\n"
            "# The first session in the dataset; loop over rows for all of them:\n"
            "# for session_id in sorted({r['sessionId'] for r in dataset.rows}):\n"
            'session_id = dataset.rows[0]["sessionId"]\n'
            "fig = figures.session_timeline(dataset, session_id)\n"
            'fig.savefig(f"session-timeline-{session_id}.png", dpi=150)\n',
            len(cells),
        )
    )
    for entry in plan:
        rq = entry.get("rq", "")
        cells.append(_markdown_cell(f"## {rq} — {rq_text.get(rq, '')}\n", len(cells)))
        _recipe_cells(dataset, entry, cells)
    cells.append(_markdown_cell("## Your analysis starts here\n", len(cells)))
    cells.append(_code_cell("# Your analysis starts here.\n", len(cells)))
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.12"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def write_notebook(
    protocol: dict, dataset: Dataset, study_id: str, out_dir: Path
) -> tuple[Path, Path]:
    """Write ``notebook.ipynb`` and ``data-dictionary.md``; returns both paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    nb_path = out_dir / "notebook.ipynb"
    nb_path.write_text(
        json.dumps(build_notebook(protocol, dataset, study_id), indent=1) + "\n"
    )
    dd_path = out_dir / "data-dictionary.md"
    dd_path.write_text(
        "# " + study_id + " — data dictionary\n\n" + data_dictionary_markdown(dataset)
    )
    return nb_path, dd_path
