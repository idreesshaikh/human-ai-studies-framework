import { useState, type ReactNode } from "react";
import { Check, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

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
        <summary className="type-caption cursor-pointer text-center text-text-muted">Examples and study tools</summary>
        <p className="mt-3 type-caption text-text-muted">Supported: coding-task studies. Not for exams, classrooms or surveys.</p>
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
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-2 sm:col-span-2">
                <Label htmlFor="known-title">Study title</Label>
                <Input
                  id="known-title"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                />
              </div>

              <div className="flex flex-col gap-2 sm:col-span-2">
                <Label htmlFor="known-question">Research question</Label>
                <Input
                  id="known-question"
                  value={researchQuestion}
                  onChange={(event) => setResearchQuestion(event.target.value)}
                />
              </div>

              <div className="flex flex-col gap-2 sm:col-span-2">
                <Label htmlFor="known-profile">Who you are recruiting</Label>
                <Input
                  id="known-profile"
                  placeholder="e.g. novice developers"
                  value={profile}
                  onChange={(event) => setProfile(event.target.value)}
                />
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor="known-design">Study design</Label>
                <Select
                  id="known-design"
                  value={design}
                  onValueChange={setDesign}
                  options={DESIGN_OPTIONS}
                />
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor="known-participants">Planned participants</Label>
                <Input
                  id="known-participants"
                  type="number"
                  min={4}
                  placeholder="e.g. 12"
                  value={participants}
                  onChange={(event) => setParticipants(event.target.value)}
                />
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor="known-session">Session length</Label>
                <Input
                  id="known-session"
                  type="number"
                  min={15}
                  max={180}
                  placeholder="e.g. 45"
                  value={sessionMinutes}
                  onChange={(event) => setSessionMinutes(event.target.value)}
                  unit="min"
                  quantity
                />
              </div>

              <fieldset className="flex flex-col gap-2 sm:col-span-2">
                <legend className="type-label text-text">What should we capture?</legend>
                <div className="grid gap-2 sm:grid-cols-2">
                  {MEASURE_OPTIONS.map(([value, label]) => (
                    <label
                      key={value}
                      className="flex cursor-pointer items-center gap-2 rounded-control border border-border bg-surface px-3 py-2 transition-colors duration-fast hover:border-control-edge"
                    >
                      <input
                        type="checkbox"
                        className="size-4 accent-accent"
                        checked={measures.includes(value)}
                        onChange={() => toggleMeasure(value)}
                      />
                      <span className="type-caption text-text">{label}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
            </div>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <p className="max-w-reading type-caption text-text-muted">
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
        <p className="mt-4 type-caption text-text-muted">
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
        <p className="mt-2 type-caption text-text-muted">Edit the example, then send.</p>
      </details>
      </details>
    </section>
  );
}
