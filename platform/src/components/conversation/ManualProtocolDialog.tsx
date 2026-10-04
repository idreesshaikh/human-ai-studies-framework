import { useState, type FormEvent } from "react";
import { Loader2, Plus, X } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { asList, asRecord, asText } from "@/lib/compiler";
import { conversationApi, type ManualProtocolFields } from "@/lib/conversationApi";

const DESIGN_OPTIONS = [
  { value: "within-subjects", label: "Within-subjects", hint: "Each developer does both conditions." },
  { value: "between-subjects", label: "Between-subjects", hint: "Each developer does one condition." },
];

const MEASURE_OPTIONS = [
  "task completion time",
  "solution correctness",
  "cognitive load",
  "code comprehension",
];

type Design = ManualProtocolFields["design"];

function fromProtocol(protocol: Record<string, unknown> = {}) {
  const participants = asRecord(protocol.participants);
  const session = asRecord(protocol.session);
  const conditions = asList(protocol.conditions).map(asText);
  const questions = asList(protocol.researchQuestions).map((rq) => asText(asRecord(rq).text)).filter(Boolean);
  return {
    title: asText(asRecord(protocol.study).title),
    researchQuestions: questions.length ? questions : [""],
    design: (participants.design === "between-subjects" ? "between-subjects" : "within-subjects") as Design,
    conditions: [conditions[0] ?? "", conditions[1] ?? ""],
    participantDescription: asText(participants.description),
    plannedParticipants: asText(participants.planned),
    taskDescription:
      asText(asRecord(asList(protocol.tasks)[0]).description) || asText(session.taskDescription),
    sessionMinutes: asText(session.durationMinutes),
    measures: asList(protocol.measures).map(asText).filter(Boolean),
  };
}

export function ManualProtocolDialog({
  studyId,
  protocol,
  onClose,
  onEntered,
}: {
  studyId: string;
  protocol?: Record<string, unknown>;
  onClose: () => void;
  onEntered: () => void;
}) {
  const [form, setForm] = useState(() => fromProtocol(protocol));
  const [other, setOther] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const set = (patch: Partial<typeof form>) => setForm((current) => ({ ...current, ...patch }));
  const [measureOptions] = useState(() => [...new Set([...MEASURE_OPTIONS, ...form.measures])]);

  const toggleMeasure = (measure: string) =>
    set({
      measures: form.measures.includes(measure)
        ? form.measures.filter((m) => m !== measure)
        : [...form.measures, measure],
    });

  async function submit(event: FormEvent) {
    event.preventDefault();
    const measures = [
      ...new Set([...form.measures, ...other.split(",").map((m) => m.trim()).filter(Boolean)]),
    ];
    if (measures.length < 1 || measures.length > 6) {
      setError("Choose between one and six outcomes.");
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

  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="w-[min(40rem,calc(100vw-2rem))]">
        <DialogTitle>Enter protocol details</DialogTitle>
        <DialogDescription>
          Fill in a design you already have. The details replace earlier decisions and go through the
          same compiler check and approval as the conversation.
        </DialogDescription>
        <form onSubmit={submit} className="mt-4 flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="manual-title">Study name</Label>
            <Input id="manual-title" required minLength={3} maxLength={160} value={form.title} onChange={(e) => set({ title: e.target.value })} />
          </div>
          <fieldset className="flex flex-col gap-2">
            <legend className="type-label text-text">Research questions</legend>
            {form.researchQuestions.map((question, i) => (
              <div key={i} className="flex items-start gap-2">
                <Textarea
                  aria-label={`Research question ${i + 1}`}
                  required
                  minLength={10}
                  maxLength={500}
                  rows={2}
                  value={question}
                  onChange={(e) => set({ researchQuestions: form.researchQuestions.map((q, j) => (j === i ? e.target.value : q)) })}
                />
                {i > 0 && (
                  <Button type="button" variant="ghost" size="sm" aria-label={`Remove research question ${i + 1}`} onClick={() => set({ researchQuestions: form.researchQuestions.filter((_, j) => j !== i) })}>
                    <X aria-hidden />
                  </Button>
                )}
              </div>
            ))}
            {form.researchQuestions.length < 6 && (
              <Button type="button" variant="ghost" size="sm" className="self-start" onClick={() => set({ researchQuestions: [...form.researchQuestions, ""] })}>
                <Plus aria-hidden />
                Add research question
              </Button>
            )}
          </fieldset>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="manual-design">Study design</Label>
              <Select id="manual-design" value={form.design} onValueChange={(v) => set({ design: v as Design })} options={DESIGN_OPTIONS} />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="manual-planned">Planned participants</Label>
              <Input id="manual-planned" type="number" required min={4} max={1000} value={form.plannedParticipants} onChange={(e) => set({ plannedParticipants: e.target.value })} quantity />
            </div>
            {form.conditions.map((condition, i) => (
              <div key={i} className="flex flex-col gap-2">
                <Label htmlFor={`manual-condition-${i}`}>Condition {i + 1}</Label>
                <Input
                  id={`manual-condition-${i}`}
                  required
                  maxLength={80}
                  placeholder={i === 0 ? "e.g. AI-assisted" : "e.g. Unassisted"}
                  value={condition}
                  onChange={(e) => set({ conditions: form.conditions.map((c, j) => (j === i ? e.target.value : c)) })}
                />
              </div>
            ))}
            <div className="flex flex-col gap-2">
              <Label htmlFor="manual-participants">Participants</Label>
              <Input id="manual-participants" required minLength={2} maxLength={240} placeholder="e.g. novice Python developers" value={form.participantDescription} onChange={(e) => set({ participantDescription: e.target.value })} />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="manual-minutes">Session length</Label>
              <Input id="manual-minutes" type="number" required min={15} max={180} value={form.sessionMinutes} onChange={(e) => set({ sessionMinutes: e.target.value })} unit="min" quantity />
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="manual-task">Task</Label>
            <Textarea id="manual-task" required minLength={8} maxLength={500} placeholder="What participants do in a session." value={form.taskDescription} onChange={(e) => set({ taskDescription: e.target.value })} />
          </div>
          <fieldset className="flex flex-col gap-2">
            <legend className="type-label text-text">Outcomes</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {measureOptions.map((measure) => (
                <label key={measure} className="flex cursor-pointer items-center gap-2 rounded-control border border-border bg-surface px-3 py-2 transition-colors duration-fast hover:border-control-edge">
                  <input type="checkbox" className="size-4 accent-accent" checked={form.measures.includes(measure)} onChange={() => toggleMeasure(measure)} />
                  <span className="type-caption text-text">{measure}</span>
                </label>
              ))}
            </div>
            <Input aria-label="Other outcomes" placeholder="Other outcomes, comma-separated" value={other} onChange={(e) => setOther(e.target.value)} />
          </fieldset>
          {error && <Notice kind="problem">{error}</Notice>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={saving}>
              {saving && <Loader2 className="size-4 animate-spin" aria-hidden />}
              Compile details
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
