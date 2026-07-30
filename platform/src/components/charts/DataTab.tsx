import { useEffect, useState } from "react";
import { CheckCircle2, AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";
import { Info } from "lucide-react";
import { MetricStrip } from "./MetricStrip";
import { SwimlaneTimeline } from "./SwimlaneTimeline";
import { PrescriptionPanel } from "./PrescriptionPanel";
import { DataProvenance } from "./DataProvenance";
import { Surface } from "@/components/shell/Surface";
import {
  studyApi,
  onSeededData,
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
  const [expandedSession, setExpandedSession] = useState<string | null>(null);
  const [seeded, setSeeded] = useState(false);

  useEffect(() => {
    // If any read falls back to built-in sample data, say so honestly.
    const off = onSeededData(() => setSeeded(true));
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
      off();
    };
  }, [studyId]);

  const metricRows = rows;

  return (
    <Surface measure="work" label="Data">
      {seeded && (
        <p
          className="flex items-center gap-2 rounded-input border border-border-strong bg-unsourced-soft px-3 py-2 text-xs text-text"
          role="status"
        >
          <Info className="size-4 shrink-0 text-unsourced" aria-hidden />
          Showing built-in sample data, not connected to a live study. Start the
          middleware to see this study's real sessions and metrics.
        </p>
      )}
      {/* Before any data exists, the provenance decision comes first: collect
          it live or curate it from GitHub. */}
      {sessions.length === 0 && (
        <DataProvenance studyId={studyId} conditions={conditions} />
      )}

      <section className="flex flex-col gap-stack">
        <h2 className="type-section text-text">Sessions</h2>
        {sessions.length === 0 ? (
          <p className="rounded-card border border-border bg-surface p-6 text-sm text-text-muted">
            No sessions yet. Collected data appears here per session, with its
            completeness and any integrity flags.
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {sessions.map((s) => {
              const isOpen = expandedSession === s.sessionId;
              return (
                <div
                  key={s.sessionId}
                  className="rounded-card border border-border bg-surface"
                >
                  <button
                    type="button"
                    className="flex w-full items-center justify-between p-4 text-left hover:bg-surface-raised/50"
                    onClick={() =>
                      setExpandedSession(isOpen ? null : s.sessionId)
                    }
                  >
                    <div className="flex items-center gap-2">
                      {isOpen ? (
                        <ChevronDown className="size-4 text-text-muted" aria-hidden />
                      ) : (
                        <ChevronRight className="size-4 text-text-muted" aria-hidden />
                      )}
                      <div>
                        <span className="font-medium text-text">{s.participantId}</span>
                        <span className="ml-2 rounded-chip bg-accent-soft px-2 py-0.5 text-xs text-accent">
                          {s.condition}
                        </span>
                      </div>
                    </div>
                    <dl className="flex gap-4 text-sm">
                      <Stat label="events" value={s.events} />
                      <Stat label="metric rows" value={s.metricRows} />
                      <Stat label="gaps" value={s.gapCount} />
                    </dl>
                    <p
                      className={cn(
                        "flex items-center gap-1 text-xs",
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
                  </button>
                  {isOpen && (
                    <div className="border-t border-border px-4 pb-4 pt-3">
                      <SwimlaneTimeline
                        sessionId={s.sessionId}
                        studyId={studyId}
                        onClose={() => setExpandedSession(null)}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Metrics and the prescription that reads them sit close together —
          they're one analytical unit, tighter than the section gap. */}
      <div className="flex flex-col gap-stack">
        <section className="flex flex-col gap-stack">
          <h2 className="type-section text-text">Metrics by condition</h2>
          <MetricStrip rows={metricRows} conditions={conditions} />
        </section>
        <PrescriptionPanel />
      </div>
    </Surface>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col items-center">
      <dd className="tabular text-base text-text">{value}</dd>
      <dt className="text-xs text-text-muted">{label}</dt>
    </div>
  );
}
