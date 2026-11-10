import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { studyApi, type OutcomeCheckReport } from "@/lib/studyApi";

const STATUS = {
  observed: "Inputs observed",
  review: "Review coverage",
  incomplete: "Incomplete capture",
  missing: "Inputs missing",
  "not-observed": "No sessions checked",
  unverified: "Custom check needed",
  configuration: "Configuration needs attention",
};

export function OutcomeChecks({ studyId, synthetic, onChecked }: { studyId: string; synthetic: boolean; onChecked: () => void }) {
  const [report, setReport] = useState<OutcomeCheckReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef(0);
  useEffect(() => {
    generation.current++;
    setReport(null);
    setError("");
    setBusy(false);
    return () => { generation.current++; };
  }, [studyId, synthetic]);

  async function check() {
    const version = ++generation.current;
    setBusy(true);
    setError("");
    setReport(null);
    try {
      const result = await studyApi.outcomeChecks(studyId, synthetic);
      if (generation.current === version) {
        setReport(result);
        onChecked();
      }
    } catch (e) {
      if (generation.current === version)
        setError(e instanceof Error ? e.message : "Could not check outcome capture.");
    } finally {
      if (generation.current === version) setBusy(false);
    }
  }

  function download() {
    if (!report) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
    try {
      const link = document.createElement("a");
      link.href = url;
      link.download = `${studyId}-outcome-checks.json`;
      link.click();
    } finally { URL.revokeObjectURL(url); }
  }

  return (
    <section className="flex min-w-0 flex-col gap-3 break-words border-b border-border pb-5" aria-label="Outcome capture checks">
      <h2 className="type-subhead text-text">Check outcome capture</h2>
      <p className="type-note text-text-muted">
        Check a rehearsal for the instrument, fields and condition coverage each
        declared outcome needs. This checks captured inputs, not study validity.
      </p>
      <div className="flex flex-wrap gap-3">
        <Button size="sm" variant="outline" disabled={busy} onClick={() => void check()}>
          {busy ? "Checking capture…" : report ? "Check again" : "Check captured inputs"}
        </Button>
        {report && <Button size="sm" variant="outline" onClick={download}>Download checks (.json)</Button>}
      </div>
      {busy && <p role="status" className="type-note text-text-muted">Checking the recorded protocol and captured sessions…</p>}
      {error && <p role="alert" className="type-note text-critical">{error}</p>}
      {report && (
        <>
          <p role="status" className="type-note text-text-muted">
            {report.sessionUnits} {report.synthetic ? "synthetic " : ""}sessions checked, including pilots.
            {report.outcomes.length === 0 && " No outcomes are declared. Add measures in Setup."}
          </p>
          <div className="divide-y divide-border">
            {report.outcomes.map((outcome, index) => (
              <details key={`${outcome.measureId}-${index}`} className="py-3">
                <summary className="cursor-pointer rounded-control type-body text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">
                  <span className="font-medium">{outcome.outcome}</span>
                  <span className="ml-2 type-note text-text-muted">{STATUS[outcome.status]}</span>
                </summary>
                <div className="mt-3 flex flex-col gap-2 type-note text-text-muted">
                  <p>{outcome.instrument ?? "No typed instrument"} · {outcome.fields.join(", ") || "No typed fields"}</p>
                  <p>Recipe: {outcome.recipe ?? "Not declared"}. {outcome.observedUnits === null ? "Coverage is unverified." : `${outcome.observedUnits} of ${outcome.checkedUnits} session units have observed inputs.`}</p>
                  <p>{Object.entries(outcome.participantsByCondition).map(([condition, count]) => `${condition}: ${count} participants`).join(" · ")}{outcome.pairedParticipants !== null && ` · ${outcome.pairedParticipants} complete participant pairs`}</p>
                  {outcome.issues.map((issue) => (
                    <p key={issue.code}>
                      <span className="text-text">{issue.message}</span> {issue.action}
                      {issue.units > 0 && ` Affected sessions: ${issue.units}.`}
                      {issue.sessionIds.length > 0 && ` Examples: ${issue.sessionIds.join(", ")}.`}
                    </p>
                  ))}
                </div>
              </details>
            ))}
          </div>
          <details className="type-note text-text-muted">
            <summary className="cursor-pointer rounded-control focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">Scope and provenance</summary>
            <div className="mt-3 flex flex-col gap-2">
              <p>{report.scope}</p>
              {report.limitations.map((line) => <p key={line}>{line}</p>)}
              <p className="break-all">Protocol: <code>{report.protocolHash}</code></p>
              <p className="break-all">Captured data: <code>{report.dataHash}</code></p>
            </div>
          </details>
        </>
      )}
    </section>
  );
}
