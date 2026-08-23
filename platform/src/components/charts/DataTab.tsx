import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  FlaskConical,
} from "lucide-react";
import { Info } from "lucide-react";
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
  OfflineError,
  onSeededData,
  type DatasetRow,
  type SessionStatus,
} from "@/lib/studyApi";
import { cn } from "@/lib/cn";

/* The Data surface  -  the study's collected data as honest shapes (NFR-8).
 * Per-session
 * integrity (completeness, seq gaps, flags) and the metric distribution split
 * by condition. Nothing here animates  -  data is the celebration. */
export function DataTab({ studyId }: { studyId: string }) {
  const [sessions, setSessions] = useState<SessionStatus[]>([]);
  const [conditions, setConditions] = useState<string[]>([]);
  const [rows, setRows] = useState<DatasetRow[]>([]);
  const [expandedSession, setExpandedSession] = useState<string | null>(null);
  const [seeded, setSeeded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [dryRun, setDryRun] = useState<{
    report: Awaited<ReturnType<typeof studyApi.simulate>> | null;
    error: string | null;
    busy: boolean;
  }>({ report: null, error: null, busy: false });

  const refresh = (live: boolean, initial = false) => {
    Promise.all([studyApi.status(studyId), studyApi.dataset(studyId)])
      .then(([s, d]) => {
        if (!live) return;
        setLoadError(null);
        setSessions(s.sessions);
        setConditions(s.conditions);
        setRows(d.rows.filter((r) => r.source === "metrics"));
      })
      .catch((e: unknown) => {
        if (!live) return;
        // A study that hasn't compiled a protocol yet has no data  -  that's a
        // real, reachable state, not a fault. Surface it calmly instead of
        // letting the rejection blank the tab.
        setLoadError(
          e instanceof Error ? e.message : "Could not load this study's data.",
        );
      })
      .finally(() => {
        if (live && initial) setLoading(false);
      });
  };

  useEffect(() => {
    // If any read falls back to built-in sample data, say so honestly.
    const off = onSeededData((seededStudy) => {
      if (seededStudy === studyId) setSeeded(true);
    });
    let live = true;
    // Re-arm the loading gate on every study switch, not just first mount  -
    // `StudyHome` doesn't remount `DataTab` on a route change between two
    // studies, so without this the stale `loading: false` from the previous
    // study let its sessions/rows flash under the new study's tab for the
    // gap between navigation and this fetch resolving. Clearing the arrays
    // too, not just the flag: if the new study's fetch fails with anything
    // other than "no protocol", the old study's sessions would otherwise
    // still be sitting in state and render right alongside that error.
    setLoading(true);
    setSeeded(false);
    setSessions([]);
    setConditions([]);
    setRows([]);
    setLoadError(null);
    refresh(live, true);
    return () => {
      live = false;
      off();
    };
  }, [studyId]);

  const runDryRun = async () => {
    setDryRun({ report: null, error: null, busy: true });
    try {
      const report = await studyApi.simulate(studyId, 10);
      setDryRun({ report, error: null, busy: false });
      refresh(true);
    } catch (e) {
      if (e instanceof OfflineError) {
        // No middleware: the rehearsal falls back to the honest client-side
        // rows DataProvenance already knows how to draw.
        setDryRun({ report: null, error: null, busy: false });
        setShowClientRehearsal(true);
        return;
      }
      setDryRun({
        report: null,
        error: e instanceof Error ? e.message : "dry run failed",
        busy: false,
      });
    }
  };
  const [showClientRehearsal, setShowClientRehearsal] = useState(false);

  const metricRows = rows;

  /* A study whose protocol has never compiled has no data by definition  -  not
   * three separate absences. The tab used to say so three times, in three
   * dashed boxes of equal weight stacked down five hundred pixels: "no
   * compiled protocol", then "no sessions", then "no metric rows carry
   * cognitive_complexity"  -  the last two being consequences of the first, and
   * the metric picker above them offering a choice that could not change
   * anything. Three statements of one fact read as three faults.
   *
   * One precondition, said once, with the move that resolves it. */
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
              {/* The tab lives in the URL, so this is a real link: it is
                * back-navigable and shareable, not a state poke. */}
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
      {seeded && (
        <p
          className="flex items-center gap-2 rounded-control border border-border bg-well px-3 py-2 type-caption text-text"
          role="status"
        >
          <Info className="size-4 shrink-0 text-text-muted" aria-hidden />
          Showing built-in sample data, not connected to a live study. Start the
          middleware to see this study's real sessions and metrics.
        </p>
      )}
      {/* The no-protocol case returned above; anything reaching here is a
        * genuine fault, so it is reported as one rather than as an absence. */}
      {loadError && (
        <Notice kind="problem">
          Couldn&apos;t load this study&apos;s data. {loadError}
        </Notice>
      )}

      {/* Before any data exists, the provenance decision comes first: collect
          it live or rehearse with synthetic data. */}
      {!loadError && sessions.length === 0 && (
        <DataProvenance
          conditions={conditions}
          onDryRun={runDryRun}
          dryRunBusy={dryRun.busy}
          showClientRehearsal={showClientRehearsal}
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
            minted tokens are marked synthetic, and the dataset labels them
            by run id. They are for rehearsal, never results.
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
                      <div>
                        <span className="font-medium text-text">{s.participantId}</span>
                        <span className="ml-2 rounded-chip bg-zone-9 px-2 py-0.5 type-legend text-text">
                          {s.condition}
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

      {/* Metrics and the prescription that reads them sit close together  -
          they're one analytical unit, tighter than the section gap. */}
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

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col items-center">
      <dd className="tabular type-body-lg text-text">{value}</dd>
      <dt className="type-caption text-text-muted">{label}</dt>
    </div>
  );
}
