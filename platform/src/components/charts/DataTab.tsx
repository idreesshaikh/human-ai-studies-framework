import { useEffect, useRef, useState } from "react";
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
import { OPEN_SETUP, DATA_EMPTY_TITLE, DATA_EMPTY_BODY } from "@/lib/uiText";

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
  const [expandedSession, setExpandedSession] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [download, setDownload] = useState({ busy: false, error: "" });
  const generation = useRef(0);
  useEffect(() => {
    if (!hasProtocol) return;
    const version = ++generation.current;
    setLoading(true);
    setLoadError(null);
    Promise.all([studyApi.status(studyId), studyApi.dataset(studyId)])
      .then(([s, d]) => {
        if (generation.current !== version) return;
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
    return () => {
      generation.current++;
    };
  }, [studyId, revision, hasProtocol]);
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
          <section className="flex flex-col gap-3 border-b border-border pb-5">
            <h2 className="type-subhead text-text">Download study records</h2>
            <p className="type-note text-text-muted">
              Data bundles include real captured rows, pilot tags and inclusion
              decisions. Synthetic rows are excluded. The design card records
              assumptions, instruments, tool versions and audit signals without
              rating validity.
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
                                {s.condition}
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
                              <CheckCircle2 className="size-3" aria-hidden />{" "}
                              complete
                            </>
                          ) : (
                            <>
                              <AlertTriangle className="size-3" aria-hidden />
                              {s.missingEvents > 0
                                ? `${s.missingEvents} event${s.missingEvents === 1 ? "" : "s"} missing`
                                : "in progress"}
                              {s.flagKinds.length > 0 &&
                                ` · ${s.flagKinds.join(", ")}`}
                            </>
                          )}
                        </p>
                      </button>
                      {isOpen && (
                        <div className="border-t border-border px-4 pb-4 pt-3">
                          <div className="mb-3 flex flex-wrap items-center gap-2 type-caption text-text-muted">
                            <span>task: {s.taskId || "not stamped"}</span>
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
              </div>
            )}
          </section>

          <ControlAudit
            studyId={studyId}
            sessions={sessions}
            role={role}
            onUpdated={() => setRevision((r) => r + 1)}
          />
          <div className="flex flex-col gap-stack">
            <section className="flex flex-col gap-stack">
              <h2 className="type-section text-text">
                Confirmatory metrics by condition
              </h2>
              <p className="type-note text-text-muted">
                Pilot sessions and researcher-excluded sessions are omitted from
                this comparison.
              </p>
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
