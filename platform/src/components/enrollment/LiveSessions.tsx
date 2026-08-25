import { useEffect, useRef, useState } from "react";
import { Radio } from "lucide-react";
import { studyApi, type LiveSession } from "@/lib/studyApi";
import { cn } from "@/lib/cn";

/* Who is running right now, and what they are doing.
 *
 * This is the payoff of the whole design → setup chain, and until now it had
 * nowhere to appear: the middleware has computed per-session event rates,
 * last-event types and gap counts all along (`GET /studies/{id}/live`), and
 * nothing rendered them. A researcher could mint a link and then had no way to
 * tell whether the editor on the other end was actually working.
 *
 * Three things are shown per session, because they are the three questions a
 * facilitator actually asks mid-study: is data arriving (the sparkline), what
 * are they working on (task and condition), and is anything being lost (gaps).
 *
 * Nothing here is seeded when the server is unreachable. An empty monitor is
 * the honest answer to "is anyone running?"; a fabricated one would be the
 * single worst place in the product to show invented data. */

const POLL_MS = 5_000;
/** Beyond this a session has gone quiet  -  the extension batches every 5s. */
const QUIET_MS = 30_000;

function quietFor(iso: string, now: number): number {
  const t = new Date(iso).getTime();
  return Number.isFinite(t) ? now - t : 0;
}

/** The event-rate sparkline: one bar per bucket, oldest at the left. */
function Rate({ rate }: { rate: number[] }) {
  const peak = Math.max(1, ...rate);
  return (
    <span
      className="flex h-5 items-end gap-px"
      aria-hidden
      title={`${rate.reduce((a, b) => a + b, 0)} events in the window`}
    >
      {rate.map((n, i) => (
        <span
          key={i}
          className={cn(
            "w-0.5 rounded-full transition-[height] duration-standard",
            n > 0 ? "bg-accent" : "bg-zone-8",
          )}
          style={{ height: `${Math.max(2, Math.round((n / peak) * 20))}px` }}
        />
      ))}
    </span>
  );
}

export function LiveSessions({ studyId }: { studyId: string }) {
  const [sessions, setSessions] = useState<LiveSession[] | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const timer = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    const poll = () =>
      void studyApi.live(studyId).then((doc) => {
        if (!cancelled) {
          setSessions(doc.sessions);
          setNow(Date.now());
        }
      });
    poll();
    timer.current = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      if (timer.current) clearInterval(timer.current);
    };
  }, [studyId]);

  // Before the first reply, say nothing rather than "no one is running"  -
  // the two are different answers and only one of them is known yet.
  if (sessions === null) return null;

  return (
    <div className="flex flex-col gap-2" data-agent="live-sessions">
      <div className="flex items-center gap-2">
        <Radio
          className={cn(
            "size-3.5",
            sessions.length ? "text-accent" : "text-text-muted",
          )}
          aria-hidden
        />
        <h3 className="type-legend text-text-muted">
          {sessions.length === 0
            ? "No sessions running"
            : `${sessions.length} session${sessions.length === 1 ? "" : "s"} running`}
        </h3>
      </div>

      {sessions.length > 0 && (
        <ul className="flex flex-col divide-y divide-border rounded-input border border-border">
          {sessions.map((s) => {
            const quiet = quietFor(s.lastReceivedAt, now) > QUIET_MS;
            const position =
              s.blockIndex !== null && s.blocksTotal
                ? `${s.blockIndex + 1} of ${s.blocksTotal}`
                : null;
            return (
              <li
                key={s.sessionId}
                className="type-body flex flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2"
                data-agent="live-session"
                data-agent-ref={s.sessionId}
              >
                <span className="flex shrink-0 items-baseline gap-1.5">
                  <span className="font-mono text-text">{s.participantId}</span>
                  <span className="font-mono type-legend text-text-muted" title="Session ID">
                    {s.sessionId}
                  </span>
                </span>
                <span className="min-w-0 flex-1 truncate text-text-muted">
                  {s.taskTitle || s.taskId ? (
                    <>
                      {s.taskTitle || s.taskId}
                      {position && (
                        <span className="tabular"> · task {position}</span>
                      )}
                    </>
                  ) : (
                    s.condition
                  )}
                </span>
                <span className="type-caption text-text-muted">
                  {s.condition}
                </span>
                <Rate rate={s.rate} />
                <span
                  className={cn(
                    "type-caption tabular",
                    quiet ? "text-text-muted italic" : "text-text-muted",
                  )}
                >
                  {quiet ? "quiet" : `${s.eventsInWindow} events`}
                </span>
                {s.gapCount > 0 && (
                  /* Never silent about loss: a gap means events the editor
                   * sent never arrived, and the researcher has to know while
                   * the session is still running, not at analysis. */
                  <span className="type-caption text-status-critical">
                    {s.missingEvents} missing
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
