import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Download,
} from "lucide-react";
import { MetricStrip } from "./MetricStrip";
import { SwimlaneTimeline } from "./SwimlaneTimeline";
import { PrescriptionPanel } from "./PrescriptionPanel";
import { ControlAudit } from "./ControlAudit";
import { Surface } from "@/components/shell/Surface";
import { EmptyState } from "@/components/shell/EmptyState";
import { Button } from "@/components/ui/button";
import {
  studyApi,
  type DatasetRow,
  type SessionStatus,
  type StudyStatusDoc,
} from "@/lib/studyApi";
import { cn } from "@/lib/cn";
import { laneLabel } from "@/lib/timeline";
import { hasRole, type Role } from "@/lib/capabilities";
import { Notice } from "@/components/ui/notice";
import { OPEN_SETUP, DATA_EMPTY_TITLE, DATA_EMPTY_BODY, conditionLabel } from "@/lib/uiText";
import { SYNTHETIC_EXAMPLE_LABEL } from "@/lib/syntheticExample";
import { OutcomeChecks } from "./OutcomeChecks";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Pagination, paginate } from "@/components/ui/pagination";

export function DataTab({
  studyId,
  role,
  hasProtocol,
}: {
  studyId: string;
  role?: Role | null;
  hasProtocol: boolean;
}) {
  const [sessions, setSessions] = useState<SessionStatus[]>([]);
  const [statusDoc, setStatusDoc] = useState<StudyStatusDoc | null>(null);
  const [conditions, setConditions] = useState<string[]>([]);
  const [rows, setRows] = useState<DatasetRow[]>([]);
  const [synthetic, setSynthetic] = useState(false);
  const [expandedSession, setExpandedSession] = useState<string | null>(null);
  const [sessionQuery, setSessionQuery] = useState("");
  const [sessionPage, setSessionPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [decisionRevision, setDecisionRevision] = useState(0);
  const [download, setDownload] = useState({ busy: false, error: "" });
  const generation = useRef(0);
  const loadData = useCallback(() => {
    const version = ++generation.current;
    setLoadError(null);
    // The seeded example holds only simulated sessions. They are read on
    // request, for that study alone, and shown under a notice; every other
    // study keeps the default read, which leaves synthetic rows out.
    return Promise.all([studyApi.status(studyId), studyApi.dataset(studyId)])
      .then((plain) =>
        plain[0].syntheticExample
          ? Promise.all([
              studyApi.status(studyId, true),
              studyApi.dataset(studyId, true),
            ])
          : plain,
      )
      .then(([s, d]) => {
        if (generation.current !== version) return;
        setSynthetic(Boolean(s.syntheticExample));
        setSessions(s.sessions);
        setStatusDoc(s);
        setConditions(s.conditions);
        setRows(d.rows);
      })
      .catch((e) => {
        if (generation.current === version)
          setLoadError(
            e instanceof Error ? e.message : "Could not load study data.",
          );
      })
      .finally(() => {
        if (generation.current === version) setLoading(false);
      });
  }, [studyId]);
  useEffect(() => {
    if (!hasProtocol) return;
    setLoading(true);
    setSessionQuery("");
    setSessionPage(0);
    setExpandedSession(null);
    void loadData();
    return () => {
      generation.current++;
    };
  }, [hasProtocol, loadData]);
  async function downloadFile(kind: "data" | "card" | "kit") {
    setDownload({ busy: true, error: "" });
    try {
      if (kind === "data") await studyApi.downloadDataBundle(studyId);
      else if (kind === "kit") await studyApi.downloadReplicationKit(studyId);
      else await studyApi.downloadDesignCard(studyId);
      setDownload({ busy: false, error: "" });
    } catch (e) {
      setDownload({
        busy: false,
        error: e instanceof Error ? e.message : "Download failed.",
      });
    }
  }
  const visibleSessions = paginate(sessions.filter((session) =>
    `${session.participantId} ${session.condition} ${conditionLabel(session.condition)} ${session.sessionId}`.toLowerCase().includes(sessionQuery.trim().toLowerCase()),
  ), sessionPage);
  if (!hasProtocol)
    return (
      <Surface measure="work" label="Data">
        <h2 className="type-section text-text">{DATA_EMPTY_TITLE}</h2>
        <EmptyState line={DATA_EMPTY_BODY} action={
          <Button asChild size="sm">
            <Link to={{ search: "?tab=conversation" }}>{OPEN_SETUP}</Link>
          </Button>
        } />
      </Surface>
    );
  if (loading)
    return (
      <Surface measure="work" label="Data">
        <p className="type-body text-text-muted" role="status">
          Loading real captured data…
        </p>
      </Surface>
    );
  return (
    <Surface measure="work" label="Data">
      {loadError ? (
        <p className="type-body text-critical" role="alert">
          {loadError}
        </p>
      ) : (
        <>
          {synthetic && (
            <Notice>
              <strong>{SYNTHETIC_EXAMPLE_LABEL}</strong> Every session below was
              simulated by <code>seed-example</code> to show how a study reads
              once data arrives. No participant took part. The rows are marked
              synthetic and are left out of data bundles, pilot estimates and
              analysis recipes, so a downloaded data bundle for this study is
              empty.
            </Notice>
          )}
          <section className="flex flex-col gap-3 border-b border-border pb-5">
            <h2 className="type-subhead text-text">Download study records</h2>
            <p className="type-note text-text-muted">
              Export captured data or the recorded study design. Synthetic rows
              are excluded; pilot tags and inclusion decisions are retained.
            </p>
            <div className="flex flex-wrap gap-3">
              <Button
                size="sm"
                variant="outline"
                disabled={download.busy}
                onClick={() => void downloadFile("data")}
              >
                <Download className="size-4" aria-hidden />
                Data (.zip)
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={download.busy}
                onClick={() => void downloadFile("card")}
              >
                Design card (.md)
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={download.busy || !hasRole(role, "run_recipe")}
                onClick={() => void downloadFile("kit")}
              >
                Replication kit
              </Button>
            </div>
            {download.error && (
              <p className="type-note text-critical" role="alert">
                {download.error}
              </p>
            )}
          </section>
          <OutcomeChecks key={`${studyId}:${decisionRevision}`} studyId={studyId} synthetic={synthetic} onChecked={() => void loadData()} />
          <section className="flex flex-col gap-stack" aria-label="Captured sessions">
            <h2 className="type-section text-text">
              {synthetic ? "Sessions (synthetic)" : "Sessions"}
            </h2>
            {sessions.length > 0 && <Field label="Search sessions">
              <Input type="search" value={sessionQuery} placeholder="Participant, condition or session" onChange={(e) => { setSessionQuery(e.target.value); setSessionPage(0); setExpandedSession(null); }} />
            </Field>}
            {sessions.length === 0 ? (
              <EmptyState line="No sessions yet. Collected data appears here per session, with its completeness and any integrity flags." />
            ) : (
              <div className="flex flex-col gap-3">
                {visibleSessions.rows.map((s) => {
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
                        className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-card p-3 text-left hover:bg-zone-9 sm:grid-cols-[minmax(0,1fr)_auto_auto]"
                        aria-expanded={isOpen}
                        onClick={() =>
                          setExpandedSession(isOpen ? null : s.sessionId)
                        }
                      >
                        <div className="flex min-w-0 items-center gap-2">
                          {isOpen ? (
                            <ChevronDown
                              className="size-4 text-text-muted"
                              aria-hidden
                            />
                          ) : (
                            <ChevronRight
                              className="size-4 text-text-muted"
                              aria-hidden
                            />
                          )}
                          <div className="min-w-0">
                            <div>
                              <span className="font-medium text-text">
                                {s.participantId}
                              </span>
                              <span className="ml-2 rounded-chip bg-zone-9 px-2 py-0.5 type-legend text-text">
                                {conditionLabel(s.condition)}
                              </span>
                            </div>
                            <span
                              className="mt-1 block truncate font-mono type-legend text-text-muted"
                              title="Session ID"
                            >
                              {s.sessionId}
                            </span>
                          </div>
                        </div>
                        <dl className="col-span-2 flex gap-4 type-body sm:col-span-1 sm:col-start-2 sm:row-start-1">
                          <Stat label="events" value={s.events} />
                          <Stat label="metric rows" value={s.metricRows} />
                          <Stat label="gaps" value={s.gapCount} />
                        </dl>
                        <p
                          className={cn(
                            "col-start-2 row-start-1 flex items-center gap-1 type-caption sm:col-start-3",
                            s.complete ? "text-text" : "text-critical",
                          )}
                        >
                          {s.complete ? (
                            <>
                              <CheckCircle2 className="size-3" aria-hidden />{" "}
                              no flags
                            </>
                          ) : (
                            <>
                              <AlertTriangle className="size-3" aria-hidden />
                              {s.flagKinds.length > 0 ? "Review capture" : s.missingEvents > 0
                                ? `${s.missingEvents} event${s.missingEvents === 1 ? "" : "s"} missing`
                                : "in progress"}
                            </>
                          )}
                        </p>
                      </button>
                      {isOpen && (
                        <div className="border-t border-border px-4 pb-4 pt-3">
                          <div className="mb-3 flex flex-wrap items-center gap-2 type-caption text-text-muted">
                            <span>task: {s.taskId || "not stamped"}</span>
                            {s.flagKinds.length > 0 && <span className="break-words text-critical">{s.flagKinds.join(", ")}</span>}
                            {Object.entries(s.sourceCounts ?? {}).map(
                              ([source, count]) => (
                                <span
                                  key={source}
                                  className="rounded-chip bg-well px-2 py-0.5"
                                >
                                  {laneLabel(source)}: {count}
                                </span>
                              ),
                            )}
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
                {visibleSessions.total === 0 && <p className="type-note text-text-muted" role="status">No matching sessions. Try another search.</p>}
                <Pagination {...visibleSessions} label="Sessions" onChange={(page) => { setSessionPage(page); setExpandedSession(null); }} />
              </div>
            )}
          </section>

          <ControlAudit
            studyId={studyId}
            sessions={sessions}
            role={role}
            onUpdated={() => { setDecisionRevision((r) => r + 1); void loadData(); }}
            synthetic={synthetic}
          />
          <div className="flex flex-col gap-stack">
            <section className="flex flex-col gap-stack" aria-label="Measurements">
              <h2 className="type-section text-text">
                Measurements by condition
              </h2>
              {synthetic ? (
                <p className="type-note text-text">
                  {SYNTHETIC_EXAMPLE_LABEL}
                </p>
              ) : (
                <p className="type-note text-text-muted">
                  Pilot sessions and researcher-excluded sessions are omitted
                  from this comparison.
                </p>
              )}
              <MetricStrip
                rows={rows.filter(
                  (r) => !r.pilot && r.inclusionDecision !== "exclude",
                )}
                conditions={conditions}
              />
            </section>
            <PrescriptionPanel studyId={studyId} />
          </div>
        </>
      )}
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
