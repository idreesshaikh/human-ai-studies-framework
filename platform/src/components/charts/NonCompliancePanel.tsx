import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import {
  plannerApi,
  type NonComplianceEstimator,
  type NonComplianceInputs,
  type NonComplianceMechanism,
  type NonComplianceResult,
} from "@/lib/plannerApi";

/* What breaking an assigned AI condition does to a between-subjects study:
 * the bias of three analyses against the true effect of using AI, and the
 * sample each needs. Everything here is simulated from rates the researcher
 * enters or from measured calibration rates; nothing is read from study data,
 * so the panel works for anyone who can view the study. */

const ENTERED = "entered";
/** Matches the server's search limit for the required sample size. */
const REQUIRED_N_LIMIT = 2000;

interface Draft {
  effect_d: number;
  n_per_arm: number;
  control_violation: number;
  treatment_nonuse: number;
  mechanism: NonComplianceMechanism;
  mix: string;
  sensitivity: number;
  specificity: number;
}
/* The detection rates have no default: any starting value would read as a
 * claim about how well AI use is flagged. */
const DEFAULTS: Draft = {
  effect_d: 0.5,
  n_per_arm: 40,
  control_violation: 0.2,
  treatment_nonuse: 0.1,
  mechanism: "random",
  mix: ENTERED,
  sensitivity: NaN,
  specificity: NaN,
};
const MECHANISMS = [
  {
    value: "random",
    label: "Random",
    hint: "Violators and non-users are picked at random.",
  },
  {
    value: "skill-linked",
    label: "Skill-linked",
    hint: "The weakest controls violate; the strongest AI-arm participants skip AI.",
  },
];
const DETECTION_SOURCES = [
  {
    value: ENTERED,
    label: "Enter rates",
    hint: "Type the sensitivity and specificity to test.",
  },
  {
    value: "instruction-only",
    label: "Route mix: instruction only",
    hint: "Measured calibration rates, all six AI routes in equal shares.",
  },
  {
    value: "locked-environment",
    label: "Route mix: locked environment",
    hint: "Measured calibration rates, browser paste and retyping only.",
  },
];
const ESTIMATORS: {
  id: NonComplianceEstimator;
  label: string;
  note: string;
}[] = [
  {
    id: "itt",
    label: "As assigned",
    note: "Compare the arms as randomised.",
  },
  {
    id: "exclude-detected",
    label: "Drop flagged controls",
    note: "Remove control participants flagged as AI users, then compare the arms.",
  },
  {
    id: "as-detected",
    label: "Flagged users against others",
    note: "Compare people flagged as AI users with everyone else, across both arms.",
  },
];
const NOT_COMPUTED = "Not computable";

const percent = (n: number | null) =>
  n === null ? NOT_COMPUTED : `${(n * 100).toFixed(1)}%`;
const bias = (n: number | null) => (n === null ? NOT_COMPUTED : n.toFixed(3));
const rate = (n: number) => n.toFixed(3);

function requestFor(draft: Draft): NonComplianceInputs {
  const { mix, sensitivity, specificity, ...scenario } = draft;
  return mix === ENTERED
    ? { ...scenario, sensitivity, specificity }
    : { ...scenario, mix };
}

export function NonCompliancePanel({ studyId }: { studyId: string }) {
  const [draft, setDraft] = useState<Draft>(DEFAULTS);
  const [ran, setRan] = useState<{
    request: NonComplianceInputs;
    result: NonComplianceResult;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);
  const headingId = useId();

  useEffect(() => {
    setRan(null);
    setError(null);
    setBusy(false);
    return () => {
      generation.current++;
    };
  }, [studyId]);

  const entered = draft.mix === ENTERED;
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((prior) => ({ ...prior, [key]: value }));
  const request = requestFor(draft);
  const dirty = ran && JSON.stringify(ran.request) !== JSON.stringify(request);

  const run = async () => {
    const version = ++generation.current;
    setBusy(true);
    setError(null);
    try {
      const result = await plannerApi.noncompliance(studyId, request);
      if (version === generation.current) setRan({ request, result });
    } catch (e) {
      if (version === generation.current)
        setError(
          e instanceof Error ? e.message : "The simulation could not be run.",
        );
    } finally {
      if (version === generation.current) setBusy(false);
    }
  };

  const number = (
    key:
      | "effect_d"
      | "n_per_arm"
      | "control_violation"
      | "treatment_nonuse"
      | "sensitivity"
      | "specificity",
    label: string,
    min: number,
    max: number,
    step: number | string,
    hint?: string,
    disabled = false,
  ) => (
    <Field label={label} hint={hint} required={!disabled}>
      <Input
        type="number"
        value={
          !disabled && Number.isFinite(draft[key]) ? String(draft[key]) : ""
        }
        min={min}
        max={max}
        step={step}
        required={!disabled}
        disabled={busy || disabled}
        onChange={(e) =>
          set(key, e.target.value === "" ? NaN : Number(e.target.value))
        }
      />
    </Field>
  );

  const skipped = ran
    ? ESTIMATORS.filter((e) => ran.result.estimators[e.id].refused > 0)
    : [];

  return (
    <section
      aria-labelledby={headingId}
      className="flex flex-col gap-4 border-t border-border pt-5"
    >
      <div className="flex flex-col gap-2">
        <h3 id={headingId} className="type-subhead text-text">
          Non-compliance sensitivity
        </h3>
        <p className="type-note text-text">
          Simulated; StudyLoop cannot verify non-use in a control arm.
        </p>
        <p className="max-w-reading type-body text-text-muted">
          Some control participants may use AI anyway, and some AI-arm
          participants may not. This simulation shows how far that moves each
          analysis from the true effect of using AI, and how many participants
          each one needs. The rates below are assumptions you set, not
          measurements of your study.
        </p>
      </div>
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          void run();
        }}
      >
        <div className="grid grid-cols-1 items-start gap-x-4 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
          {number(
            "effect_d",
            "Effect of using AI",
            -10,
            10,
            "any",
            "Change in the outcome caused by using AI, in SD units.",
          )}
          {number("n_per_arm", "Participants per arm", 4, 1000, 1)}
          {number(
            "control_violation",
            "Control-arm violation rate",
            0,
            0.5,
            0.01,
            "Share of the control arm who use AI anyway, up to 0.5.",
          )}
          {number(
            "treatment_nonuse",
            "AI-arm non-use rate",
            0,
            1,
            0.01,
            "Share of the AI arm who do not use it.",
          )}
          <Field
            label="Who breaks the condition"
            hint={MECHANISMS.find((m) => m.value === draft.mechanism)?.hint}
          >
            <Select
              value={draft.mechanism}
              options={MECHANISMS}
              disabled={busy}
              onValueChange={(v) => set("mechanism", v as NonComplianceMechanism)}
            />
          </Field>
          <Field
            label="Telemetry flag rates"
            hint={DETECTION_SOURCES.find((m) => m.value === draft.mix)?.hint}
          >
            <Select
              value={draft.mix}
              options={DETECTION_SOURCES}
              disabled={busy}
              onValueChange={(v) => set("mix", v)}
            />
          </Field>
          {number(
            "sensitivity",
            "Sensitivity",
            0,
            1,
            0.01,
            entered
              ? "Share of real AI users the telemetry flags."
              : "Set by the route mix.",
            !entered,
          )}
          {number(
            "specificity",
            "Specificity",
            0,
            1,
            0.01,
            entered
              ? "Share of non-users the telemetry correctly leaves unflagged."
              : "Set by calibration.",
            !entered,
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={busy}>
            {busy ? "Simulating…" : "Run simulation"}
          </Button>
        </div>
      </form>
      {error && (
        <p className="type-note text-critical" role="alert">
          {error}
        </p>
      )}
      {ran && (
        <div className="flex flex-col gap-3" aria-live="polite">
          {dirty && (
            <p className="type-note text-critical">
              Inputs have changed. Run the simulation again to update the table.
            </p>
          )}
          <p className="max-w-reading type-body text-text">
            Telemetry flag rates used: sensitivity{" "}
            <span className="tabular">{rate(ran.result.detection.sensitivity)}</span>
            , specificity{" "}
            <span className="tabular">{rate(ran.result.detection.specificity)}</span>
            ,{" "}
            {ran.result.detection.source === "calibration"
              ? "measured in calibration"
              : "entered by you"}
            .
          </p>
          <Table>
            <caption className="pb-2 text-left type-label text-text">
              Simulated estimates by analysis
            </caption>
            <THead>
              <TR>
                <TH scope="col">Analysis</TH>
                <TH scope="col">Bias (SD units)</TH>
                <TH scope="col">Coverage</TH>
                <TH scope="col">Rejects 'no difference'</TH>
                <TH scope="col">Required n per arm</TH>
              </TR>
            </THead>
            <TBody>
              {ESTIMATORS.map((e) => {
                const m = ran.result.estimators[e.id];
                const needed =
                  e.id === "as-detected"
                    ? "Not estimated"
                    : (ran.result.requiredN[e.id] ??
                      `Not reached by ${REQUIRED_N_LIMIT}`);
                return (
                  <TR key={e.id}>
                    <TH scope="row" className="min-w-48 align-top text-text">
                      <span className="type-body">{e.label}</span>
                      <span className="block type-caption font-normal text-text-muted">
                        {e.note}
                      </span>
                    </TH>
                    <TD className="tabular">{bias(m.bias)}</TD>
                    <TD className="tabular">{percent(m.coverage)}</TD>
                    <TD className="tabular">{percent(m.power)}</TD>
                    <TD className="tabular">{needed}</TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
          <ul className="flex list-disc flex-col gap-1 pl-5 type-note text-text-muted">
            <li>
              Bias is the average estimate minus the true effect. Coverage is
              how often the 95% interval contains the true effect.
            </li>
            <li>
              Rejects 'no difference' is the share of simulated studies whose
              test finds a difference at alpha 0.05. For a biased analysis it
              is not power to recover the true effect.
            </li>
            <li>
              Required n is the smallest number per arm at which an analysis
              rejects 'no difference' in 80% of simulated studies.
            </li>
            {skipped.map((e) => (
              <li key={e.id}>
                {e.label}: {ran.result.estimators[e.id].refused} simulated
                studies could not be compared because a group had fewer than
                two people.
              </li>
            ))}
            <li>The same inputs always give the same table.</li>
          </ul>
        </div>
      )}
    </section>
  );
}
