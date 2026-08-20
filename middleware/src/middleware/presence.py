"""Live presence and study updates (FR-PLAT collaboration)."""

from __future__ import annotations

import logging
import queue
import threading
import uuid
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# Small on purpose: these are invalidation pings, not a log to replay.
QUEUE_MAX = 64

KEEPALIVE_SECONDS = 15.0


@dataclass
class Viewer:
    """One open subscription: a person looking at a study right now."""

    viewer_id: str
    sub: str
    display_name: str
    since: str
    events: queue.Queue = field(default_factory=lambda: queue.Queue(QUEUE_MAX))
    dropped: int = 0


class Hub:
    """The in-process registry of who is watching what."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._viewers: dict[str, dict[str, Viewer]] = {}


    def subscribe(self, study_id: str, sub: str, display_name: str, at: str) -> Viewer:
        viewer = Viewer(
            viewer_id=uuid.uuid4().hex[:12],
            sub=sub,
            display_name=display_name or "Someone",
            since=at,
        )
        with self._lock:
            self._viewers.setdefault(study_id, {})[viewer.viewer_id] = viewer
        self.publish(
            study_id,
            "presence",
            {"viewers": self.viewers(study_id)},
            exclude=viewer.viewer_id,
        )
        return viewer

    def unsubscribe(self, study_id: str, viewer_id: str) -> None:
        with self._lock:
            self._viewers.get(study_id, {}).pop(viewer_id, None)
            if not self._viewers.get(study_id):
                self._viewers.pop(study_id, None)
        self.publish(study_id, "presence", {"viewers": self.viewers(study_id)})

    def viewers(self, study_id: str) -> list[dict]:
        """
        Who is watching, one entry per person (not per tab): the same researcher in two
        windows is one presence, with its earliest join time — two chips for one
        colleague would read as two colleagues.
        """
        with self._lock:
            open_viewers = list(self._viewers.get(study_id, {}).values())
        by_person: dict[str, dict] = {}
        for v in open_viewers:
            existing = by_person.get(v.sub)
            if existing is None or v.since < existing["since"]:
                by_person[v.sub] = {
                    "sub": v.sub,
                    "displayName": v.display_name,
                    "since": v.since,
                }
        return sorted(by_person.values(), key=lambda v: (v["since"], v["sub"]))


    def publish(
        self, study_id: str, event: str, data: dict, *, exclude: str | None = None
    ) -> int:
        """Fan an event out to this study's viewers; returns how many got it."""
        with self._lock:
            targets = [
                v
                for v in self._viewers.get(study_id, {}).values()
                if v.viewer_id != exclude
            ]
        delivered = 0
        for viewer in targets:
            try:
                viewer.events.put_nowait((event, data))
                delivered += 1
            except queue.Full:
                viewer.dropped += 1
                log.warning(
                    "presence: viewer %s on %s is behind (%d dropped)",
                    viewer.viewer_id,
                    study_id,
                    viewer.dropped,
                )
        return delivered


hub = Hub()
