import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Disclosure } from "@/components/ui/disclosure";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

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
  ["task completion time", "Task time"],
  ["solution correctness", "Correctness"],
  ["cognitive load", "Cognitive load"],
  ["code comprehension", "Code comprehension"],
] as const;

export function KnownDetails({ onUse }: { onUse: (text: string) => void }) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [design, setDesign] = useState("");
  const [title, setTitle] = useState("");
  const [researchQuestion, setResearchQuestion] = useState("");
  const [profile, setProfile] = useState("");
  const [participants, setParticipants] = useState("");
  const [sessionMinutes, setSessionMinutes] = useState("");
  const [measures, setMeasures] = useState<string[]>([]);

  const toggleMeasure = (value: string) => {
    setMeasures((current) =>
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value],
    );
  };

  const addKnownDetails = () => {
    // One labelled line per fact the researcher filled in, so the intake parser
    // reads each field exactly and nothing blank is guessed.
    const lines = [
      "Here are the concrete study details I already know:",
      title.trim() ? `Title: ${title.trim()}` : "",
      researchQuestion.trim() ? `Research question: ${researchQuestion.trim()}` : "",
      profile.trim() ? `Participants: ${profile.trim()}` : "",
      design ? `Use a ${design} design.` : "",
      measures.length > 0 ? `Measure ${measures.join(", ")}.` : "",
      participants.trim() ? `N = ${participants.trim()}` : "",
      sessionMinutes.trim() ? `Duration: ${sessionMinutes.trim()} minutes` : "",
    ].filter(Boolean);
    onUse(lines.join("\n"));
    setDetailsOpen(false);
  };

  return (
    <Disclosure
      summary="Add known details"
      open={detailsOpen}
      onOpenChange={setDetailsOpen}
      buttonClassName="type-control py-3"
    >
      <div className="pb-4">
        <div className="form-grid">
          <Field id="known-title" label="Study title" className="span-2">
            <Input value={title} onChange={(event) => setTitle(event.target.value)} />
          </Field>

          <Field id="known-question" label="Research question" className="span-2">
            <Input value={researchQuestion} onChange={(event) => setResearchQuestion(event.target.value)} />
          </Field>

          <Field id="known-profile" label="Who you are recruiting" className="span-2">
            <Input placeholder="e.g. novice developers" value={profile} onChange={(event) => setProfile(event.target.value)} />
          </Field>

          <Field id="known-design" label="Study design">
            <Select value={design || undefined} onValueChange={setDesign} options={DESIGN_OPTIONS} />
          </Field>

          <Field id="known-participants" label="Planned participants" hint="At least 4.">
            <Input type="number" inputMode="numeric" min={4} stepper quantity placeholder="e.g. 12" value={participants} onChange={(event) => setParticipants(event.target.value)} />
          </Field>

          <Field id="known-session" label="Session length" hint="Minutes, 15 to 180.">
            <Input type="number" inputMode="numeric" min={15} max={180} step={5} stepper unit="min" quantity placeholder="e.g. 45" value={sessionMinutes} onChange={(event) => setSessionMinutes(event.target.value)} />
          </Field>

          <fieldset className="form-section span-2">
            <legend className="type-label text-text">What should we capture?</legend>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {MEASURE_OPTIONS.map(([value, label]) => (
                <Checkbox
                  key={value}
                  bordered
                  label={label}
                  checked={measures.includes(value)}
                  onChange={() => toggleMeasure(value)}
                />
              ))}
            </div>
          </fieldset>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <Button type="button" size="sm" onClick={addKnownDetails}>
            Add to chat
          </Button>
        </div>
      </div>
    </Disclosure>
  );
}
