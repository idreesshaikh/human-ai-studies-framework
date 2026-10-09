import { useState, type ReactNode } from "react";
import { Field } from "@/components/ui/field";
import { Check, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";

/* Empty state for a new developer study. The supported lane is stated before
 * anyone commits to a long conversation, while the small known-facts intake
 * lets deterministic details jump straight into the same assistant thread. */

const OPENINGS = [
  "Does an AI assistant change how much code developers rewrite before they ship?",
  "Compare how long debugging takes with and without an AI pair.",
  "Do developers review AI-written code as carefully as code they wrote themselves?",
];

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

export function ConversationStart({
  onUse,
  onEnterManually,
  composer,
}: {
  onUse: (text: string) => void;
  onEnterManually?: () => void;
  composer: ReactNode;
}) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [design, setDesign] = useState("within-subjects");
  const [title, setTitle] = useState("");
  const [researchQuestion, setResearchQuestion] = useState("");
  const [profile, setProfile] = useState("");
  const [participants, setParticipants] = useState("");
  const [sessionMinutes, setSessionMinutes] = useState("");
  const [measures, setMeasures] = useState<string[]>([
    "task completion time",
    "solution correctness",
  ]);

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
      "Compare AI-assisted work with unassisted work.",
      `Use a ${design} design.`,
      measures.length > 0 ? `Measure ${measures.join(", ")}.` : "",
      participants.trim() ? `N = ${participants.trim()}` : "",
      sessionMinutes.trim() ? `Duration: ${sessionMinutes.trim()} minutes` : "",
    ].filter(Boolean);
    onUse(lines.join("\n"));
    setDetailsOpen(false);
  };

  return (
    <section aria-label="Start the developer study setup" className="max-w-reading">
      <h2 className="type-title text-center text-text">What would you like to study?</h2>
      <div className="mt-6">{composer}</div>

      <details className="mt-4">
        <summary className="type-caption cursor-pointer text-center text-text-muted">Start from details or an example</summary>
        <p className="mt-3 type-note text-text-muted">Supported: coding-task studies. Not for exams, classrooms or surveys.</p>
      <section className="mt-4 border-y border-border py-4" aria-labelledby="known-details-heading">
        <button
          type="button"
          className="flex w-full items-center justify-between gap-4 text-left"
          aria-expanded={detailsOpen}
          onClick={() => setDetailsOpen((open) => !open)}
        >
          <span>
            <span id="known-details-heading" className="type-control block text-text">
              Add known details
            </span>
          </span>
          <ChevronDown
            className={`size-4 shrink-0 text-text-muted transition-transform duration-standard ${detailsOpen ? "rotate-180" : ""}`}
            aria-hidden
          />
        </button>

        {detailsOpen && (
          <div className="mt-4 border-t border-border pt-4">
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
                <Select value={design} onValueChange={setDesign} options={DESIGN_OPTIONS} />
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
              <p className="max-w-reading type-note text-text-muted">
                These details will be placed in the chat for the assistant to review, explain, and add to the protocol.
              </p>
              <Button type="button" size="sm" onClick={addKnownDetails}>
                <Check aria-hidden />
                Add to chat
              </Button>
            </div>
          </div>
        )}
      </section>

      {onEnterManually && (
        <p className="mt-4 type-note text-text-muted">
          Already have a design?{" "}
          <button type="button" className="text-accent underline-offset-2 hover:underline" onClick={onEnterManually}>
            Enter the protocol details directly
          </button>
        </p>
      )}

      <details className="mt-5">
        <summary className="type-caption cursor-pointer text-text-muted">Try an example</summary>
        <ul className="mt-2 divide-y divide-border">
          {OPENINGS.map((text) => (
            <li key={text}>
              <button
                type="button"
                onClick={() => onUse(text)}
                className="type-body group flex w-full items-start gap-2.5 px-3 py-3 text-left text-text transition-colors duration-fast hover:bg-zone-9"
              >
                <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-dot bg-border-strong transition-colors duration-fast group-hover:bg-accent" />
                <span>{text}</span>
              </button>
            </li>
          ))}
        </ul>
        <p className="mt-2 type-note text-text-muted">Edit the example, then send.</p>
      </details>
      </details>
    </section>
  );
}
