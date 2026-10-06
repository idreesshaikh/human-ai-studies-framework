import { useRef, useState, type FormEvent } from "react";
import { CircleAlert, Loader2, Plus, X } from "lucide-react";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Field } from "@/components/ui/field";
import { Notice } from "@/components/ui/notice";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { asList, asRecord, asText } from "@/lib/compiler";
import {
  conversationApi,
  type ManualProtocolFields,
} from "@/lib/conversationApi";
import { validateManualProtocol, type ManualProblem } from "@/lib/manualProtocol";
import { measureOptionsFromMoves } from "@/lib/uiText";
import type { DesignMove } from "@/lib/types";

const DESIGN_OPTIONS = [
  {
    value: "within-subjects",
    label: "Within-subjects",
    hint: "Each developer does both conditions.",
  },
  {
    value: "between-subjects",
    label: "Between-subjects",
    hint: "Each developer does one condition.",
  },
];

const MEASURE_OPTIONS = [
  "task completion time",
  "solution correctness",
  "cognitive load",
  "code comprehension",
];

type Design = ManualProtocolFields["design"];

function fromProtocol(
  protocol: Record<string, unknown> = {},
  acceptedMeasures: string[] = [],
) {
  const participants = asRecord(protocol.participants);
  const session = asRecord(protocol.session);
  const conditions = asList(protocol.conditions).map(asText);
  const questions = asList(protocol.researchQuestions)
    .map((rq) => asText(asRecord(rq).text))
    .filter(Boolean);
  return {
    title: asText(asRecord(protocol.study).title),
    researchQuestions: questions.length ? questions : [""],
    design: (participants.design === "between-subjects"
      ? "between-subjects"
      : "within-subjects") as Design,
    conditions: [conditions[0] ?? "", conditions[1] ?? ""],
    participantDescription: asText(participants.description),
    plannedParticipants: asText(participants.planned),
    taskDescription:
      asText(asRecord(asList(protocol.tasks)[0]).description) ||
      asText(session.taskDescription),
    sessionMinutes: asText(session.durationMinutes),
    measures: [
      ...new Set([
        ...asList(protocol.measures).map(asText).filter(Boolean),
        ...acceptedMeasures,
      ]),
    ],
  };
}

const MAX_OUTCOMES = 6;
const MAX_QUESTIONS = 6;

export function ManualProtocolDialog({
  studyId,
  protocol,
  moves = [],
  onClose,
  onEntered,
}: {
  studyId: string;
  protocol?: Record<string, unknown>;
  /** Moves from the chat: accepted measure cards pre-check their outcome. */
  moves?: DesignMove[];
  onClose: () => void;
  onEntered: () => void;
}) {
  const acceptedMeasures = measureOptionsFromMoves(moves, MEASURE_OPTIONS);
  const [form, setForm] = useState(() => fromProtocol(protocol, acceptedMeasures));
  const summary = useRef<HTMLDivElement>(null);
  const [problems, setProblems] = useState<ManualProblem[]>([]);
  const [other, setOther] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const set = (patch: Partial<typeof form>) => setForm((current) => ({ ...current, ...patch }));
  const [measureOptions] = useState(() => [...new Set([...MEASURE_OPTIONS, ...form.measures])]);
  const errorFor = (id: string) => problems.find((p) => p.id === id)?.message;

  const allMeasures = () => [
    ...new Set([...form.measures, ...other.split(",").map((m) => m.trim()).filter(Boolean)]),
  ];
  const selectedCount = allMeasures().length;

  const toggleMeasure = (measure: string) =>
    set({
      measures: form.measures.includes(measure)
        ? form.measures.filter((m) => m !== measure)
        : [...form.measures, measure],
    });

  function focusField(id: string) {
    const el = document.getElementById(id);
    el?.scrollIntoView({ block: "center" });
    el?.focus();
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const measures = allMeasures();
    const found = validateManualProtocol({ ...form, measures });
    setProblems(found);
    if (found.length) {
      requestAnimationFrame(() => {
        summary.current?.scrollIntoView({ block: "nearest" });
        summary.current?.focus();
      });
      return;
    }
    setSaving(true);
    setError("");
    try {
      await conversationApi.enterProtocol(studyId, {
        ...form,
        researchQuestions: form.researchQuestions.map((q) => q.trim()),
        conditions: form.conditions.map((c) => c.trim()),
        plannedParticipants: Number(form.plannedParticipants),
        sessionMinutes: Number(form.sessionMinutes),
        measures,
        counterbalanced: form.design === "within-subjects",
      });
      onEntered();
      onClose();
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : "Could not save the protocol details.");
    } finally {
      setSaving(false);
    }
  }

  const formId = "manual-protocol-form";
  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogContent wide>
        <DialogHeader>
          <DialogTitle>Enter protocol details</DialogTitle>
          <DialogDescription>
            These replace earlier decisions; approve the draft before running.
          </DialogDescription>
        </DialogHeader>
        <DialogBody role="region" aria-label="Protocol fields">
          <form id={formId} noValidate onSubmit={submit} className="form-stack">
            {problems.length > 0 && (
              <div
                ref={summary}
                tabIndex={-1}
                role="alert"
                className="rounded-control border border-critical bg-surface p-3"
              >
                <p className="flex items-center gap-2 type-label text-critical">
                  <CircleAlert className="size-4 shrink-0" aria-hidden />
                  {problems.length === 1 ? "1 problem to fix" : `${problems.length} problems to fix`}
                </p>
                <ul className="mt-2 list-disc pl-6 type-caption text-text">
                  {problems.map((p) => (
                    <li key={p.id}>
                      <a
                        href={`#${p.id}`}
                        className="underline"
                        onClick={(e) => {
                          e.preventDefault();
                          focusField(p.id);
                        }}
                      >
                        {p.label}
                      </a>
                      : {p.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <section className="form-section" aria-labelledby="manual-h-study">
              <h3 id="manual-h-study" className="type-subhead text-text">Study</h3>
              <Field id="manual-title" label="Study name" required error={errorFor("manual-title")}>
                <Input maxLength={160} autoComplete="off" value={form.title} onChange={(e) => set({ title: e.target.value })} />
              </Field>
              {form.researchQuestions.map((question, i) => (
                <Field
                  key={i}
                  id={`manual-rq-${i}`}
                  label={`Research question ${i + 1}`}
                  required
                  error={errorFor(`manual-rq-${i}`)}
                  action={
                    form.researchQuestions.length > 1 ? (
                      <Button
                        type="button"
                        variant="subtle"
                        size="sm"
                        aria-label={`Remove research question ${i + 1}`}
                        onClick={() => set({ researchQuestions: form.researchQuestions.filter((_, j) => j !== i) })}
                      >
                        <X aria-hidden />
                        Remove
                      </Button>
                    ) : undefined
                  }
                >
                  <Textarea
                    autoGrow
                    rows={2}
                    maxLength={500}
                    value={question}
                    onChange={(e) =>
                      set({ researchQuestions: form.researchQuestions.map((q, j) => (j === i ? e.target.value : q)) })
                    }
                  />
                </Field>
              ))}
              {form.researchQuestions.length < MAX_QUESTIONS && (
                <Button
                  type="button"
                  variant="subtle"
                  size="sm"
                  className="self-start"
                  onClick={() => set({ researchQuestions: [...form.researchQuestions, ""] })}
                >
                  <Plus aria-hidden />
                  Add research question
                </Button>
              )}
            </section>

            <section className="form-section" aria-labelledby="manual-h-design">
              <h3 id="manual-h-design" className="type-subhead text-text">Design</h3>
              <div className="form-grid">
                <Field
                  id="manual-design"
                  label="Study design"
                  className="span-2"
                  hint={
                    form.design === "within-subjects"
                      ? "Both conditions per participant; order is counterbalanced."
                      : "One condition per participant."
                  }
                >
                  <Select value={form.design} onValueChange={(v) => set({ design: v as Design })} options={DESIGN_OPTIONS} />
                </Field>
                {form.conditions.map((condition, i) => (
                  <Field key={i} id={`manual-condition-${i}`} label={`Condition ${i + 1}`} required error={errorFor(`manual-condition-${i}`)}>
                    <Input
                      maxLength={80}
                      placeholder={i === 0 ? "e.g. AI-assisted" : "e.g. Unassisted"}
                      value={condition}
                      onChange={(e) => set({ conditions: form.conditions.map((c, j) => (j === i ? e.target.value : c)) })}
                    />
                  </Field>
                ))}
              </div>
            </section>

            <section className="form-section" aria-labelledby="manual-h-people">
              <h3 id="manual-h-people" className="type-subhead text-text">Participants</h3>
              <div className="form-grid">
                <Field
                  id="manual-participants"
                  label="Who takes part"
                  required
                  className="span-2"
                  hint="Role, experience, and any inclusion criteria."
                  error={errorFor("manual-participants")}
                >
                  <Input
                    maxLength={240}
                    placeholder="e.g. Python developers"
                    value={form.participantDescription}
                    onChange={(e) => set({ participantDescription: e.target.value })}
                  />
                </Field>
                <Field id="manual-planned" label="Planned participants" required hint="4 to 1000." error={errorFor("manual-planned")}>
                  <Input type="number" inputMode="numeric" min={4} max={1000} stepper quantity value={form.plannedParticipants} onChange={(e) => set({ plannedParticipants: e.target.value })} />
                </Field>
                <Field id="manual-minutes" label="Session length" required hint="Minutes, 15 to 180." error={errorFor("manual-minutes")}>
                  <Input type="number" inputMode="numeric" min={15} max={180} step={5} stepper unit="min" quantity value={form.sessionMinutes} onChange={(e) => set({ sessionMinutes: e.target.value })} />
                </Field>
              </div>
            </section>

            <section className="form-section" aria-labelledby="manual-h-task">
              <h3 id="manual-h-task" className="type-subhead text-text">Task</h3>
              <Field id="manual-task" label="What participants do" required error={errorFor("manual-task")}>
                <Textarea autoGrow rows={2} maxLength={500} value={form.taskDescription} onChange={(e) => set({ taskDescription: e.target.value })} />
              </Field>
            </section>

            <fieldset
              className="form-section"
              id="manual-outcomes"
              tabIndex={-1}
              aria-describedby={errorFor("manual-outcomes") ? "manual-outcomes-error" : undefined}
            >
              <legend className="flex w-full items-baseline justify-between gap-2">
                <h3 className="type-subhead text-text">Outcomes</h3>
                <span className="type-caption text-text-muted" aria-live="polite">
                  {selectedCount} of {MAX_OUTCOMES} selected
                </span>
              </legend>
              {errorFor("manual-outcomes") && (
                <p id="manual-outcomes-error" className="flex items-start gap-1 type-note text-critical">
                  <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                  {errorFor("manual-outcomes")}
                </p>
              )}
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {measureOptions.map((measure) => (
                  <Checkbox
                    key={measure}
                    bordered
                    label={measure}
                    checked={form.measures.includes(measure)}
                    onChange={() => toggleMeasure(measure)}
                  />
                ))}
              </div>
              <Field id="manual-other-outcomes" label="Other outcomes" hint="Separate several with commas.">
                <Input placeholder="e.g. defect count" value={other} onChange={(e) => setOther(e.target.value)} />
              </Field>
            </fieldset>
            {error && <Notice kind="problem">{error}</Notice>}
          </form>
        </DialogBody>
        <DialogFooter aria-busy={saving}>
          <Button type="button" variant="outline" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form={formId} size="sm" disabled={saving}>
            {saving && <Loader2 className="size-4 animate-spin" aria-hidden />}
            {saving ? "Saving…" : "Save draft"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
