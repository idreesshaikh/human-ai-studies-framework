"""Deterministic, bounded replay; raw code is never inferred from edit counts."""

from datetime import UTC, datetime


def replay_frames(events: list[dict], *, raw_code: bool = False) -> list[dict]:
    def key(event):
        try:
            instant = datetime.fromisoformat(event["ts"].replace("Z", "+00:00"))
            if instant.tzinfo is None:
                instant = instant.replace(tzinfo=UTC)
            timestamp = instant.timestamp()
        except (ValueError, TypeError):
            timestamp = float("inf")
        return timestamp, event["source"], event["seq"]

    frames = []
    for event in sorted(events, key=key):
        payload = event.get("payload") or {}
        patch = payload.get("diff")
        allowed = raw_code and payload.get("codeCaptureEnabled") is True
        frames.append(
            {
                "ts": event["ts"],
                "source": event["source"],
                "seq": event["seq"],
                "type": event["type"],
                "flags": event.get("flags", []),
                "changes": {
                    name: payload[name]
                    for name in ("filesChanged", "insertions", "deletions")
                    if isinstance(payload.get(name), int)
                    and not isinstance(payload[name], bool)
                    and payload[name] >= 0
                },
                "diff": patch
                if allowed and isinstance(patch, str) and len(patch) <= 64_000
                else None,
                "codeState": "captured"
                if allowed and isinstance(patch, str) and 0 < len(patch) <= 64_000
                else "policy-disabled"
                if not raw_code
                else "not-captured",
            }
        )
    return frames
