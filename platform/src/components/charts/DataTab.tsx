import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  FlaskConical,
} from "lucide-react";
import { MetricStrip } from "./MetricStrip";
import { SwimlaneTimeline } from "./SwimlaneTimeline";
import { PrescriptionPanel } from "./PrescriptionPanel";
import { DataProvenance } from "./DataProvenance";
import { DryRunPlan } from "./DryRunPlan";
import { Surface } from "@/components/shell/Surface";
import { EmptyState } from "@/components/shell/EmptyState";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import {
  studyApi,
  type DatasetRow,
  type SessionStatus,
  type StudyStatusDoc,
} from "@/lib/studyApi";
import { cn } from "@/lib/cn";

export function DataTab({ studyId }: { studyId: string; }) {
  const [sessions, setSessions] = useState<SessionStatus[]>([]);
  const [statusDoc, setStatusDoc] = useState<StudyStatusDoc | null>(null);
  const [conditions, setConditions] = useState<string[]>([]);
  const [rows, setRows] = useState<DatasetRow[]>([]);
  const [expandedSession, setExpandedSession] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [dryRun, setDryRun] = useState<{
    report: Awaited<ReturnType<typeof studyApi.simulate>> | null;
    error: string | null;
    busy: boolean;
  }>({ report: null, error: null, busy: false });

  const currentStudy = useRef<string | null>(studyId);

  const refresh = (isCurrent: () => boolean, initial = false) => {
    Promise.all([studyApi.status(studyId), studyApi.dataset(studyId)])
      .then(([s, d]) => {
        if (!isCurrent()) return;
        setLoadError(null);
        setSessions(s.sessions);
        setStatusDoc(s);
        setConditions(s.conditions);
        setRows(d.rows.filter((r) => r.source === "metrics"));
      })
      .catch((e: unknown) => {
        if (!isCurrent()) return;
        setLoadError(
          e instanceof Error ? e.message : "Could not load this study's data.",
        );
      })
      .finally(() => {
        if (isCurrent() && initial) setLoading(false);
      });
  };

  useEffect(() => {
    let live = true;
    setLoading(true);
    setSessions([]);
    setStatusDoc(null);
    setConditions([]);
    setRows([]);
    setLoadError(null);
    currentStudy.current = studyId;
    setDryRun({ report: null, error: null, busy: false });
    setExpandedSession(null);
    refresh(() => live, true);
    return () => {
      live = false;
      currentStudy.current = null;
    };
  }, [studyId]);

  const runDryRun = async () => {
    setDryRun({ report: null, error: null, busy: true });
    try {
      const report = await studyApi.simulate(studyId, 10);
      if (currentStudy.current !== studyId) return;
      setDryRun({ report, error: null, busy: false });
      refresh(() => currentStudy.current === studyId);
    } catch (e) {
      if (currentStudy.current !== studyId) return;
      setDryRun({
        report: null,
        error: e instanceof Error ? e.message : "dry run failed",
        busy: false,
      });
    }
  };

  const metricRows = rows;

  const noProtocol =
    !!loadError && loadError.toLowerCase().includes("no protocol");

  if (loading) return null;

  if (noProtocol) {
    return (
      <Surface measure="work" label="Data">
        <EmptyState
          line={
            <>
              Nothing has been collected yet: this study has no compiled
              protocol. Design it in the conversation and apply the draft  -
              its sessions, integrity flags and metrics appear here once
              participants start running it.
            </>
          }
          action={
            <Button asChild size="sm">

              <Link to={{ search: "?tab=conversation" }}>
                Open the design conversation
              </Link>
            </Button>
          }
        />
      </Surface>
    );
  }

  return (
    <Surface measure="work" label="Data">

      {loadError && (
        <Notice kind="problem">
          Couldn&apos;t load this study&apos;s data. {loadError}
        </Notice>
      )}

      {statusDoc && Object.keys(statusDoc.producers).length > 0 && (
        <section className="flex flex-col gap-2 border-b border-border pb-5">
          <div>
            <h2 className="type-subhead text-text">Configured producers</h2>
            <p className="mt-1 max-w-reading type-caption text-text-muted">
              Configuration is not receipt. A source is counted below only after its events or metric rows arrive.
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {Object.entries(statusDoc.producers).map(([id, producer]) => (
              <div key={id} className="rounded-input border border-border px-3 py-2">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="type-label text-text">{id}</span>
                  <span className="type-caption text-text-muted">{producer.state}</span>
                </div>
                <p className="mt-0.5 type-caption text-text-muted">{producer.reason}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {!loadError && sessions.length === 0 && (
        <DataProvenance
          onDryRun={runDryRun}
          dryRunBusy={dryRun.busy}
        />
      )}

      {dryRun.report && (
        <div className="flex items-start gap-2 rounded-plate border border-dashed border-unsourced bg-well p-3">
          <FlaskConical
            className="mt-0.5 size-4 shrink-0 text-text-muted"
            aria-hidden
          />
          <p className="type-caption text-text">
            <span className="type-label text-text">
              Dry run complete: {dryRun.report.participants} synthetic
              participants
            </span>
            <br />
            {dryRun.report.sessions} sessions, {dryRun.report.events} events
            stored through the real capture path. These sessions are simulated;
            they are excluded from live results and default exports.
          </p>
        </div>
      )}
      {dryRun.report?.plan && <DryRunPlan plan={dryRun.report.plan} />}
      {dryRun.error && (
        <p className="type-caption text-critical" role="alert">
          {dryRun.error}
        </p>
      )}

      <section className="flex flex-col gap-stack">
        <h2 className="type-section text-text">Sessions</h2>
        {sessions.length === 0 ? (
          <EmptyState line="No sessions yet. Collected data appears here per session, with its completeness and any integrity flags." />
        ) : (
          <div className="flex flex-col gap-3">
            {sessions.map((s) => {
              const isOpen = expandedSession === s.sessionId;
              const missingProducers = statusDoc
                ? statusDoc.requiredProducers.filter((id) => {
                  const source = statusDoc.producers[id]?.source ?? id;
                  return (s.sourceCounts?.[source] ?? 0) === 0;
                })
                : [];
              return (
                <div
                  key={s.sessionId}
                  className="rounded-card border border-border bg-surface"
                >
                  <button
                    type="button"
                    className="flex w-full items-center justify-between p-4 text-left hover:bg-zone-9"
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
                      <div className="min-w-0">
                        <div>
                          <span className="font-medium text-text">{s.participantId}</span>
                          <span className="ml-2 rounded-chip bg-zone-9 px-2 py-0.5 type-legend text-text">
                            {s.condition}
                          </span>
                        </div>
                        <span className="mt-1 block truncate font-mono type-legend text-text-muted" title="Session ID">
                          {s.sessionId}
                        </span>
                      </div>
                    </div>
                    <dl className="flex gap-4 type-body">
                      <Stat label="events" value={s.events} />
                      <Stat label="metric rows" value={s.metricRows} />
                      <Stat label="gaps" value={s.gapCount} />
                    </dl>
                    <p
                      className={cn(
                        "flex items-center gap-1 type-caption",
                        s.complete ? "text-text" : "text-critical",
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
                            ? `${s.missingEvents} event${s.missingEvents === 1 ? "" : "s"} missing`
                            : "in progress"}
                          {s.flagKinds.length > 0 && ` · ${s.flagKinds.join(", ")}`}
                        </>
                      )}
                    </p>
                  </button>
                  {isOpen && (
                    <div className="border-t border-border px-4 pb-4 pt-3">
                      <div className="mb-3 flex flex-wrap items-center gap-2 type-caption text-text-muted">
                        <span>task: {s.taskId || "not stamped"}</span>
                        {Object.entries(s.sourceCounts ?? {}).map(([source, count]) => (
                          <span key={source} className="rounded-chip bg-well px-2 py-0.5">
                            {source}: {count}
                          </span>
                        ))}
                        {missingProducers.length > 0 && (
                          <span className="text-critical">
                            missing required: {missingProducers.join(", ")}
                          </span>
                        )}
                      </div>
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

      <div className="flex flex-col gap-stack">
        <section className="flex flex-col gap-stack">
          <h2 className="type-section text-text">Metrics by condition</h2>
          <p className="-mt-2 max-w-reading type-body text-text-muted">
            Compare one code measure across study conditions. Each dot is one
            analyzed function; the line shows the group median.
          </p>
          <MetricStrip rows={metricRows} conditions={conditions} />
        </section>
        <PrescriptionPanel studyId={studyId} />
      </div>
    </Surface>
  );
}

function Stat({ label, value }: { label: string; value: number; }) {
  return (
    <div className="flex flex-col items-center">
      <dd className="tabular type-body-lg text-text">{value}</dd>
      <dt className="type-caption text-text-muted">{label}</dt>
    </div>
  );
}
