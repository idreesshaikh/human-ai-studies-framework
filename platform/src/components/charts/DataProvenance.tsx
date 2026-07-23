import { useState } from "react";
import {
  Radio,
  GitBranch,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  FlaskConical,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { MetricStrip } from "./MetricStrip";
import { studyApi, OfflineError, type MiningJob, type DatasetRow } from "@/lib/studyApi";

/* Deterministic synthetic rows for a rehearsal — NOT real data and never
 * persisted or sent to the server. A seeded LCG (no Math.random, matching the
 * charts' determinism) gives each condition a plausible-but-distinct spread so
 * the researcher can see the shape of their analysis before collecting
 * anything. Watermarked loudly wherever it renders. */
function syntheticRows(conditions: string[]): DatasetRow[] {
  const conds = conditions.length ? conditions : ["ai-assisted", "unassisted"];
  const rows: DatasetRow[] = [];
  let seed = 1337;
  const rand = () => {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    return seed / 0x7fffffff;
  };
  conds.forEach((condition, ci) => {
    const centre = 7 + ci * 2; // conditions differ so the plot isn't flat
    for (let i = 0; i < 12; i++) {
      const jitter = (rand() - 0.5) * 6;
      const cc = Math.max(1, Math.round(centre + jitter));
      rows.push({
        source: "synthetic",
        ts: "",
        sessionId: `synthetic-${condition}-${i}`,
        participantId: `S${ci}${i}`,
        condition,
        type: "metric",
        seq: null,
        flags: [],
        payload: {
          cognitive_complexity: cc,
          parameter_count: Math.max(0, Math.round(cc / 2 + (rand() - 0.5) * 2)),
          nesting_penalty: Math.max(0, Math.round(cc / 3 + (rand() - 0.5) * 2)),
        },
      });
    }
  });
  return rows;
}

/* The data-provenance decision (FR-CUR): before a study has data, where does
 * it come from? Two honest paths this platform actually supports —
 *  • collect it live (instrument real participant sessions), or
 *  • curate it from GitHub (mine PRs/commits into the same join-key schema).
 * The curate path runs a real mining job inline; if the study's protocol has
 * no sampling frame yet, the server says so plainly rather than pretending. */
export function DataProvenance({
  studyId,
  conditions,
}: {
  studyId: string;
  conditions: string[];
}) {
  const [job, setJob] = useState<MiningJob | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rehearsal, setRehearsal] = useState<DatasetRow[] | null>(null);

  async function startMining() {
    setBusy(true);
    setError(null);
    try {
      setJob(await studyApi.startMiningJob(studyId));
    } catch (e) {
      setError(
        e instanceof OfflineError
          ? "Start the middleware to run a mining job."
          : e instanceof Error
            ? e.message
            : "Couldn't start the mining job.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="text-sm font-medium text-text">Where does your data come from?</h2>
        <p className="mt-1 text-xs text-text-muted">
          A study needs data to analyse. Collect it live from instrumented
          sessions, or curate it from public GitHub activity — both land in the
          same join-key schema, so the analysis is identical.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="flex flex-col gap-2 rounded-card border border-border bg-surface p-4">
          <h3 className="flex items-center gap-2 text-sm font-medium text-text">
            <Radio className="size-4 text-accent" aria-hidden /> Collect it live
          </h3>
          <p className="flex-1 text-xs text-text-muted">
            Mint enrollment links in the Participants tab. Each participant pastes
            one into their editor and their real coding sessions stream in.
          </p>
          <span className="text-xs text-text-muted">→ Participants tab</span>
        </div>

        <div className="flex flex-col gap-2 rounded-card border border-border bg-surface p-4">
          <h3 className="flex items-center gap-2 text-sm font-medium text-text">
            <GitBranch className="size-4 text-accent" aria-hidden /> Curate from GitHub
          </h3>
          <p className="flex-1 text-xs text-text-muted">
            Mine PRs, commits, and reviews matching your protocol's sampling
            frame, pseudonymised into the same event schema.
          </p>
          <Button size="sm" variant="subtle" onClick={startMining} disabled={busy} className="self-start">
            {busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <GitBranch className="size-4" aria-hidden />}
            {busy ? "Mining…" : "Start a mining job"}
          </Button>
        </div>

        <div className="flex flex-col gap-2 rounded-card border border-border bg-surface p-4">
          <h3 className="flex items-center gap-2 text-sm font-medium text-text">
            <FlaskConical className="size-4 text-accent" aria-hidden /> Rehearse first
          </h3>
          <p className="flex-1 text-xs text-text-muted">
            No data yet? Generate a synthetic pilot to see the shape of your
            analysis before you collect anything. Clearly labelled, never saved.
          </p>
          <Button
            size="sm"
            variant="subtle"
            onClick={() => setRehearsal(syntheticRows(conditions))}
            className="self-start"
          >
            <FlaskConical className="size-4" aria-hidden /> Generate synthetic pilot
          </Button>
        </div>
      </div>

      {error && (
        <p className="flex items-start gap-2 rounded-input border border-border-strong bg-unsourced-soft px-3 py-2 text-xs text-text">
          <AlertTriangle className="size-4 shrink-0 text-unsourced" aria-hidden />
          {error}
        </p>
      )}

      {job && (
        <div className="rounded-card border border-border bg-surface p-4">
          <div className="flex items-center gap-2">
            {job.state === "gated" || job.state === "complete" ? (
              <CheckCircle2 className="size-4 text-grounded" aria-hidden />
            ) : (
              <Loader2 className="size-4 animate-spin text-accent" aria-hidden />
            )}
            <span className="text-sm font-medium text-text">
              Mining job {job.id.slice(0, 8)} · {job.state}
            </span>
          </div>
          {job.statusMessage && (
            <p className="mt-1 text-xs text-text-muted">{job.statusMessage}</p>
          )}
          {Object.keys(job.coverage).length > 0 && (
            <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
              {Object.entries(job.coverage).map(([k, v]) => (
                <div key={k} className="flex items-center gap-1">
                  <dt className="text-text-muted">{k}</dt>
                  <dd className="tabular font-medium text-text">{v}</dd>
                </div>
              ))}
            </dl>
          )}
          {job.firedHeuristics.length > 0 && (
            <p className="mt-2 text-xs text-text-muted">
              Validity flags: {job.firedHeuristics.join(", ")}
            </p>
          )}
        </div>
      )}

      {rehearsal && (
        <div className="rounded-card border-2 border-dashed border-unsourced bg-unsourced-soft/40 p-4">
          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-2 text-sm font-medium text-text">
              <FlaskConical className="size-4 text-unsourced" aria-hidden />
              Synthetic pilot — not real data
            </span>
            <button
              onClick={() => setRehearsal(null)}
              aria-label="Dismiss the synthetic pilot"
              className="text-text-muted hover:text-text"
            >
              <X className="size-4" aria-hidden />
            </button>
          </div>
          <p className="mt-1 text-xs text-text-muted">
            Generated to rehearse your analysis. These numbers are made up and
            are never saved or counted as results — collect real data above when
            you're ready.
          </p>
          <div className="mt-3">
            <MetricStrip rows={rehearsal} conditions={conditions} />
          </div>
        </div>
      )}
    </section>
  );
}
