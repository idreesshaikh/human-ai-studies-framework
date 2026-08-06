import { useState } from "react";
import { Radio, FlaskConical, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MetricStrip } from "./MetricStrip";
import { type DatasetRow } from "@/lib/studyApi";

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
 * it come from? Collect it live (instrument real participant sessions), or
 * rehearse with a synthetic pilot to see the shape of the analysis first. */
export function DataProvenance({ conditions }: { conditions: string[] }) {
  const [rehearsal, setRehearsal] = useState<DatasetRow[] | null>(null);

  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="type-subhead text-text">Where does your data come from?</h2>
        <p className="mt-1 text-xs text-text-muted">
          A study needs data to analyse. Collect it live from instrumented
          sessions, or rehearse with synthetic data first.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-2 rounded-card border border-border bg-surface p-4">
          <h3 className="type-subhead flex items-center gap-2 text-text">
            <Radio className="size-4 text-accent" aria-hidden /> Collect it live
          </h3>
          <p className="flex-1 text-xs text-text-muted">
            Mint enrollment links in the Participants tab. Each participant pastes
            one into their editor and their real coding sessions stream in.
          </p>
          <span className="text-xs text-text-muted">→ Participants tab</span>
        </div>

        <div className="flex flex-col gap-2 rounded-card border border-border bg-surface p-4">
          <h3 className="type-subhead flex items-center gap-2 text-text">
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

      {rehearsal && (
        <div className="rounded-card border-2 border-dashed border-unsourced bg-unsourced-soft/40 p-4">
          <div className="flex items-center justify-between gap-2">
            <span className="type-subhead flex items-center gap-2 text-text">
              <FlaskConical className="size-4 text-unsourced" aria-hidden />
              Synthetic pilot, not real data
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
            are never saved or counted as results; collect real data above when
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
