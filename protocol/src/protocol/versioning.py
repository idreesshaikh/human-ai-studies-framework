"""Content-addressed protocol, task, instrument and re-run provenance."""

import hashlib
import json


def content_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode()
    ).hexdigest()


def version_record(value: dict) -> dict:
    return {
        "id": value.get("id"),
        "version": value.get("version", "unversioned"),
        "sha256": content_hash({k: v for k, v in value.items() if k != "contentHash"}),
    }


def provenance(protocol: dict) -> dict:
    return {
        "protocolId": (protocol.get("study") or {}).get("id"),
        "protocolVersion": protocol.get("protocolVersion"),
        "protocolHash": content_hash(protocol),
        "tasks": [version_record(t) for t in protocol.get("tasks", [])],
        "measureSet": {
            "version": protocol.get("measureSetVersion", "unversioned"),
            "sha256": content_hash(protocol.get("measures", [])),
        },
        "instruments": [
            version_record(i)
            for i in protocol.get("instruments", {}).get("surveys", [])
        ],
        "toolVersions": protocol.get("toolVersions", {}),
        "rerunOf": protocol.get("rerunOf"),
    }


def compare_designs(original: dict, rerun: dict) -> dict:
    fields = (
        "participants",
        "conditions",
        "tasks",
        "measures",
        "measureSetVersion",
        "instruments",
        "analysisPlan",
        "toolVersions",
        "covariate",
    )
    return {
        "original": provenance(original),
        "rerun": provenance(rerun),
        "fields": [
            {
                "field": k,
                "original": original.get(k),
                "rerun": rerun.get(k),
                "changed": original.get(k) != rerun.get(k),
            }
            for k in fields
        ],
        "pooled": False,
    }
