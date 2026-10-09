import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { hasRole, type Role } from "@/lib/capabilities";
import {
  plannerApi,
  type AuditResult,
  type SessionDecision,
} from "@/lib/plannerApi";
import type { SessionStatus } from "@/lib/studyApi";

const STATUS = {
  "no-evidence": "No captured evidence",
  "evidence-of-ai-use": "Evidence of AI use",
  "cannot-assess": "Cannot assess",
};
export function ControlAudit({
  studyId,
  sessions,
  role,
  onUpdated,
}: {
  studyId: string;
  sessions: SessionStatus[];
  role?: Role | null;
  onUpdated: () => void;
}) {
  const [audit, setAudit] = useState<AuditResult | null>(null);
  const [decisions, setDecisions] = useState<Record<string, SessionDecision>>(
    {},
  );
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);
  useEffect(() => {
    const version = ++generation.current;
    Promise.all([plannerApi.audit(studyId), plannerApi.load(studyId)])
      .then(([a, p]) => {
        if (generation.current === version) {
          setAudit(a);
          setDecisions(p.decisions);
          setError(null);
        }
      })
      .catch((e) => {
        if (generation.current === version)
          setError(
            e instanceof Error ? e.message : "The audit could not be loaded.",
          );
      });
    return () => {
      generation.current++;
    };
  }, [studyId, sessions]);
  return (
    <section className="flex flex-col gap-3 border-t border-border pt-5">
      <h2 className="type-section text-text">
        Control-arm audit and session decisions
      </h2>
      <p className="max-w-reading type-note text-text-muted">
        The audit reports captured signals. No captured evidence is never proof
        of no AI use. Inclusion remains your decision.
      </p>
      {error && (
        <p className="type-note text-critical" role="alert">
          {error}
        </p>
      )}
      {audit && (
        <>
          <p className="type-note text-text-muted">{audit.accuracy}</p>
          {!audit.sessions.length && (
            <p className="type-note text-text-muted">
              No real captured sessions in declared control conditions. Set
              controlConditions in the protocol to name the arms to audit.
            </p>
          )}
          <div className="flex flex-col gap-4">
            {sessions.map((session) => {
              const assessment = audit.sessions.find(
                (s) => s.sessionId === session.sessionId,
              );
              return (
                <div
                  key={session.sessionId}
                  className="border-b border-border pb-4"
                >
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <h3 className="type-label text-text">
                      {session.participantId} · {session.condition}
                    </h3>
                    <p className="type-note text-text">
                      {assessment
                        ? STATUS[assessment.status]
                        : "Outside declared control arms"}
                    </p>
                  </div>
                  <p className="mt-1 break-all type-caption text-text-muted">
                    {session.sessionId}
                  </p>
                  {assessment && (
                    <>
                      <ul className="my-2 flex list-disc flex-col gap-1 pl-5 type-note text-text-muted">
                        {assessment.reasons.map((reason) => (
                          <li key={reason}>{reason}</li>
                        ))}
                      </ul>
                      <p className="type-caption text-text-muted">
                        {Object.entries(assessment.counts)
                          .map(([name, count]) => `${name}: ${count}`)
                          .join(" · ") || "No signal counts recorded"}
                      </p>
                    </>
                  )}
                  <SessionControls
                    key={`${session.sessionId}:${decisions[session.sessionId]?.updatedAt ?? ""}`}
                    studyId={studyId}
                    sessionId={session.sessionId}
                    decision={decisions[session.sessionId]}
                    editable={hasRole(role, "contribute")}
                    onSaved={(decision) => {
                      setDecisions((p) => ({
                        ...p,
                        [session.sessionId]: decision,
                      }));
                      onUpdated();
                    }}
                  />
                </div>
              );
            })}
          </div>
          <details>
            <summary className="cursor-pointer type-control text-text-muted">
              Known capture blind spots
            </summary>
            <ul className="mt-2 flex list-disc flex-col gap-1 pl-5 type-note text-text-muted">
              {audit.blindSpots.map((spot) => (
                <li key={spot}>{spot}</li>
              ))}
            </ul>
          </details>
        </>
      )}
    </section>
  );
}
function SessionControls({
  studyId,
  sessionId,
  decision,
  editable,
  onSaved,
}: {
  studyId: string;
  sessionId: string;
  decision?: SessionDecision;
  editable: boolean;
  onSaved: (d: SessionDecision) => void;
}) {
  const [pilot, setPilot] = useState(decision?.pilot ?? false);
  const [inclusion, setInclusion] = useState(decision?.decision ?? "undecided");
  const [reason, setReason] = useState(decision?.reason ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <form
      className="mt-3 flex flex-col gap-3"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError(null);
        try {
          onSaved(
            await plannerApi.annotate(studyId, sessionId, {
              pilot,
              decision: inclusion,
              reason,
            }),
          );
        } catch (e) {
          setError(
            e instanceof Error
              ? e.message
              : "Could not save the session decision.",
          );
        } finally {
          setBusy(false);
        }
      }}
    >
      <div className="flex flex-wrap items-end gap-3">
        <Checkbox
          label="Pilot session"
          checked={pilot}
          disabled={!editable || busy}
          onChange={(e) => setPilot(e.target.checked)}
        />
        <label className="flex flex-col gap-1">
          <span className="type-label text-text">Confirmatory inclusion</span>
          <Select
            value={inclusion}
            disabled={!editable || busy}
            options={[
              { value: "undecided", label: "Undecided" },
              { value: "include", label: "Include" },
              { value: "exclude", label: "Exclude" },
            ]}
            onValueChange={(v) => setInclusion(v as typeof inclusion)}
          />
        </label>
        <label className="flex min-w-48 flex-1 flex-col gap-1">
          <span className="type-label text-text">
            Reason for the decision or pilot tag
          </span>
          <Input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            required
            maxLength={4000}
            disabled={!editable || busy}
          />
        </label>
        {editable && (
          <Button type="submit" size="sm" variant="outline" disabled={busy}>
            {busy ? "Saving…" : "Save decision"}
          </Button>
        )}
      </div>
      <p className="type-note text-text-muted">
        {pilot
          ? "Pilot outcomes are excluded from confirmatory analysis."
          : "Pilot status is set by the researcher."}{" "}
        {decision &&
          `Last recorded by ${decision.decidedBy} on ${decision.updatedAt}.`}
      </p>
      {error && (
        <p className="type-note text-critical" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}
