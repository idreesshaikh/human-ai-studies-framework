"""
The post-run data bundle: a study's collected data as plain, tidy files a
researcher can open in a spreadsheet or pandas without the platform.

Pure functions over already study-scoped rows (see ``app._joined_rows``), so the
route owns scoping and auth and this module owns only the shape of the zip.
The zip is deterministic: fixed member timestamps and permissions, sorted
members, so two exports of the same data are byte-identical.
"""

import csv
import hashlib
import io
import json
import re
import zipfile

import yaml
from protocol.design_card import design_card, design_card_markdown

FORMAT_VERSION = 1

JOIN_COLUMNS = [
    "participantId",
    "condition",
    "sessionId",
    "taskId",
    "ts",
    "schemaVersion",
    "source",
    "seq",
    "flags",
    "pilot",
    "inclusionDecision",
]
_EPOCH = (1980, 1, 1, 0, 0, 0)

README = """# Data bundle

Everything here is plain text (UTF-8) a spreadsheet, pandas or R can open.

## Files

- `events/<type>.csv`: one table per event type (RFC 4180 CSV, `\\n` line
  endings, header row first). Join keys come first (participantId, condition,
  sessionId, taskId, ts, schemaVersion, source, seq, flags); payload fields
  follow, nested objects flattened to `a.b` columns, lists and flags as JSON
  text. An empty cell means the value was absent or null.
- `events/all.json`: the full joined timeline, every leg on one clock.
- `protocol.yaml`: the resolved study protocol these data were collected under.
- `data-dictionary.md`: what each table and column holds.
- `files/`: artifacts uploaded for this study, if any.
- `design-card.json` and `design-card.md`: recorded power assumptions, typed
  measures, survey wording/versions, session tool versions, audit results and
  inclusion decisions. No validity score.
- `manifest.json`: provenance and integrity, described below.

## Conventions

- Timestamps (`ts`) are ISO 8601 in UTC.
- `schemaVersion` is the event schema each row was written under.
- Dry-run (synthetic) rows are excluded unless the export asked for them;
  `manifest.json` records which.

## manifest.json

- `formatVersion`: version of this bundle layout.
- `studyId`, `protocol`: the study and the protocol's id, version, title and
  sha256 (of its canonical JSON).
- `includesSynthetic`, `encoding`, `timestampFormat`.
- `schemaVersions`: event schema versions present in the data.
- `participants`: each participant's assigned condition(s).
- `rows`, `tables`: total and per-table row counts.
- `members`: sha256 of every other file in the bundle.

The bundle is deterministic: re-exporting unchanged data gives identical bytes,
so it carries no export timestamp.
"""


def is_synthetic(row: dict) -> bool:
    return bool((row.get("payload") or {}).get("synthetic"))


def flatten(value: object, prefix: str = "") -> dict[str, object]:
    """Flatten nested dicts to dotted keys; lists and scalars stay as values."""
    if not isinstance(value, dict):
        return {prefix or "value": value}
    out: dict[str, object] = {}
    for key, inner in value.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(inner, dict) and inner:
            out.update(flatten(inner, path))
        else:
            out[path] = inner
    return out


def _cell(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return value


def _table_csv(rows: list[dict]) -> str:
    flat = [flatten(r["payload"] or {}) for r in rows]
    payload_cols = sorted({k for f in flat for k in f} - set(JOIN_COLUMNS))
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(JOIN_COLUMNS + payload_cols)
    for r, f in zip(rows, flat, strict=True):
        writer.writerow(
            [_cell(r.get(c)) for c in JOIN_COLUMNS]
            + [_cell(f.get(c)) for c in payload_cols]
        )
    return buf.getvalue()


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "unnamed"


def _protocol_meta(protocol: dict | None) -> dict | None:
    if protocol is None:
        return None
    study = protocol.get("study") or {}
    canonical = json.dumps(protocol, sort_keys=True, default=str)
    return {
        "id": study.get("id"),
        "title": study.get("title"),
        "version": protocol.get("protocolVersion"),
        "sha256": hashlib.sha256(canonical.encode()).hexdigest(),
    }


def _assignments(rows: list[dict]) -> dict[str, list[str]]:
    seen: dict[str, set[str]] = {}
    for r in rows:
        if r.get("participantId") and r.get("condition"):
            seen.setdefault(r["participantId"], set()).add(r["condition"])
    return {p: sorted(c) for p, c in sorted(seen.items())}


def build_bundle(
    study_id: str,
    rows: list[dict],
    dictionary_md: str,
    files: list[tuple[str, bytes]],
    *,
    protocol: dict | None = None,
    include_synthetic: bool = False,
    design_card_record: dict | None = None,
) -> bytes:
    """Zip the tidy tables, timeline, protocol, dictionary and uploaded files."""
    by_type: dict[str, list[dict]] = {}
    for r in rows:
        by_type.setdefault(r["type"], []).append(r)

    members: dict[str, bytes] = {
        "README.md": README.encode(),
        "data-dictionary.md": dictionary_md.encode(),
        "events/all.json": json.dumps(
            {"studyId": study_id, "rows": rows}, indent=1, sort_keys=True
        ).encode(),
    }
    if protocol is not None:
        members["protocol.yaml"] = yaml.safe_dump(
            protocol, sort_keys=False, default_flow_style=False
        ).encode()
    card = design_card_record or (
        design_card(protocol, rows=rows) if protocol else None
    )
    if card:
        members["design-card.json"] = json.dumps(
            card, indent=2, sort_keys=True
        ).encode()
        members["design-card.md"] = design_card_markdown(card).encode()
    used: set[str] = set()
    for type_, group in sorted(by_type.items()):
        stem = _safe(type_)
        while stem in used:  # two types that sanitise alike must not overwrite
            stem += "_"
        used.add(stem)
        members[f"events/{stem}.csv"] = _table_csv(group).encode()
    for name, data in files:
        members[f"files/{_safe(name)}"] = data

    manifest = {
        "formatVersion": FORMAT_VERSION,
        "studyId": study_id,
        "protocol": _protocol_meta(protocol),
        "includesSynthetic": include_synthetic,
        "encoding": "utf-8",
        "timestampFormat": "ISO 8601, UTC",
        "schemaVersions": sorted(
            {r["schemaVersion"] for r in rows if r.get("schemaVersion") is not None}
        ),
        "participants": _assignments(rows),
        "rows": len(rows),
        "tables": {t: len(g) for t, g in sorted(by_type.items())},
        "members": {
            name: hashlib.sha256(data).hexdigest()
            for name, data in sorted(members.items())
        },
    }
    members["manifest.json"] = json.dumps(manifest, indent=1, sort_keys=True).encode()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)
    return buf.getvalue()
