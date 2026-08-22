import { CheckCircle2, AlertTriangle, FlaskConical } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { DryRunPlan as Plan } from "@/lib/studyApi";

/* What the dry run found out.
 *
 * Storing synthetic events only proves the capture path works. This is the
 * other half: the study's own analysis plan, run over that synthetic data, so
 * a researcher learns whether the statistics their design prescribes can
 * actually be computed  -  before a single real participant sits down. It is the
 * one thing no amount of reading the protocol will tell them, and the step
 * they are most afraid of getting wrong.
 *
 * Each recipe's `summary` is rendered verbatim, never reformatted or trimmed.
 * The honesty lives in its exact wording: recipes state their own caveats
 * ("small n: hypothesis-generating only, not confirmatory"), their own schema
 * gaps, and when a comparison could not be made at all. Paraphrasing that into
 * a tidier sentence, or reducing it to a green tick, would strip precisely the
 * part a researcher has to read. Nothing here animates  -  this is a result. */
export function DryRunPlan({ plan }: { plan: Plan }) {
  if (plan.note) {
    return (
      <p className="type-caption text-text-muted" data-agent="dry-run-plan">
        {plan.note}
      </p>
    );
  }

  const ran = plan.ran.length;
  const failures = Object.entries(plan.errors ?? {});
  /* "Every prescribed test computed" is the claim worth making plainly, and
   * only when it is true of the whole plan  -  a blocked recipe or a raised
   * error both make it false, so both must clear before the calm wording. */
  const complete = ran === plan.planned && plan.blocked.length === 0 && !failures.length;

  return (
    <section className="flex flex-col gap-3" data-agent="dry-run-plan">
      <div>
        <h3 className="type-subhead flex items-center gap-2 text-text">
          <FlaskConical className="size-4 text-text-muted" aria-hidden />
          The statistics your design prescribes
        </h3>
        <p className="mt-1 type-caption text-text-muted">
          {complete ? (
            <>
              All {plan.planned} of the tests this protocol calls for ran
              against the synthetic data. The analysis plan is satisfiable:
              when real sessions arrive, these are the tests that execute, on
              this data shape, with no further decisions to make.
            </>
          ) : (
            <>
              {ran} of {plan.planned} prescribed{" "}
              {plan.planned === 1 ? "test" : "tests"} ran. The rest are listed
              below with what they were missing  -  better to learn it here than
              after collecting from real participants.
            </>
          )}{" "}
          These numbers come from simulated data and are never findings.
        </p>
      </div>

      {plan.results.length > 0 && (
        <ul className="flex flex-col gap-2">
          {plan.results.map((r) => (
            <li
              key={r.recipeId}
              data-agent="dry-run-recipe"
              data-agent-ref={r.recipeId}
              className="rounded-plate border border-border bg-surface p-3"
            >
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                <CheckCircle2
                  className="size-4 shrink-0 translate-y-0.5 text-ok"
                  aria-hidden
                />
                <span className="type-label text-text">{r.title}</span>
                {r.rqs.map((rq) => (
                  <Badge key={rq} variant="outline">
                    {rq}
                  </Badge>
                ))}
              </div>
              {/* Verbatim, and wrapped rather than clipped: the caveats live
                * at the end of these sentences. */}
              <p className="mt-1.5 type-caption leading-relaxed text-text-muted">
                {r.summary}
              </p>
            </li>
          ))}
        </ul>
      )}

      {plan.blocked.length > 0 && (
        <div className="rounded-plate border border-dashed border-unsourced bg-well p-3">
          <p className="type-label flex items-center gap-2 text-text">
            <AlertTriangle className="size-4 text-text-muted" aria-hidden />
            Not computable on this data
          </p>
          <ul className="mt-1.5 flex flex-col gap-1">
            {plan.blocked.map((b) => (
              <li key={`${b.rq}-${b.recipeId}`} className="type-caption text-text-muted">
                <span className="text-text">{b.recipeId}</span> ({b.rq})  - {" "}
                {b.reason}
              </li>
            ))}
          </ul>
          <p className="mt-1.5 type-caption text-text-muted">
            Each line is a gap between what the plan asks for and what the
            capture config collects. Both are yours to change.
          </p>
        </div>
      )}

      {failures.length > 0 && (
        <div className="rounded-plate border border-dashed border-critical bg-well p-3">
          <p className="type-label text-text">Recipes that raised an error</p>
          <ul className="mt-1.5 flex flex-col gap-1">
            {failures.map(([id, message]) => (
              <li key={id} className="type-caption text-text-muted">
                <span className="text-text">{id}</span>  -  {message}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
