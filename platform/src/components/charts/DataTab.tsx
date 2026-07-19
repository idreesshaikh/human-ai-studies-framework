import { useEffect, useState } from "react";
import { CheckCircle2, AlertTriangle } from "lucide-react";
import { MetricStrip } from "./MetricStrip";
import {
  studyApi,
  type DatasetRow,
  type SessionStatus,
} from "@/lib/studyApi";
import { cn } from "@/lib/cn";

/* The Data surface — the study's collected data as honest shapes (NFR-8).
 * Per-session
 * integrity (completeness, seq gaps, flags) and the metric distribution split
 * by condition. Nothing here animates — data is the celebration. */
export function DataTab({ studyId }: { studyId: string }) {
  const [sessions, setSessions] = useState<SessionStatus[]>([]);
  const [conditions, setConditions] = useState<string[]>([]);
  const [rows, setRows] = useState<DatasetRow[]>([]);

  useEffect(() => {
    let live = true;
    Promise.all([studyApi.status(studyId), studyApi.dataset(studyId)]).then(
      ([s, d]) => {
        if (!live) return;
        setSessions(s.sessions);
        setConditions(s.conditions);
        setRows(d.rows.filter((r) => r.source === "metrics"));
      },
    );
    return () => {
      live = false;
    };
  }, [studyId]);

  const metricRows = rows;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 overflow-auto p-6">
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-text">Sessions</h2>
        {sessions.length === 0 ? (
          <p className="rounded-card border border-border bg-surface p-6 text-sm text-text-muted">
            No sessions yet. Collected data appears here per session, with its
            completeness and any integrity flags.
          </p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {sessions.map((s) => (
              <div
                key={s.sessionId}
                className="rounded-card border border-border bg-surface p-4"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-text">{s.participantId}</span>
                  <span className="rounded-chip bg-accent-soft px-2 py-0.5 text-xs text-accent">
                    {s.condition}
                  </span>
                </div>
                <dl className="mt-2 grid grid-cols-3 gap-2 text-sm">
                  <Stat label="events" value={s.events} />
                  <Stat label="metric rows" value={s.metricRows} />
                  <Stat label="gaps" value={s.gapCount} />
                </dl>
                <p
                  className={cn(
                    "mt-2 flex items-center gap-1 text-xs",
                    s.complete ? "text-grounded" : "text-unsourced",
                  )}
                >
                  {s.complete ? (
                    <>
                      <CheckCircle2 className="size-3" aria-hidden /> complete
                    </>
                  ) : (
                    <>
                      <AlertTriangle className="size-3" aria-hidden />
                      {s.missingEvents > 0
                        ? `${s.missingEvents} events missing`
                        : "in progress"}
                      {s.flagKinds.length > 0 && ` · ${s.flagKinds.join(", ")}`}
                    </>
                  )}
                </p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-text">Metrics by condition</h2>
        <MetricStrip rows={metricRows} conditions={conditions} />
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dd className="tabular text-lg text-text">{value}</dd>
      <dt className="text-xs text-text-muted">{label}</dt>
    </div>
  );
}
