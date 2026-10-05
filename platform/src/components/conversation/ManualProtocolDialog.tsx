import { useRef, useState, type FormEvent } from "react";
import { Loader2, Plus, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { asList, asRecord, asText } from "@/lib/compiler";
import {
  conversationApi,
  type ManualProtocolFields,
} from "@/lib/conversationApi";
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
  const [form, setForm] = useState(() =>
    fromProtocol(protocol, acceptedMeasures),
  );
  const outcomesError = useRef<HTMLParagraphElement>(null);
  const [measureError, setMeasureError] = useState("");
  const [other, setOther] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const set = (patch: Partial<typeof form>) =>
    setForm((current) => ({ ...current, ...patch }));
  const [measureOptions] = useState(() => [
    ...new Set([...MEASURE_OPTIONS, ...form.measures]),
  ]);

  const toggleMeasure = (measure: string) =>
    set({
      measures: form.measures.includes(measure)
        ? form.measures.filter((m) => m !== measure)
        : [...form.measures, measure],
    });

  async function submit(event: FormEvent) {
    event.preventDefault();
    const measures = [
      ...new Set([
        ...form.measures,
        ...other
          .split(",")
          .map((m) => m.trim())
          .filter(Boolean),
      ]),
    ];
    if (measures.length < 1 || measures.length > 6) {
      setMeasureError("Choose between one and six outcomes.");
      requestAnimationFrame(() => {
        outcomesError.current?.scrollIntoView({ block: "center" });
        outcomesError.current?.focus();
      });
      return;
    }
    setMeasureError("");
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
      setError(
        e instanceof Error && e.message
          ? e.message
          : "Could not save the protocol details.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogContent
        scrollable={false}
        className="w-[min(40rem,calc(100vw-2rem))]"
      >
        <div className="shrink-0 border-b border-border pb-4 pr-10">
          <DialogTitle>Enter protocol details</DialogTitle>
          <DialogDescription>
            These details replace earlier decisions. Review and approve the
            draft before running the study.
          </DialogDescription>
        </div>
        <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
          <div
            className="-mx-1 min-h-0 flex-1 overflow-y-auto px-1 py-4"
            role="region"
            aria-label="Protocol fields"
          >
            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="manual-title">Study name</Label>
                <Input
                  id="manual-title"
                  className="h-10"
                  required
                  minLength={3}
                  maxLength={160}
                  value={form.title}
                  onChange={(e) => set({ title: e.target.value })}
                />
              </div>
              <fieldset className="flex flex-col gap-2">
                <legend className="type-label text-text">
                  Research questions
                </legend>
                {form.researchQuestions.map((question, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <Textarea
                      className="min-h-20"
                      aria-label={`Research question ${i + 1}`}
                      required
                      minLength={10}
                      maxLength={500}
                      rows={2}
                      value={question}
                      onChange={(e) =>
                        set({
                          researchQuestions: form.researchQuestions.map(
                            (q, j) => (j === i ? e.target.value : q),
                          ),
                        })
                      }
                    />
                    {i > 0 && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        aria-label={`Remove research question ${i + 1}`}
                        onClick={() =>
                          set({
                            researchQuestions: form.researchQuestions.filter(
                              (_, j) => j !== i,
                            ),
                          })
                        }
                      >
                        <X aria-hidden />
                      </Button>
                    )}
                  </div>
                ))}
                {form.researchQuestions.length < 6 && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="self-start"
                    onClick={() =>
                      set({
                        researchQuestions: [...form.researchQuestions, ""],
                      })
                    }
                  >
                    <Plus aria-hidden />
                    Add research question
                  </Button>
                )}
              </fieldset>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="manual-design">Study design</Label>
                  <Select
                    id="manual-design"
                    aria-describedby="manual-design-hint"
                    value={form.design}
                    onValueChange={(v) => set({ design: v as Design })}
                    options={DESIGN_OPTIONS}
                  />
                  <p
                    id="manual-design-hint"
                    className="type-caption text-text-muted"
                  >
                    {form.design === "within-subjects"
                      ? "Both conditions per participant; order is counterbalanced."
                      : "One condition per participant."}
                  </p>
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="manual-planned">Planned participants</Label>
                  <Input
                    id="manual-planned"
                    className="h-10"
                    type="number"
                    required
                    min={4}
                    max={1000}
                    value={form.plannedParticipants}
                    onChange={(e) =>
                      set({ plannedParticipants: e.target.value })
                    }
                    quantity
                  />
                </div>
                {form.conditions.map((condition, i) => (
                  <div key={i} className="flex flex-col gap-2">
                    <Label htmlFor={`manual-condition-${i}`}>
                      Condition {i + 1}
                    </Label>
                    <Input
                      id={`manual-condition-${i}`}
                      className="h-10"
                      required
                      maxLength={80}
                      placeholder={
                        i === 0 ? "e.g. AI-assisted" : "e.g. Unassisted"
                      }
                      value={condition}
                      onChange={(e) =>
                        set({
                          conditions: form.conditions.map((c, j) =>
                            j === i ? e.target.value : c,
                          ),
                        })
                      }
                    />
                  </div>
                ))}
                <div className="flex flex-col gap-2">
                  <Label htmlFor="manual-participants">Who takes part</Label>
                  <Input
                    id="manual-participants"
                    className="h-10"
                    required
                    minLength={2}
                    maxLength={240}
                    placeholder="e.g. Python developers"
                    value={form.participantDescription}
                    onChange={(e) =>
                      set({ participantDescription: e.target.value })
                    }
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="manual-minutes">Session length</Label>
                  <Input
                    id="manual-minutes"
                    className="h-10"
                    aria-describedby="manual-minutes-hint"
                    type="number"
                    required
                    min={15}
                    max={180}
                    value={form.sessionMinutes}
                    onChange={(e) => set({ sessionMinutes: e.target.value })}
                    unit="min"
                    quantity
                  />
                  <p
                    id="manual-minutes-hint"
                    className="type-caption text-text-muted"
                  >
                    Minutes per task block.
                  </p>
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="manual-task">Task</Label>
                <Textarea
                  id="manual-task"
                  className="min-h-20"
                  rows={2}
                  required
                  minLength={8}
                  maxLength={500}
                  placeholder="What participants do in a session."
                  value={form.taskDescription}
                  onChange={(e) => set({ taskDescription: e.target.value })}
                />
              </div>
              <fieldset
                className="flex flex-col gap-2"
                aria-describedby={measureError ? "outcomes-error" : undefined}
              >
                <legend className="type-label text-text">Outcomes</legend>
                {measureError && (
                  <p
                    id="outcomes-error"
                    ref={outcomesError}
                    tabIndex={-1}
                    role="alert"
                    className="type-caption text-critical"
                  >
                    {measureError}
                  </p>
                )}
                <div className="grid gap-2 sm:grid-cols-2">
                  {measureOptions.map((measure) => (
                    <label
                      key={measure}
                      className="flex min-h-11 cursor-pointer items-center gap-2 rounded-control border border-border bg-surface px-3 py-2 transition-colors duration-fast hover:border-control-edge"
                    >
                      <input
                        type="checkbox"
                        className="checkbox"
                        checked={form.measures.includes(measure)}
                        onChange={() => toggleMeasure(measure)}
                      />
                      <span className="type-caption text-text">{measure}</span>
                    </label>
                  ))}
                </div>
                <details>
                  <summary className="type-caption cursor-pointer text-text-muted">
                    Other outcomes
                  </summary>
                  <Input
                    className="mt-2 h-10"
                    aria-label="Other outcomes"
                    placeholder="Comma-separated outcomes"
                    value={other}
                    onChange={(e) => setOther(e.target.value)}
                  />
                </details>
              </fieldset>
            </div>
          </div>
          <div className="shrink-0 border-t border-border pt-4">
            {error && <Notice kind="problem">{error}</Notice>}
            <div className="flex justify-end gap-2" aria-busy={saving}>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onClose}
              >
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={saving}>
                {saving && (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                )}
                {saving ? "Saving…" : "Save draft"}
              </Button>
            </div>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
