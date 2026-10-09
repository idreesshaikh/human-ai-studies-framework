import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Surface } from "@/components/shell/Surface";
import { EmptyState } from "@/components/shell/EmptyState";
import { OPEN_SETUP, PLAN_EMPTY_TITLE, PLAN_EMPTY_BODY } from "@/lib/uiText";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { hasRole, type Role } from "@/lib/capabilities";
import {
  plannerApi,
  type Lineage,
  type PlanInputs,
  type PlanResult,
  type PlannerProtocol,
  type TypedMeasure,
} from "@/lib/plannerApi";

const DEFAULTS: PlanInputs = {
  design: "between-subjects",
  test: "mann-whitney",
  distribution: "normal",
  effect: 0.5,
  sd: 1,
  alpha: 0.05,
  target_power: 0.8,
  dropout: 0,
  covariate_correlation: 0,
  period_effect: 0,
  order_effect: 0,
  counterbalanced: true,
  planned_n: 40,
  max_n: 400,
  simulations: 1000,
  seed: 20261007,
  ordinal_levels: 7,
};
const LABELS: Record<string, string> = {
  "mann-whitney": "Mann–Whitney U",
  wilcoxon: "Wilcoxon signed-rank",
  "two-sample-t": "Independent t-test / ANCOVA",
  "paired-t": "Paired t-test",
};
function testsFor(protocol: PlannerProtocol, measure?: TypedMeasure) {
  const recipes = measure
    ? [measure.analysisRecipe]
    : protocol.analysisPlan.flatMap((p) => p.recipes);
  const paired = protocol.participants.design === "within-subjects";
  const tests: string[] = [];
  if (recipes.includes("mean-comparison"))
    tests.push(paired ? "paired-t" : "two-sample-t");
  if (
    recipes.includes("typed-measures") ||
    recipes.includes(
      paired ? "paired-nonparametric" : "two-group-nonparametric",
    )
  )
    tests.push(paired ? "wilcoxon" : "mann-whitney");
  return tests;
}
const percent = (n: number) => `${(n * 100).toFixed(1)}%`;

export function PowerPanel({
  studyId,
  active = true,
  hasProtocol,
  role,
}: {
  studyId: string;
  active?: boolean;
  hasProtocol: boolean;
  role?: Role | null;
}) {
  const [protocol, setProtocol] = useState<PlannerProtocol | null>(null);
  const [inputs, setInputs] = useState<PlanInputs>(DEFAULTS);
  const [result, setResult] = useState<PlanResult | null>(null);
  const [lineage, setLineage] = useState<Lineage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);
  const canEdit = hasRole(role, "contribute");
  const wasActive = useRef(false);

  useEffect(() => {
    if (!active && wasActive.current) {
      wasActive.current = false;
      return;
    }
    if (!active || !hasProtocol) return;
    wasActive.current = true;
    const version = ++generation.current;
    setLoading(true);
    setBusy(false);
    setError(null);
    plannerApi
      .load(studyId)
      .then((doc) => {
        if (version !== generation.current) return;
        setProtocol(doc.protocol);
        setResult(doc.plan);
        const measures =
          doc.protocol.measures?.filter(
            (m): m is TypedMeasure => typeof m === "object",
          ) ?? [];
        const first =
          measures.find((m) => testsFor(doc.protocol, m).length) ?? measures[0];
        const selected =
          measures.find((m) => m.id === doc.plan?.measureId) ?? first;
        const allowed = testsFor(doc.protocol, selected);
        const prior = doc.plan?.inputs;
        setInputs({
          ...(prior ?? DEFAULTS),
          design: doc.protocol.participants.design,
          counterbalanced: doc.protocol.participants.counterbalanced,
          planned_n:
            prior?.planned_n ?? Math.max(4, doc.protocol.participants.planned),
          test:
            prior && allowed.includes(prior.test)
              ? prior.test
              : (allowed[0] ?? ""),
          measure_id: selected?.id,
          distribution:
            prior && doc.plan?.measureId === selected?.id
              ? prior.distribution
              : selected?.analysisScale === "log"
                ? "log-normal"
                : "normal",
        });
      })
      .catch((e) => {
        if (version === generation.current)
          setError(
            e instanceof Error
              ? e.message
              : "Could not load the recorded plan.",
          );
      })
      .finally(() => {
        if (version === generation.current) setLoading(false);
      });
    return () => {
      generation.current++;
    };
  }, [studyId, active, hasProtocol]);

  const measures =
    protocol?.measures?.filter(
      (m): m is TypedMeasure => typeof m === "object",
    ) ?? [];
  const measure = measures.find((m) => m.id === inputs.measure_id);
  const tests = protocol ? testsFor(protocol, measure) : [];
  const paired = inputs.design === "within-subjects";
  const simulation = !inputs.test.endsWith("-t");
  const dirty =
    result &&
    ((result.measureId ?? null) !== (inputs.measure_id ?? null) ||
      Object.entries(result.inputs).some(
        ([key, value]) => inputs[key as keyof PlanInputs] !== value,
      ));
  const set = <K extends keyof PlanInputs>(key: K, value: PlanInputs[K]) =>
    setInputs((p) => ({ ...p, [key]: value }));
  const calculate = async (pilot: boolean) => {
    const version = generation.current;
    setBusy(true);
    setError(null);
    try {
      const doc = await (pilot
        ? plannerApi.pilot(studyId, inputs)
        : plannerApi.calculate(studyId, inputs));
      if (version === generation.current) {
        setResult(doc);
        setInputs({ ...doc.inputs, measure_id: doc.measureId });
      }
    } catch (e) {
      if (version === generation.current)
        setError(
          e instanceof Error ? e.message : "The plan could not be calculated.",
        );
    } finally {
      if (version === generation.current) setBusy(false);
    }
  };
  const number = (
    key: keyof PlanInputs,
    label: string,
    min: number,
    max: number,
    step: number | string,
    hint?: string,
  ) => (
    <label className="flex min-w-0 flex-col gap-1" key={key}>
      <span className="type-label text-text">{label}</span>
      <Input
        type="number"
        value={Number.isFinite(Number(inputs[key])) ? String(inputs[key]) : ""}
        min={min}
        max={max}
        step={step}
        required
        disabled={!canEdit || busy}
        onChange={(e) =>
          set(key, e.target.value === "" ? NaN : Number(e.target.value))
        }
      />
      {hint && <span className="type-note text-text-muted">{hint}</span>}
    </label>
  );
  if (!hasProtocol)
    return (
      <Surface measure="work" label="Planning">
        <h2 className="type-section text-text">{PLAN_EMPTY_TITLE}</h2>
        <EmptyState line={PLAN_EMPTY_BODY} action={
          <Button asChild size="sm">
            <Link to={{ search: "?tab=conversation" }}>{OPEN_SETUP}</Link>
          </Button>
        } />
      </Surface>
    );
  return (
    <Surface measure="work" label="Planning" className="bg-surface">
      <section className="flex flex-col gap-5">
        <div className="flex flex-col gap-2">
          <h2 className="type-section text-text">
            Plan participant recruitment
          </h2>
          <p className="max-w-reading type-body text-text-muted">
            Estimate power for the analysis in your protocol. A plan based on
            assumptions is a hypothesis; it is not a study finding.
          </p>
        </div>
        {loading && (
          <p className="type-body text-text-muted" role="status">
            Loading the recorded protocol and plan…
          </p>
        )}
        {error && (
          <p className="type-body text-critical" role="alert">
            {error}
          </p>
        )}
        {!loading && !protocol && (
          <Button variant="outline" asChild>
            <Link to="?tab=conversation">Open Setup to record a protocol</Link>
          </Button>
        )}
        {!loading && protocol && (
          <>
            <p className="type-note text-text-muted">
              Recorded design:{" "}
              <span className="text-text">{protocol.participants.design}</span>,{" "}
              {protocol.conditions.join(" / ")}.{" "}
              {protocol.participants.counterbalanced
                ? "Counterbalanced order."
                : "Fixed order."}{" "}
              <Link className="text-accent underline" to="?tab=conversation">
                Change the design in Setup
              </Link>
            </p>
            {!canEdit && (
              <p className="type-note text-text-muted">
                You can read saved plans. A project member can calculate and
                save a new plan.
              </p>
            )}
            <form
              className="flex flex-col gap-5"
              onSubmit={(e) => {
                e.preventDefault();
                void calculate(false);
              }}
            >
              <fieldset
                disabled={!canEdit || busy}
                className="grid min-w-0 gap-5 sm:grid-cols-2 lg:grid-cols-3"
              >
                {measures.length > 0 && (
                  <label className="flex flex-col gap-1">
                    <span className="type-label text-text">
                      Outcome measure
                    </span>
                    <Select
                      value={inputs.measure_id ?? ""}
                      options={measures.map((m) => ({
                        value: m.id,
                        label: m.construct,
                      }))}
                      onValueChange={(id) => {
                        const m = measures.find((v) => v.id === id);
                        setInputs((p) => ({
                          ...p,
                          measure_id: id,
                          test: testsFor(protocol, m)[0] ?? "",
                          distribution:
                            m?.analysisScale === "log"
                              ? "log-normal"
                              : "normal",
                        }));
                      }}
                    />
                    <span className="type-note text-text-muted">
                      {measure?.fields.join(", ")}
                    </span>
                  </label>
                )}
                <label className="flex flex-col gap-1">
                  <span className="type-label text-text">Planned test</span>
                  <Select
                    value={inputs.test}
                    options={tests.map((t) => ({ value: t, label: LABELS[t] }))}
                    onValueChange={(t) => set("test", t)}
                  />
                  <span className="type-note text-text-muted">
                    {measure?.analysisRecipe ??
                      "Uses the recorded analysis plan."}
                  </span>
                </label>
                <label className="flex flex-col gap-1">
                  <span className="type-label text-text">
                    Outcome distribution
                  </span>
                  <Select
                    value={inputs.distribution}
                    options={[
                      { value: "normal", label: "Normal" },
                      {
                        value: "log-normal",
                        label: "Log-normal (completion times)",
                      },
                      { value: "ordinal", label: "Ordinal (Likert ratings)" },
                    ]}
                    onValueChange={(v) => set("distribution", v)}
                  />
                </label>
                {number(
                  "effect",
                  "Effect to detect",
                  0.0001,
                  100000000,
                  "any",
                  inputs.distribution === "ordinal"
                    ? "Latent normal shift in SD units."
                    : inputs.distribution === "log-normal"
                      ? "Difference on the log scale."
                      : "Difference in outcome units.",
                )}
                {number(
                  "sd",
                  paired ? "SD of participant differences" : "Outcome SD",
                  0.0001,
                  100000000,
                  "any",
                  inputs.distribution === "log-normal"
                    ? "SD on the log scale."
                    : inputs.distribution === "ordinal"
                      ? "Set to 1 for latent standardized effects."
                      : "Use the same units as the effect.",
                )}
                {number(
                  "planned_n",
                  "Planned complete participants (total)",
                  4,
                  1000,
                  1,
                )}
                {number("alpha", "Two-sided alpha", 0.001, 0.5, 0.001)}
                {number("target_power", "Target power", 0.01, 0.99, 0.01)}
                {number(
                  "dropout",
                  "Expected dropout (fraction)",
                  0,
                  0.95,
                  0.01,
                  "0.10 means 10% dropout.",
                )}
              </fieldset>
              <details className="border-t border-border pt-3">
                <summary className="cursor-pointer type-control text-text">
                  Range, covariates and period assumptions
                </summary>
                <fieldset
                  disabled={!canEdit || busy}
                  className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-3"
                >
                  {number("max_n", "Maximum total n to explore", 4, 1000, 1)}
                  {inputs.test === "two-sample-t" &&
                    number(
                      "covariate_correlation",
                      "Pre-task covariate correlation",
                      -0.95,
                      0.95,
                      0.01,
                      "Requires a declared pre-task covariate; uses the approximate ANCOVA factor 1 − rho².",
                    )}
                  {paired && (
                    <>
                      {number(
                        "period_effect",
                        "Period effect",
                        -1000,
                        1000,
                        "any",
                        "Same units as effect; nonzero effects require simulation.",
                      )}
                      {number(
                        "order_effect",
                        "Additional order effect",
                        -1000,
                        1000,
                        "any",
                        "Shift for participants assigned the positive order; carryover is unsupported.",
                      )}
                    </>
                  )}
                  {simulation && (
                    <>
                      {number(
                        "simulations",
                        "Simulation repetitions",
                        200,
                        10000,
                        100,
                      )}
                      {number("seed", "Reproducible seed", 0, 4294967295, 1)}
                    </>
                  )}
                  {inputs.distribution === "ordinal" &&
                    number("ordinal_levels", "Ordinal categories", 2, 11, 1)}
                </fieldset>
              </details>
              {!tests.length && (
                <p className="type-body text-text-muted">
                  This protocol has no supported two-arm comparison recipe.
                  Record a supported analysis in Setup; the planner will not
                  invent a sample size.
                </p>
              )}
              <div className="flex flex-wrap gap-3">
                <Button
                  type="submit"
                  disabled={!canEdit || busy || !tests.length}
                >
                  {busy ? "Calculating…" : "Calculate and save plan"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={!canEdit || busy || !tests.length}
                  onClick={(e) => {
                    if (e.currentTarget.form?.reportValidity())
                      void calculate(true);
                  }}
                >
                  Update from tagged pilot sessions
                </Button>
              </div>
              <p className="type-note text-text-muted">
                Tag real pilot sessions in Data. Their outcomes are excluded
                from confirmatory analysis; synthetic rows are never used in
                pilot estimates.
              </p>
            </form>
            {result && (
              <section
                className="flex flex-col gap-4 border-t border-border pt-5"
                aria-live="polite"
              >
                <h3 className="type-subhead text-text">
                  {result.basis === "pilot-data"
                    ? "Plan based on pilot data"
                    : "Plan based on assumptions"}
                </h3>
                {(dirty || result.stale) && (
                  <p className="type-note text-critical">
                    {result.stale
                      ? "The recorded protocol changed after this plan was saved."
                      : "Inputs have changed."}{" "}
                    Recalculate to update the result below.
                  </p>
                )}
                <p className="type-body text-text">
                  {result.required
                    ? `${result.required.recruitTotal} participants to recruit (${result.required.recruitPerArm} ${paired ? "paired participants" : "per arm"}), allowing for dropout. ${result.required.totalN} complete participants reach estimated ${percent(result.required.power)} power.`
                    : (result.requiredWithheld?.message ??
                      `The target is not reached within ${result.inputs.max_n} participants. No required sample size is reported.`)}
                </p>
                {result.required?.ci && (
                  <p className="type-note text-text-muted">
                    Simulation 95% interval at the estimated sample size:{" "}
                    {percent(result.required.ci[0])} to{" "}
                    {percent(result.required.ci[1])}.
                  </p>
                )}
                {result.pilot && (
                  <div className="flex flex-col gap-1 type-body text-text">
                    <p>
                      {result.pilot.participants} pilot participants; SD{" "}
                      {result.pilot.sd.toPrecision(4)}, 95% interval{" "}
                      {result.pilot.sdCI
                        .map((n) => n.toPrecision(4))
                        .join(" to ")}
                      .
                    </p>
                    <p>
                      Before pilot:{" "}
                      {result.before?.required?.recruitTotal ??
                        "target not reached"}{" "}
                      to recruit. After pilot:{" "}
                      {result.required?.recruitTotal ?? "target not reached"}.
                    </p>
                    {!result.pilot.actionable && (
                      <p className="text-critical">
                        Fewer than 8 pilot participants: this variance interval
                        is too wide to act on.
                      </p>
                    )}
                    {result.pilotSensitivity?.map((p) => (
                      <p key={p.sd} className="type-note text-text-muted">
                        At pilot SD {p.sd.toPrecision(4)}:{" "}
                        {p.required
                          ? `${p.required.recruitTotal} to recruit`
                          : "target not reached in range"}
                        .
                      </p>
                    ))}
                  </div>
                )}
                {result.nullPower && (
                  <p className="type-note text-text-muted">
                    Under no treatment effect, the simulation rejects{" "}
                    {percent(result.nullPower.power)} of runs at planned n (95%
                    interval {result.nullPower.ci.map(percent).join(" to ")};
                    nominal alpha {percent(result.inputs.alpha)}).
                  </p>
                )}
                <PowerChart result={result} />
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse type-body text-left">
                    <caption className="pb-2 text-left type-label text-text">
                      Sensitivity at planned sample sizes ({result.effectUnits})
                    </caption>
                    <thead>
                      <tr className="border-b border-border type-caption text-text-muted">
                        <th className="py-2 font-normal">
                          Complete participants
                        </th>
                        <th className="py-2 font-normal">
                          Smallest detectable effect
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.sensitivity.map((s) => (
                        <tr key={s.totalN} className="border-b border-border">
                          <td className="py-2 tabular">{s.totalN}</td>
                          <td className="py-2 tabular">
                            {s.smallestDetectableEffect?.toPrecision(3) ??
                              "Not reached"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <ul className="flex list-disc flex-col gap-1 pl-5 type-note text-text-muted">
                  {result.warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
                <p className="type-caption text-text-muted">
                  Saved plan {result.planId}; protocol v
                  {result.protocol?.protocolVersion}. {result.method}{" "}
                  calculation.{" "}
                  {result.method === "simulation" &&
                    `Seed ${result.inputs.seed}, ${result.inputs.simulations} repetitions.`}
                </p>
              </section>
            )}
            {protocol.rerunOf && (
              <details
                className="border-t border-border pt-3"
                onToggle={(e) => {
                  if (e.currentTarget.open && !lineage)
                    plannerApi
                      .lineage(studyId)
                      .then(setLineage)
                      .catch((e) =>
                        setError(
                          e instanceof Error
                            ? e.message
                            : "Could not load the original design.",
                        ),
                      );
                }}
              >
                <summary className="cursor-pointer type-control text-text">
                  Compare with original study: {protocol.rerunOf}
                </summary>
                <p className="mt-3 type-note text-text-muted">
                  Designs are recorded separately. No automatic pooling.
                </p>
                {lineage && (
                  <div className="mt-3 overflow-x-auto">
                    <table className="w-full type-note">
                      <thead>
                        <tr>
                          <th className="text-left">Design field</th>
                          <th className="text-left">Original</th>
                          <th className="text-left">Re-run</th>
                        </tr>
                      </thead>
                      <tbody>
                        {lineage.fields.map((f) => (
                          <tr key={f.field} className="border-b border-border">
                            <td className="py-2">
                              {f.field}
                              {f.changed ? " (changed)" : ""}
                            </td>
                            <td className="max-w-64 break-words p-2">
                              {JSON.stringify(f.original) ?? "Not recorded"}
                            </td>
                            <td className="max-w-64 break-words p-2">
                              {JSON.stringify(f.rerun) ?? "Not recorded"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </details>
            )}
          </>
        )}
      </section>
    </Surface>
  );
}

function PowerChart({ result }: { result: PlanResult }) {
  const x = (n: number) => 56 + (720 * n) / result.inputs.max_n;
  const y = (p: number) => 24 + 240 * (1 - p);
  return (
    <figure className="flex flex-col gap-2">
      <svg
        viewBox="0 0 820 315"
        role="img"
        aria-label={`Estimated power versus total complete participants; target ${percent(result.inputs.target_power)}`}
        className="h-auto w-full"
      >
        {[0, 0.25, 0.5, 0.75, 1].map((p) => (
          <g key={p}>
            <line
              x1="56"
              x2="776"
              y1={y(p)}
              y2={y(p)}
              stroke="var(--viz-grid)"
            />
            <text
              x="48"
              y={y(p) + 4}
              textAnchor="end"
              className="fill-text-muted type-caption"
            >
              {percent(p)}
            </text>
          </g>
        ))}
        {[0, 0.25, 0.5, 0.75, 1].map((p) => (
          <text
            key={p}
            x={x(p * result.inputs.max_n)}
            y="286"
            textAnchor="middle"
            className="fill-text-muted type-caption"
          >
            {Math.round(p * result.inputs.max_n)}
          </text>
        ))}
        <line
          x1="56"
          x2="776"
          y1={y(result.inputs.target_power)}
          y2={y(result.inputs.target_power)}
          stroke="var(--viz-axis)"
          strokeDasharray="6 4"
        />
        <polyline
          points={result.curve
            .map((p) => `${x(p.totalN)},${y(p.power)}`)
            .join(" ")}
          fill="none"
          stroke="var(--series-1)"
          strokeWidth="2"
        />
        {result.curve
          .filter((p) => p.ci)
          .map((p) => (
            <line
              key={p.totalN}
              x1={x(p.totalN)}
              x2={x(p.totalN)}
              y1={y(p.ci![0])}
              y2={y(p.ci![1])}
              stroke="var(--series-1)"
              strokeWidth="1"
            />
          ))}
        <text
          x="416"
          y="310"
          textAnchor="middle"
          className="fill-text-muted type-caption"
        >
          Total complete participants
        </text>
      </svg>
      <figcaption className="type-note text-text-muted">
        Power curve for the recorded assumptions. Dashed line: target power.{" "}
        {result.method === "simulation" &&
          "Vertical marks: 95% Monte Carlo intervals."}
      </figcaption>
    </figure>
  );
}
