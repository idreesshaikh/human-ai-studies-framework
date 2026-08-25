import { useMemo, useState } from "react";
import { Check, ClipboardCheck, Loader2, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  conversationApi,
  type QuickProtocolInput,
  type QuickProtocolResult,
} from "@/lib/conversationApi";

type Design = QuickProtocolInput["design"];
type FormState = Omit<QuickProtocolInput, "conditions"> & {
  conditionA: string;
  conditionB: string;
};
type Errors = Partial<Record<keyof FormState | "conditions" | "measures", string>>;

const MEASURE_OPTIONS = [
  { value: "task completion time", label: "Task completion time" },
  { value: "solution correctness", label: "Solution correctness" },
  { value: "code defects", label: "Code defects" },
  { value: "cognitive load", label: "Cognitive load / workload" },
  { value: "code comprehension", label: "Code comprehension" },
  { value: "review quality", label: "Review quality" },
] as const;

const DESIGN_OPTIONS = [
  {
    value: "within-subjects",
    label: "Within-subjects",
    hint: "Each developer does both conditions; order is counterbalanced.",
  },
  {
    value: "between-subjects",
    label: "Between-subjects",
    hint: "Each developer does one condition; groups are assigned separately.",
  },
];

const INITIAL: FormState = {
  title: "",
  researchQuestion: "",
  design: "within-subjects",
  conditionA: "AI-assisted",
  conditionB: "Unassisted",
  participantDescription: "",
  plannedParticipants: 12,
  taskDescription: "",
  sessionMinutes: 45,
  measures: ["task completion time", "solution correctness"],
  counterbalanced: true,
};

function FieldError({ message }: { message?: string }) {
  return message ? <p className="type-caption text-critical">{message}</p> : null;
}

function Checklist({
  value,
  label,
  checked,
  onChange,
}: {
  value: string;
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-2.5 rounded-control border border-border bg-surface px-3 py-2.5 transition-colors duration-fast hover:border-control-edge">
      <input
        type="checkbox"
        className="mt-0.5 size-4 accent-accent"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        value={value}
      />
      <span className="type-caption text-text">{label}</span>
    </label>
  );
}

function protocolSummary(result: QuickProtocolResult) {
  const protocol = result.protocol ?? {};
  const participants = (protocol.participants ?? {}) as Record<string, unknown>;
  const session = (protocol.session ?? {}) as Record<string, unknown>;
  const conditions = Array.isArray(protocol.conditions)
    ? protocol.conditions.map(String)
    : [];
  return {
    conditions,
    design: String(participants.design ?? ""),
    participants: String(participants.planned ?? ""),
    task: String(session.taskDescription ?? ""),
    minutes: String(session.durationMinutes ?? ""),
  };
}

export function QuickProtocolForm({
  studyId,
  initialTitle = "",
  initialResearchQuestion = "",
  onApplied,
}: {
  studyId: string;
  initialTitle?: string;
  initialResearchQuestion?: string;
  onApplied?: () => void;
}) {
  const [form, setForm] = useState<FormState>(() => ({
    ...INITIAL,
    title: initialTitle,
    researchQuestion: initialResearchQuestion,
  }));
  const [errors, setErrors] = useState<Errors>({});
  const [submitError, setSubmitError] = useState("");
  const [result, setResult] = useState<QuickProtocolResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [applied, setApplied] = useState(false);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
    setSubmitError("");
  };

  const validate = (): Errors => {
    const next: Errors = {};
    if (!form.title.trim()) next.title = "Give the study a name.";
    if (form.researchQuestion.trim().length < 10) {
      next.researchQuestion = "Write the question this study will answer.";
    }
    if (!form.conditionA.trim() || !form.conditionB.trim()) {
      next.conditions = "Name both conditions you want to compare.";
    } else if (form.conditionA.trim().toLowerCase() === form.conditionB.trim().toLowerCase()) {
      next.conditions = "The two conditions must be different.";
    }
    const minimum = form.design === "between-subjects" ? 6 : 4;
    if (form.plannedParticipants < minimum) {
      next.plannedParticipants = `Use at least ${minimum} participants for this design.`;
    }
    if (!form.participantDescription.trim()) {
      next.participantDescription = "Describe who you can recruit.";
    }
    if (form.taskDescription.trim().length < 8) {
      next.taskDescription = "Describe the concrete coding task.";
    }
    if (form.sessionMinutes < 15 || form.sessionMinutes > 180) {
      next.sessionMinutes = "Choose a session between 15 and 180 minutes.";
    }
    if (form.measures.length === 0) next.measures = "Choose at least one outcome.";
    return next;
  };

  const submit = async () => {
    if (busy) return;
    const next = validate();
    setErrors(next);
    if (Object.keys(next).length > 0) return;
    setBusy(true);
    setSubmitError("");
    setResult(null);
    setApplied(false);
    try {
      const created = await conversationApi.quickProtocol(studyId, {
        title: form.title.trim(),
        researchQuestion: form.researchQuestion.trim(),
        design: form.design,
        conditions: [form.conditionA.trim(), form.conditionB.trim()],
        participantDescription: form.participantDescription.trim(),
        plannedParticipants: form.plannedParticipants,
        taskDescription: form.taskDescription.trim(),
        sessionMinutes: form.sessionMinutes,
        measures: form.measures,
        counterbalanced: form.counterbalanced,
      });
      setResult(created);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Could not create the draft.");
    } finally {
      setBusy(false);
    }
  };

  const apply = async () => {
    if (!result || busy) return;
    setBusy(true);
    setSubmitError("");
    try {
      await conversationApi.approve(studyId, result.compilationId);
      setApplied(true);
      onApplied?.();
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Could not apply the draft.");
    } finally {
      setBusy(false);
    }
  };

  const summary = useMemo(() => (result ? protocolSummary(result) : null), [result]);

  return (
    <div className="h-full overflow-y-auto bg-well">
      <div className="mx-auto flex w-full max-w-wide flex-col gap-5 p-4 sm:p-6">
        <header className="border-b border-border pb-5">
          <div>
            <h2 className="type-section text-text">Fill the choices you already know</h2>
            <p className="type-body mt-1 max-w-reading text-text-muted">
              Use fields for facts that are easy to choose or validate. Both paths write to
              the same protocol draft, so you can switch whenever a choice needs explanation.
            </p>
          </div>
        </header>

        <Notice kind="note">
          <strong>Supported lane:</strong> a coding task in VS Code with AI-assisted work
          compared with an unassisted condition. Choose within- or between-subjects; the
          compiler rejects anything outside this lane before it can be applied.
        </Notice>

        <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_21rem]">
          <Card className="min-w-0">
            <CardContent className="flex flex-col gap-6 p-4 sm:p-6">
              <section className="flex flex-col gap-4" aria-labelledby="study-details-heading">
                <div>
                  <p className="type-label font-medium text-text-muted">Study brief</p>
                  <h3 id="study-details-heading" className="type-subheading mt-1 text-text">
                    What are you trying to learn?
                  </h3>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="flex flex-col gap-2 sm:col-span-2">
                    <Label htmlFor="quick-title">Study name</Label>
                    <Input id="quick-title" value={form.title} onChange={(event) => set("title", event.target.value)} aria-invalid={Boolean(errors.title)} />
                    <FieldError message={errors.title} />
                  </div>
                  <div className="flex flex-col gap-2 sm:col-span-2">
                    <Label htmlFor="quick-rq">Research question</Label>
                    <Textarea id="quick-rq" value={form.researchQuestion} onChange={(event) => set("researchQuestion", event.target.value)} placeholder="e.g. Does AI assistance change debugging time and correctness for novice developers?" aria-invalid={Boolean(errors.researchQuestion)} />
                    <FieldError message={errors.researchQuestion} />
                  </div>
                </div>
              </section>

              <section className="flex flex-col gap-4 border-t border-border pt-5" aria-labelledby="design-heading">
                <div>
                  <p className="type-label font-medium text-text-muted">Comparison</p>
                  <h3 id="design-heading" className="type-subheading mt-1 text-text">
                    What will you compare?
                  </h3>
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="quick-design">Study design</Label>
                  <Select
                    id="quick-design"
                    value={form.design}
                    onValueChange={(value) => set("design", value as Design)}
                    options={DESIGN_OPTIONS}
                  />
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="quick-condition-a">Condition one</Label>
                    <Input id="quick-condition-a" value={form.conditionA} onChange={(event) => set("conditionA", event.target.value)} aria-invalid={Boolean(errors.conditions)} />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="quick-condition-b">Condition two</Label>
                    <Input id="quick-condition-b" value={form.conditionB} onChange={(event) => set("conditionB", event.target.value)} aria-invalid={Boolean(errors.conditions)} />
                  </div>
                </div>
                <FieldError message={errors.conditions} />
                {form.design === "within-subjects" && (
                  <Checklist
                    value="counterbalanced"
                    label="Counterbalance condition order across developers"
                    checked={form.counterbalanced}
                    onChange={(checked) => set("counterbalanced", checked)}
                  />
                )}
              </section>

              <section className="flex flex-col gap-4 border-t border-border pt-5" aria-labelledby="session-heading">
                <div>
                  <p className="type-label font-medium text-text-muted">Session</p>
                  <h3 id="session-heading" className="type-subheading mt-1 text-text">
                    Who will do what, and for how long?
                  </h3>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="flex flex-col gap-2 sm:col-span-2">
                    <Label htmlFor="quick-participants">Participant profile</Label>
                    <Input id="quick-participants" value={form.participantDescription} onChange={(event) => set("participantDescription", event.target.value)} placeholder="e.g. novice Python developers" aria-invalid={Boolean(errors.participantDescription)} />
                    <FieldError message={errors.participantDescription} />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="quick-count">Planned participants</Label>
                    <Input id="quick-count" type="number" min={4} max={1000} quantity value={form.plannedParticipants} onChange={(event) => set("plannedParticipants", Number(event.target.value))} aria-invalid={Boolean(errors.plannedParticipants)} />
                    <FieldError message={errors.plannedParticipants} />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="quick-minutes">Session length</Label>
                    <Input id="quick-minutes" type="number" min={15} max={180} quantity unit="min" value={form.sessionMinutes} onChange={(event) => set("sessionMinutes", Number(event.target.value))} aria-invalid={Boolean(errors.sessionMinutes)} />
                    <FieldError message={errors.sessionMinutes} />
                  </div>
                  <div className="flex flex-col gap-2 sm:col-span-2">
                    <Label htmlFor="quick-task">Coding task</Label>
                    <Textarea id="quick-task" value={form.taskDescription} onChange={(event) => set("taskDescription", event.target.value)} placeholder="e.g. Fix a small Python bug in a provided repository." aria-invalid={Boolean(errors.taskDescription)} />
                    <FieldError message={errors.taskDescription} />
                  </div>
                </div>
              </section>

              <section className="flex flex-col gap-4 border-t border-border pt-5" aria-labelledby="outcomes-heading">
                <div>
                  <p className="type-label font-medium text-text-muted">Outcomes</p>
                  <h3 id="outcomes-heading" className="type-subheading mt-1 text-text">
                    What should the study capture?
                  </h3>
                  <p className="type-caption mt-1 text-text-muted">
                    Choose the outcomes that matter. The standard VS Code session capture is
                    configured automatically with the draft.
                  </p>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  {MEASURE_OPTIONS.map((option) => (
                    <Checklist
                      key={option.value}
                      value={option.value}
                      label={option.label}
                      checked={form.measures.includes(option.value)}
                      onChange={(checked) =>
                        set(
                          "measures",
                          checked
                            ? [...form.measures, option.value]
                            : form.measures.filter((measure) => measure !== option.value),
                        )
                      }
                    />
                  ))}
                </div>
                <FieldError message={errors.measures} />
              </section>

              {submitError && <Notice kind="problem">{submitError}</Notice>}

              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-5">
                <p className="type-caption max-w-reading text-text-muted">
                  The compiler checks the protocol before anything is applied. You can still
                  change it in the chat afterwards.
                </p>
                <Button onClick={submit} disabled={busy}>
                  {busy && !result ? <Loader2 className="animate-spin" aria-hidden /> : <ClipboardCheck aria-hidden />}
                  Validate and create draft
                </Button>
              </div>
            </CardContent>
          </Card>

          <aside className="flex flex-col gap-4 border-l border-border pl-4 xl:sticky xl:top-5" aria-label="Checklist guidance">
            {result && summary ? (
              <Card className="border-accent/50">
                <CardContent className="flex flex-col gap-4 p-4">
                  <div className="flex items-start gap-2">
                    <ShieldCheck className="mt-0.5 size-5 shrink-0 text-accent" aria-hidden />
                    <div>
                      <p className="type-eyebrow text-accent">COMPILER RESULT</p>
                      <h3 className="type-subheading mt-1 text-text">
                        {result.valid ? "Draft verified" : "Draft needs attention"}
                      </h3>
                    </div>
                  </div>
                  {result.valid ? (
                    <p className="type-caption text-text-muted">
                      The required protocol fields are present and the selected design has a
                      runnable analysis plan.
                    </p>
                  ) : (
                    <Notice kind="problem">
                      {result.errors.concat(result.unresolved).join(" ") || "The compiler found an issue."}
                    </Notice>
                  )}
                  <dl className="divide-y divide-border rounded-plate border border-border bg-surface">
                    <div className="flex gap-3 px-3 py-2.5"><dt className="type-caption text-text-muted">Design</dt><dd className="ml-auto text-right type-caption text-text">{summary.design}</dd></div>
                    <div className="flex gap-3 px-3 py-2.5"><dt className="type-caption text-text-muted">Conditions</dt><dd className="ml-auto text-right type-caption text-text">{summary.conditions.join(" / ")}</dd></div>
                    <div className="flex gap-3 px-3 py-2.5"><dt className="type-caption text-text-muted">Participants</dt><dd className="ml-auto text-right type-quantity text-text">{summary.participants}</dd></div>
                    <div className="flex gap-3 px-3 py-2.5"><dt className="type-caption text-text-muted">Session</dt><dd className="ml-auto text-right type-quantity text-text">{summary.minutes} min</dd></div>
                  </dl>
                  <div>
                    <p className="type-caption font-medium text-text">Outcomes</p>
                    <p className="mt-1 type-caption text-text-muted">{result.selectedMeasures.join(" · ")}</p>
                  </div>
                  {result.valid && !applied && (
                    <Button onClick={apply} disabled={busy} className="w-full">
                      {busy ? <Loader2 className="animate-spin" aria-hidden /> : <Check aria-hidden />}
                      Apply verified protocol
                    </Button>
                  )}
                  {applied && (
                    <Notice kind="note">
                      Protocol applied. The study is ready for the Run tab when you are.
                    </Notice>
                  )}
                </CardContent>
              </Card>
            ) : (
              <div className="flex flex-col gap-3">
                  <p className="type-label font-medium text-text">How this works</p>
                  <ol className="flex flex-col gap-3">
                    {[
                      ["Fill the essentials", "Use the plain-language fields; no protocol vocabulary required."],
                      ["Validate", "The server checks scope, required fields, schema, and analysis."],
                      ["Review and run", "Apply the verified draft, then move to Run to mint sessions."],
                    ].map(([title, text], index) => (
                      <li key={title} className="flex gap-3">
                        <span className="type-quantity flex size-6 shrink-0 items-center justify-center rounded-dot border border-border bg-well text-text-muted">{index + 1}</span>
                        <div><p className="type-caption font-medium text-text">{title}</p><p className="mt-0.5 type-caption text-text-muted">{text}</p></div>
                      </li>
                    ))}
                  </ol>
              </div>
            )}
          </aside>
        </div>
      </div>
    </div>
  );
}
