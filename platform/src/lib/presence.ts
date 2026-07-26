import { useEffect, useRef, useState } from "react";
import { getAuthToken } from "./api.ts";

/* Live presence + study-change pushes (FR-PLAT collaboration).
 *
 * The server's SSE channel is consumed with fetch streaming rather than
 * `EventSource`, because `EventSource` cannot send an Authorization header
 * and putting a bearer token in a query string would leak it into logs.
 *
 * A change event carries only *what* changed. Acting on it means re-reading
 * through the ordinary endpoints, so this stream never becomes a second
 * source of truth — and a `dropped` frame (this viewer fell behind) is
 * treated as "re-read everything", never as "nothing happened". */

const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");

export interface PresenceViewer {
  sub: string;
  displayName: string;
  since: string;
}

export interface StudyChange {
  changed: "conversation" | "move" | "draft";
  turnId?: string;
  moveId?: string;
  status?: string;
  compilationId?: string;
}

/** Who else is in this study, and the last change pushed from the server.
 *
 * Degrades silently and completely: with no server, no SSE support, or a
 * proxy that buffers, `viewers` stays empty and nothing else in the
 * workspace behaves differently. Presence is an enhancement, never a
 * dependency. */
export function usePresence(studyId: string | undefined): {
  viewers: PresenceViewer[];
  change: StudyChange | null;
} {
  const [viewers, setViewers] = useState<PresenceViewer[]>([]);
  const [change, setChange] = useState<StudyChange | null>(null);
  // Kept in a ref so a re-render never restarts the stream.
  const aborted = useRef(false);

  useEffect(() => {
    if (!studyId) return;
    aborted.current = false;
    const controller = new AbortController();

    (async () => {
      try {
        const token = await getAuthToken();
        const res = await fetch(
          `${API_BASE}/studies/${encodeURIComponent(studyId)}/presence/stream`,
          {
            headers: {
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
              accept: "text/event-stream",
            },
            credentials: "include",
            signal: controller.signal,
          },
        );
        if (!res.ok || !res.body) return;

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split("\n\n");
          buffer = frames.pop() ?? "";
          for (const frame of frames) {
            if (frame.startsWith(":")) continue; // keepalive
            const event = /^event: (.+)$/m.exec(frame)?.[1];
            const raw = /^data: (.*)$/m.exec(frame)?.[1];
            if (!event || raw == null || aborted.current) continue;
            const payload = JSON.parse(raw);
            if (event === "presence") setViewers(payload.viewers ?? []);
            else if (event === "study") setChange(payload as StudyChange);
            // Fell behind: re-read everything rather than trust a gapped
            // stream. A synthetic conversation change is the broadest nudge
            // the consumers already know how to handle.
            else if (event === "dropped") setChange({ changed: "conversation" });
          }
        }
      } catch {
        /* Offline, aborted, or unsupported — presence simply stays empty. */
      }
    })();

    return () => {
      aborted.current = true;
      controller.abort();
      setViewers([]);
    };
  }, [studyId]);

  return { viewers, change };
}
