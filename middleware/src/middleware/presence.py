"""Live presence and study updates (FR-PLAT collaboration).

Collaboration on a study is otherwise asynchronous: two researchers in the
same study see each other's work only by reloading. This is the smallest
thing that makes a shared study feel live —

- **who is looking at this study right now**, and
- **a push when the study changes** (a new conversation turn, a decided
  move, a fresh draft), so the other viewer's screen catches up on its own.

Deliberately not a collaborative editor. No CRDT, no operational transform,
no simultaneous typing: at the scale this platform targets (a handful of
researchers per study) that machinery would cost far more than it returns,
and the honest primitives — presence plus an invalidation push — deliver the
felt difference. Viewers act on the push by re-reading through the ordinary
endpoints, so the API stays the single source of truth and no state is
reconstructed from the event stream.

Transport is the same server-sent-events channel the streamed design turn
introduced, and the registry is in-process: one Railway container serves the
whole app, so a shared in-memory hub is the right size. If the service ever
runs replicated, this module is the one seam to move behind Redis pub/sub —
which is exactly why publishing goes through :func:`publish` rather than
touching queues at call sites.

Every subscriber gets a *bounded* queue: a viewer whose browser stalls drops
events rather than growing the server's memory, and is told it fell behind
(``dropped``) so it can do a full re-read instead of trusting a gapped
stream. Losing an event must never look like nothing happened.
"""

from __future__ import annotations

import logging
import queue
import threading
import uuid
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

#: Events a stalled client may buffer before it is treated as behind. Small
#: on purpose: these are invalidation pings, not a log to replay.
QUEUE_MAX = 64

#: How long a subscriber waits for an event before the stream emits a
#: keepalive comment. Under the 30-60s idle timeout proxies typically apply.
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
    """The in-process registry of who is watching what.

    Thread-safe by a single lock: FastAPI serves these sync endpoints from a
    thread pool, so subscribe/unsubscribe/publish genuinely race.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._viewers: dict[str, dict[str, Viewer]] = {}

    # ------------------------------------------------------- subscriptions

    def subscribe(self, study_id: str, sub: str, display_name: str, at: str) -> Viewer:
        viewer = Viewer(
            viewer_id=uuid.uuid4().hex[:12],
            sub=sub,
            display_name=display_name or "Someone",
            since=at,
        )
        with self._lock:
            self._viewers.setdefault(study_id, {})[viewer.viewer_id] = viewer
        # Everyone *else* is told the room changed; the new viewer's own first
        # frame is sent by the stream itself, so its queue holds only news.
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
        """Who is watching, one entry per person (not per tab): the same
        researcher in two windows is one presence, with its earliest join
        time — two chips for one colleague would read as two colleagues."""
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

    # ----------------------------------------------------------- publishing

    def publish(
        self, study_id: str, event: str, data: dict, *, exclude: str | None = None
    ) -> int:
        """Fan an event out to this study's viewers; returns how many got it.

        Never raises and never blocks: a full queue marks that subscriber as
        behind instead of stalling the writer that triggered the event (a
        conversation turn must not wait on someone's browser). ``exclude``
        skips one viewer id — used so a joiner doesn't receive its own
        arrival twice.
        """
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


#: The process-wide hub. One container, one registry (see the module note).
hub = Hub()
