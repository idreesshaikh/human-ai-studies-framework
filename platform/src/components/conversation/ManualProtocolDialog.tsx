import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowDown, ArrowUp, CircleAlert, Loader2, Plus, X } from "lucide-react";
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
import { asList, asRecord, asText, measureText } from "@/lib/compiler";
import {
  conversationApi,
  type CompileResult,
  type ManualProtocolFields,
  type MeasureChoice,
} from "@/lib/conversationApi";
import { validateManualProtocol, type ManualProblem } from "@/lib/manualProtocol";
import { MEASURE_LABELS, measureOptionsFromMoves } from "@/lib/uiText";
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
  "time to first green",
  "test success",
  "overall workload",
  "self-rated comprehension",
];

const LEGACY_MEASURES: Record<string, string> = {
  "task completion time": "time to first green",
  "solution correctness": "test success",
  "cognitive load": "overall workload",
  "code comprehension": "self-rated comprehension",
};

type Design = ManualProtocolFields["design"];

type TaskDraft = {
  key: string;
  id?: string;
  title: string;
  description: string;
  minutes: string;
  materials: string;
  version: string;
  conditions?: string[];
};

function taskDraftsFromProtocol(protocol: Record<string, unknown> = {}): TaskDraft[] {
  const session = asRecord(protocol.session);
  const tasks = asList(protocol.tasks).map((entry, index) => {
    const task = asRecord(entry);
    return {
      key: asText(task.id) || `saved-${index}`,
      id: asText(task.id) || undefined,
      title: asText(task.title),
      description: asText(task.description),
      minutes: typeof task.minutes === "number" ? String(task.minutes) : "",
      materials: asText(task.materials),
      version: asText(task.version),
      conditions: asList(task.conditions).map(asText).filter(Boolean),
    };
  });
  if (tasks.length) return tasks;
  return [{ key: "primary", title: "", description: asText(session.taskDescription), minutes: "", materials: "", version: "" }];
}

function estimateRecordedTaskMinutes(
  tasks: TaskDraft[],
  conditions: string[],
  design: Design,
): number {
  const names = conditions.filter(Boolean);
  if (!names.length || !tasks.length) return 0;
  const minutes = (task: TaskDraft) => {
    const value = Number(task.minutes);
    return Number.isInteger(value) && value > 0 ? value : 0;
  };
  const assigned = (condition: string) => {
    const eligible = tasks.filter((task) => !task.conditions?.length || task.conditions.includes(condition));
    return eligible.length ? eligible : tasks;
  };
  let maximum = 0;
  // The assignment pattern repeats within this small window for the supported
  // two-condition designs. Use it directly so repeated tasks count twice.
  for (let participant = 0; participant < Math.max(24, tasks.length * names.length * 2); participant++) {
    let total = 0;
    if (design === "within-subjects") {
      const orderedConditions = participant % names.length
        ? [...names.slice(participant % names.length), ...names.slice(0, participant % names.length)]
        : names;
      orderedConditions.forEach((condition) => {
        const options = assigned(condition);
        total += minutes(options[(participant + names.indexOf(condition)) % options.length]);
      });
    } else {
      const condition = names[participant % names.length];
      total = assigned(condition).reduce((sum, task) => sum + minutes(task), 0);
    }
    maximum = Math.max(maximum, total);
  }
  return maximum;
}

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
    sessionMinutes: asText(session.durationMinutes),
    measures: [
      ...new Set([
        ...asList(protocol.measures).map(measureText).filter(Boolean),
        ...acceptedMeasures,
      ]),
    ],
  };
}

const MAX_OUTCOMES = 6;
const MAX_QUESTIONS = 6;
const MAX_TASKS = 12;

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
  onEntered: (result: CompileResult) => Promise<void>;
}) {
  const acceptedMeasures = measureOptionsFromMoves(moves, MEASURE_OPTIONS);
  const [form, setForm] = useState(() => fromProtocol(protocol, acceptedMeasures));
  const [tasks, setTasks] = useState(() => taskDraftsFromProtocol(protocol));
  const summary = useRef<HTMLDivElement>(null);
  const [problems, setProblems] = useState<ManualProblem[]>([]);
  const [other, setOther] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [catalog, setCatalog] = useState<MeasureChoice[]>([]);
  const [existingChoices, setExistingChoices] = useState<Record<string, string>>({});
  const [catalogError, setCatalogError] = useState(false);
  const [suggestions, setSuggestions] = useState<MeasureChoice[]>([]);
  const [lookup, setLookup] = useState<"idle" | "loading" | "ready" | "unavailable">("idle");
  const set = (patch: Partial<typeof form>) => setForm((current) => ({ ...current, ...patch }));
  const measureOptions = [...new Set([...MEASURE_OPTIONS, ...form.measures])];
  const errorFor = (id: string) => problems.find((p) => p.id === id)?.message;
  const updateTask = (index: number, patch: Partial<TaskDraft>) =>
    setTasks((current) => current.map((task, i) => i === index ? { ...task, ...patch } : task));
  const moveTask = (index: number, offset: number) =>
    setTasks((current) => {
      const next = [...current];
      const target = index + offset;
      if (target < 0 || target >= next.length) return current;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });

  useEffect(() => {
    let current = true;
    conversationApi.measureCatalog().then((choices) => {
      if (!current) return;
      setCatalog(choices);
      const canonical = (text: string) => {
        const declared = asList(protocol?.measures).map(asRecord).find((row) => row.construct === text);
        const matches = declared ? choices.filter((choice) => choice.instrument === declared.instrument && JSON.stringify(choice.fields) === JSON.stringify(declared.fields)) : [];
        return matches.length === 1 ? matches[0].construct : declared ? text : LEGACY_MEASURES[text.toLowerCase()] ?? text;
      };
      setExistingChoices(Object.fromEntries(asList(protocol?.measures).map(asRecord).filter((row) => typeof row.id === "string" && typeof row.construct === "string").map((row) => [canonical(String(row.construct)), String(row.id)])));
      setForm((form) => ({ ...form, measures: [...new Set(form.measures.map((text) => {
        return canonical(text);
      }))] }));
    }).catch(() => { if (current) setCatalogError(true); });
    return () => { current = false; };
  }, [protocol]);

  useEffect(() => {
    const query = other.split(",")[0].trim();
    setSuggestions([]);
    if (query.length < 2) { setLookup("idle"); return; }
    setLookup("loading");
    const controller = new AbortController();
    const timer = setTimeout(() => {
      conversationApi.measureSuggestions(studyId, query, form.design, controller.signal).then((result) => {
        if (controller.signal.aborted) return;
        setSuggestions(result.suggestions);
        setLookup("ready");
      }).catch(() => { if (!controller.signal.aborted) setLookup("unavailable"); });
    }, 200);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [other, form.design, studyId]);

  const choiceFor = (text: string) => catalog.find((choice) =>
    [choice.construct, ...choice.aliases].some((alias) => alias.toLowerCase() === text.toLowerCase()),
  );

  const allMeasures = () => [
    ...new Set([...form.measures, ...other.split(",").map((m) => m.trim()).filter(Boolean)]),
  ];
  const selectedCount = allMeasures().length;
  const minParticipants = form.design === "between-subjects" ? 6 : 4;
  const expectedTaskMinutes = estimateRecordedTaskMinutes(tasks, form.conditions, form.design);
  const sessionMinutes = Number(form.sessionMinutes);

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
    const found = validateManualProtocol({
      ...form,
      taskDescription: tasks[0]?.description ?? "",
      measures,
    });
    if (tasks.length === 0) {
      found.push({ id: "manual-tasks", label: "Tasks", message: "Keep at least one task in the study." });
    }
    tasks.forEach((task, index) => {
      const taskLabel = `Task ${index + 1}`;
      if (index > 0 && (task.description.trim().length < 8 || task.description.trim().length > 5000)) {
        found.push({
          id: index === 0 ? "manual-task" : `manual-task-desc-${index}`,
          label: taskLabel,
          message: "Describe what participants do in 8 to 5,000 characters.",
        });
      }
      if (task.title.trim().length > 80) {
        found.push({ id: `manual-task-title-${index}`, label: `${taskLabel} name`, message: "Use 80 characters or fewer." });
      }
      if (task.minutes && (!/^\d+$/.test(task.minutes) || Number(task.minutes) < 1 || Number(task.minutes) > 180)) {
        found.push({ id: `manual-task-minutes-${index}`, label: `${taskLabel} time`, message: "Enter a whole number from 1 to 180 minutes." });
      }
    });
    if (Number.isInteger(sessionMinutes) && expectedTaskMinutes > sessionMinutes) {
      found.push({
        id: "manual-task-minutes-summary",
        label: "Task time",
        message: `The assigned tasks total ${expectedTaskMinutes} minutes, longer than the ${sessionMinutes}-minute session. Shorten a task or increase the session length.`,
      });
    }
    if (measures.some((text) => !existingChoices[text] && !choiceFor(text)?.recipeByDesign[form.design])) {
      found.push({ id: "manual-other-outcomes", label: "Other outcomes", message: "Choose a supported mapping for each outcome. Set up custom capture or analysis in the chat instead." });
    }
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
      const result = await conversationApi.enterProtocol(studyId, {
        ...form,
        taskDescription: tasks[0].description.trim(),
        taskEdits: tasks.map((task) => ({
          id: task.id,
          title: task.title.trim(),
          description: task.description.trim(),
          minutes: task.minutes ? Number(task.minutes) : null,
          materials: task.materials.trim(),
          version: task.version.trim(),
        })),
        researchQuestions: form.researchQuestions.map((q) => q.trim()),
        conditions: form.conditions.map((c) => c.trim()),
        plannedParticipants: Number(form.plannedParticipants),
        sessionMinutes: Number(form.sessionMinutes),
        measures,
        measureIds: measures.filter((text) => !existingChoices[text]).map((text) => choiceFor(text)!.id),
        existingMeasureIds: measures.filter((text) => existingChoices[text]).map((text) => existingChoices[text]),
        typedMeasures: true,
        counterbalanced: form.design === "within-subjects",
      });
      await onEntered(result);
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
                <Field id="manual-planned" label="Planned participants" required hint={`${minParticipants} to 1000${form.design === "between-subjects" ? "; at least 3 per condition" : ""}.`} error={errorFor("manual-planned")}>
                  <Input type="number" inputMode="numeric" min={minParticipants} max={1000} stepper quantity value={form.plannedParticipants} onChange={(e) => set({ plannedParticipants: e.target.value })} />
                </Field>
                <Field id="manual-minutes" label="Session length" required hint="Minutes, 15 to 180." error={errorFor("manual-minutes")}>
                  <Input type="number" inputMode="numeric" min={15} max={180} step={5} stepper unit="min" quantity value={form.sessionMinutes} onChange={(e) => set({ sessionMinutes: e.target.value })} />
                </Field>
              </div>
            </section>

            <section className="form-section" aria-labelledby="manual-h-task">
              <h3 id="manual-h-task" className="type-subhead text-text">Task</h3>
              <p className="max-w-reading type-note text-text-muted">
                {form.design === "within-subjects"
                  ? "Participants do one task per condition. Tasks rotate across participants."
                  : "Each participant completes the task list under their assigned condition."}
                {" "}Expected times are optional; together they should fit the session.
              </p>
              <div className="flex flex-col gap-4">
                {tasks.map((task, index) => (
                  <fieldset key={task.key} className="flex min-w-0 flex-col gap-3 rounded-card border border-border p-3">
                    <legend className="px-1 type-label text-text">Task {index + 1}</legend>
                    <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
                      <Field id={`manual-task-title-${index}`} label="Task name (optional)" hint="Defaults to the first sentence of the task." error={errorFor(`manual-task-title-${index}`)}>
                        <Input maxLength={80} value={task.title} onChange={(e) => updateTask(index, { title: e.target.value })} />
                      </Field>
                      <div className="flex items-end gap-1">
                        <Button type="button" variant="outline" size="icon" aria-label={`Move task ${index + 1} up`} disabled={index === 0 || saving} onClick={() => moveTask(index, -1)}>
                          <ArrowUp aria-hidden />
                        </Button>
                        <Button type="button" variant="outline" size="icon" aria-label={`Move task ${index + 1} down`} disabled={index === tasks.length - 1 || saving} onClick={() => moveTask(index, 1)}>
                          <ArrowDown aria-hidden />
                        </Button>
                        <Button type="button" variant="subtle" size="sm" aria-label={`Remove task ${index + 1}`} disabled={tasks.length === 1 || saving} onClick={() => setTasks((current) => current.filter((_, i) => i !== index))}>
                          <X aria-hidden /> Remove
                        </Button>
                      </div>
                    </div>
                    <Field id={index === 0 ? "manual-task" : `manual-task-desc-${index}`} label="What participants do" required error={errorFor(index === 0 ? "manual-task" : `manual-task-desc-${index}`)}>
                      <Textarea autoGrow rows={2} maxLength={5000} value={task.description} onChange={(e) => updateTask(index, { description: e.target.value })} />
                    </Field>
                    <Field id={`manual-task-minutes-${index}`} label="Expected task time" hint="Optional." error={errorFor(`manual-task-minutes-${index}`)}>
                      <Input type="number" inputMode="numeric" min={1} max={180} step={1} unit="min" value={task.minutes} onChange={(e) => updateTask(index, { minutes: e.target.value })} />
                    </Field>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <Field id={`manual-task-materials-${index}`} label="Materials or code location" hint="Optional: repository, project path, or archive.">
                        <Input maxLength={600} value={task.materials} onChange={(e) => updateTask(index, { materials: e.target.value })} />
                      </Field>
                      <Field id={`manual-task-version-${index}`} label="Task version or revision" hint="Optional: release, branch, or commit.">
                        <Input maxLength={120} value={task.version} onChange={(e) => updateTask(index, { version: e.target.value })} />
                      </Field>
                    </div>
                  </fieldset>
                ))}
              </div>
              {tasks.length < MAX_TASKS && (
                  <Button type="button" variant="subtle" size="sm" className="self-start" disabled={saving} onClick={() => setTasks((current) => [...current, { key: `new-${Date.now()}-${current.length}`, title: "", description: "", minutes: "", materials: "", version: "" }])}>
                  <Plus aria-hidden /> Add task
                </Button>
              )}
              <p className="type-caption text-text-muted" aria-live="polite">
                {expectedTaskMinutes === 0
                  ? "No task times entered."
                  : `Recorded task time: ${expectedTaskMinutes} of ${form.sessionMinutes || "—"} minutes per participant.`}
              </p>
              {Number.isInteger(sessionMinutes) && expectedTaskMinutes > sessionMinutes && (
                <Notice id="manual-task-minutes-summary" kind="problem" tabIndex={-1}>
                  The assigned tasks total {expectedTaskMinutes} minutes, longer than this session. Shorten a task or increase the session length.
                </Notice>
              )}
              {form.design === "within-subjects" && tasks.length < form.conditions.length && (
                <Notice kind="note">
                  Participants will repeat a task across conditions; familiarity may affect the comparison.
                </Notice>
              )}
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
                {measureOptions.map((measure) => {
                  const choice = choiceFor(measure);
                  const compatible = Boolean(choice?.recipeByDesign[form.design]);
                  return (
                  <Checkbox
                    key={measure}
                    bordered
                    label={MEASURE_LABELS[measure] ?? measure}
                    description={choice && !compatible ? "No supported analysis for this design yet." : undefined}
                    disabled={saving || (Boolean(choice) && !compatible && !form.measures.includes(measure))}
                    checked={form.measures.includes(measure)}
                    onChange={() => toggleMeasure(measure)}
                  />
                ); })}
              </div>
              <Field id="manual-other-outcomes" label="Other outcomes" hint="Separate several with commas.">
                <Input placeholder="e.g. mental demand" value={other} maxLength={600} onChange={(e) => setOther(e.target.value)} />
              </Field>
              <div className="flex flex-col gap-2" aria-live="polite" aria-busy={lookup === "loading"}>
                {lookup === "loading" && <p className="type-caption text-text-muted">Checking available measures…</p>}
                {suggestions.map((choice) => (
                  <div key={choice.id} className="flex flex-wrap items-start justify-between gap-2">
                    <p className="min-w-0 flex-1 type-caption text-text-muted">{choice.description}{!choice.designCompatible && " No supported outcome analysis for this design."}</p>
                    <Button type="button" variant="outline" size="sm" aria-label={`Add ${choice.construct}`} disabled={!choice.designCompatible || saving || form.measures.length >= MAX_OUTCOMES || form.measures.includes(choice.construct)} onClick={() => {
                      set({ measures: [...new Set([...form.measures, choice.construct])] });
                      setOther(other.split(",").slice(1).join(",").trim());
                      document.getElementById("manual-other-outcomes")?.focus();
                    }}><Plus aria-hidden />Add {choice.construct}</Button>
                  </div>
                ))}
                {((lookup === "ready" && suggestions.length === 0) || lookup === "unavailable" || catalogError) && <p className="type-caption text-text-muted">Choose an available measure, or set up custom capture in the chat.</p>}
              </div>
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
