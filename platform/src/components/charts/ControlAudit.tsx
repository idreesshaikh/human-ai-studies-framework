import { useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Field } from "@/components/ui/field";
import { Pagination, paginate } from "@/components/ui/pagination";
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
import { conditionLabel } from "@/lib/uiText";

const STATUS = {
  "no-evidence": "No AI signals captured",
  "evidence-of-ai-use": "AI signals captured",
  "cannot-assess": "Capture needs review",
};
const SIGNALS: Record<string, string> = {
  ai_suggestion: "AI suggestions", ai_edit_heuristic: "Possible AI edits",
  agent_turn: "Agent turns", tool_call: "Tool calls",
  clipboard_paste: "Clipboard pastes", paste_edit: "Paste edits",
};

export function ControlAudit({ studyId, sessions, role, onUpdated, synthetic = false }: {
  studyId: string; sessions: SessionStatus[]; role?: Role | null;
  onUpdated: () => void; synthetic?: boolean;
}) {
  const [audit, setAudit] = useState<AuditResult | null>(null);
  const [decisions, setDecisions] = useState<Record<string, SessionDecision>>({});
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState("review");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);
  const generation = useRef(0);
  useEffect(() => {
    const version = ++generation.current;
    setError(null);
    Promise.all([plannerApi.audit(studyId, synthetic), plannerApi.load(studyId)])
      .then(([a, p]) => {
        if (generation.current !== version) return;
        setAudit(a);
        setDecisions(p.decisions);
      })
      .catch((e) => {
        if (generation.current === version)
          setError(e instanceof Error ? e.message : "The audit could not be loaded.");
      });
    return () => { generation.current++; };
  }, [studyId, sessions, synthetic]);
  const assessments = new Map(audit?.sessions.map((s) => [s.sessionId, s]));
  const filtered = sessions.filter((session) => {
    const assessment = assessments.get(session.sessionId);
    if (view === "review" && (!assessment || assessment.status === "no-evidence")) return false;
    if (view === "control" && !assessment) return false;
    return `${session.participantId} ${session.condition} ${conditionLabel(session.condition)} ${session.sessionId}`.toLowerCase().includes(query.trim().toLowerCase());
  });
  const slice = paginate(filtered, page);
  const reset = () => { setPage(0); setExpanded(null); };
  return (
    <section className="flex min-w-0 flex-col gap-3 border-t border-border pt-5" aria-label="Session review">
      <h2 className="type-section text-text">Session review</h2>
      <p className="max-w-reading type-note text-text-muted">
        Review AI signals in control conditions and record inclusion decisions.
        Missing signals cannot rule out AI use outside the captured tools.
      </p>
      {synthetic && <p className="type-note text-text-muted">Example sessions only. Decisions are disabled.</p>}
      {error && <p className="type-note text-critical" role="alert">{error}</p>}
      {!audit && !error && <p className="type-note text-text-muted" role="status">Loading session review…</p>}
      {audit && !error && (
        <>
          <p className="type-note text-text-muted">
            {audit.sessions.length} control sessions · {audit.sessions.filter((s) => s.status === "evidence-of-ai-use").length} with AI signals · {audit.sessions.filter((s) => s.status === "cannot-assess").length} with incomplete capture
          </p>
          <div className="grid grid-cols-1 items-end gap-3 sm:grid-cols-2">
            <Field label="Show sessions">
              <Select value={view} options={[
                { value: "review", label: "Needs review" },
                { value: "control", label: "Control conditions" },
                { value: "all", label: "All sessions" },
              ]} onValueChange={(value) => { setView(value); reset(); }} />
            </Field>
            <Field label="Search review sessions">
              <Input type="search" value={query} placeholder="Participant, condition or session" onChange={(e) => { setQuery(e.target.value); reset(); }} />
            </Field>
          </div>
          {slice.total === 0 ? (
            <p className="py-3 type-note text-text-muted" role="status">
              {query.trim() ? "No matching sessions. Try another search." : !audit.sessions.length ? "No control-condition data to assess. Check the conditions in Setup, or choose All sessions to review decisions." : view === "review" ? "No control sessions flagged for review. Choose All sessions to review decisions." : "No sessions in this view."}
            </p>
          ) : (
            <div className="divide-y divide-border border-y border-border">
              {slice.rows.map((session) => {
                const assessment = assessments.get(session.sessionId);
                const open = expanded === session.sessionId;
                return (
                  <div key={session.sessionId}>
                    <button type="button" className="grid w-full grid-cols-1 gap-1 rounded-control px-3 py-3 text-left hover:bg-zone-9 sm:grid-cols-2 sm:items-center sm:gap-3" aria-expanded={open} onClick={() => setExpanded(open ? null : session.sessionId)}>
                      <span className="flex min-w-0 items-center gap-2 type-body text-text">
                        {open ? <ChevronDown className="size-4 shrink-0" aria-hidden /> : <ChevronRight className="size-4 shrink-0" aria-hidden />}
                        <span className="font-medium">{session.participantId}</span>
                        <span className="truncate text-text-muted">{conditionLabel(session.condition)}</span>
                      </span>
                      <span className="pl-6 type-note text-text sm:pl-0">{assessment ? STATUS[assessment.status] : "Not a control condition"}</span>
                    </button>
                    {open && (
                      <div className="flex min-w-0 flex-col gap-2 px-3 pb-4 type-note text-text-muted">
                        <p className="break-all">Session: {session.sessionId}</p>
                        {assessment && <>
                          <ul className="list-disc space-y-1 pl-5">{assessment.reasons.filter((reason) => !/^Captured \d+ (ai_suggestion|agent_turn|tool_call) event\(s\)\.$/.test(reason)).map((reason) => <li key={reason}>{reason}</li>)}</ul>
                          <p>{Object.entries(assessment.counts).map(([name, count]) => `${SIGNALS[name] ?? name}: ${count}`).join(" · ") || "No signal counts recorded."}</p>
                        </>}
                        {!synthetic && <SessionControls
                          key={`${session.sessionId}:${decisions[session.sessionId]?.updatedAt ?? ""}`}
                          studyId={studyId} sessionId={session.sessionId}
                          decision={decisions[session.sessionId]} editable={hasRole(role, "contribute")}
                          onSaved={(decision) => { setDecisions((prior) => ({ ...prior, [session.sessionId]: decision })); onUpdated(); }}
                        />}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          <Pagination {...slice} label="Audit" onChange={(next) => { setPage(next); setExpanded(null); }} />
          <details className="type-note text-text-muted">
            <summary className="cursor-pointer rounded-control py-2 text-text">Capture limits</summary>
            <p className="mt-2">Accuracy: {audit.accuracy}</p>
            <ul className="mt-2 list-disc space-y-1 pl-5">{audit.blindSpots.map((spot) => <li key={spot}>{spot}</li>)}</ul>
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
          <span className="type-label text-text">Include in analysis</span>
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
