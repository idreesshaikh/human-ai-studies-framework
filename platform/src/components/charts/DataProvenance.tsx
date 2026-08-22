import { useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MetricStrip } from "./MetricStrip";
import { type DatasetRow } from "@/lib/studyApi";

/* Deterministic synthetic rows for a rehearsal  -  NOT real data and never
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
 * it come from? Collect it live (instrument real participant sessions), or
 * rehearse with a synthetic dry run to see the shape of the analysis first.
 * The dry run goes through the real capture path on the middleware; when no
 * middleware is running, it falls back to the client-side rows below, drawn
 * the same way and watermarked the same way. */
export function DataProvenance({
  conditions,
  onDryRun,
  dryRunBusy = false,
  showClientRehearsal = false,
}: {
  conditions: string[];
  onDryRun: () => void;
  dryRunBusy?: boolean;
  showClientRehearsal?: boolean;
}) {
  const [rehearsal, setRehearsal] = useState<DatasetRow[] | null>(null);
  const offline = showClientRehearsal && rehearsal === null;

  const rehearse = () => {
    if (offline) setRehearsal(syntheticRows(conditions));
    else onDryRun();
  };

  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="type-subhead text-text">Where does your data come from?</h2>
        <p className="mt-1 type-caption text-text-muted">
          A study needs data to analyse. Collect it live from instrumented
          sessions, or rehearse with synthetic data first.
        </p>
      </div>

      {/* A fork, drawn as a fork: two paths on ONE plate, divided by the rule
        * between them. It was two cards of icon + heading + text side by side,
        * which is the generic scaffold the craft floor names as the lazy
        * container: the icons carried no information the headings did not, and
        * two framed boxes implied two unrelated things rather than one
        * decision with two answers.
        *
        * Rehearsing is the live action here (collecting happens on another
        * tab), so it holds the one fill and its path is named second: the eye
        * lands on the action last, after reading what the choice is. */}
      <div className="grid overflow-hidden rounded-plate border border-border bg-surface sm:grid-cols-2">
        <div className="flex flex-col gap-1.5 border-b border-border p-4 sm:border-b-0 sm:border-r">
          <h3 className="type-label text-text">Collect it live</h3>
          <p className="type-caption flex-1 text-text-muted">
            Mint enrollment links in the Participants tab. Each participant
            pastes one into their editor and their real coding sessions stream
            in.
          </p>
          <span className="type-caption text-text-muted">
            Next: the Participants tab
          </span>
        </div>

        <div className="flex flex-col items-start gap-1.5 p-4">
          <h3 className="type-label text-text">Rehearse first</h3>
          <p className="type-caption flex-1 text-text-muted">
            No data yet? Run a synthetic dry run: simulated participants
            through the real capture path, so you can see the shape of your
            analysis before collecting anything. Clearly labelled, for
            rehearsal only.
          </p>
          <Button size="sm" onClick={rehearse} className="mt-1" disabled={dryRunBusy}>
            {dryRunBusy
              ? "Running dry run…"
              : offline
                ? "Generate synthetic pilot"
                : "Run a dry run (10 simulated participants)"}
          </Button>
          {offline && (
            <span className="type-caption text-text-muted">
              Middleware is offline. Showing an in-browser sample instead.
            </span>
          )}
        </div>
      </div>

      {rehearsal && (
        <div className="rounded-plate border border-dashed border-unsourced bg-well p-4">
          <div className="flex items-center justify-between gap-2">
            <span className="type-label flex items-center gap-2 text-text">
              <span aria-hidden className="mark-unsourced" />
              In-browser rehearsal, not real data
            </span>
            <button
              onClick={() => setRehearsal(null)}
              aria-label="Dismiss the rehearsal"
              className="rounded-control text-text-muted transition-colors duration-fast hover:text-text"
            >
              <X className="size-4" aria-hidden />
            </button>
          </div>
          <p className="mt-1 type-caption text-text-muted">
            The middleware is offline, so this rehearsal was generated in the
            browser. These numbers are made up and are never saved or counted
            as results; start the middleware to run a real dry run through the
            capture path.
          </p>
          <div className="mt-3">
            <MetricStrip rows={rehearsal} conditions={conditions} />
          </div>
        </div>
      )}
    </section>
  );
}
