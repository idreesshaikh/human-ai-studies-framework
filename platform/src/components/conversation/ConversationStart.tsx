import { useState } from "react";
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

export function ConversationStart({ onUse }: { onUse: (text: string) => void }) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [design, setDesign] = useState("within-subjects");
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
    const lines = [
      "Here are the concrete study details I already know:",
      "Compare AI-assisted work with unassisted work.",
      `Use a ${design} design.`,
      measures.length > 0 ? `Measure ${measures.join(", ")}.` : "",
      participants.trim() ? `Plan for ${participants.trim()} participants.` : "",
      sessionMinutes.trim()
        ? `Run each session for ${sessionMinutes.trim()} minutes.`
        : "",
    ].filter(Boolean);
    onUse(lines.join(" "));
    setDetailsOpen(false);
  };

  return (
    <section data-agent="conversation-start" aria-label="Start the developer study setup" className="max-w-reading">
      <h2 className="type-section text-text">Describe the study in your own words</h2>
      <p className="mt-2 max-w-[52ch] type-body text-text-muted">
        Give me a complete brief if you have one, or start with the part you know. I’ll teach the
        design choices as we go and turn the decisions we keep into a runnable protocol.
      </p>

      <p
        data-agent="study-scope"
        className="mt-4 max-w-[58ch] border-l-2 border-accent pl-3 type-caption text-text-muted"
      >
        Students are supported when they are programming. Other study types belong outside this workspace.
      </p>

      <section className="mt-6 border-y border-border py-4" aria-labelledby="known-details-heading">
        <button
          type="button"
          className="flex w-full items-center justify-between gap-4 text-left"
          aria-expanded={detailsOpen}
          onClick={() => setDetailsOpen((open) => !open)}
        >
          <span>
            <span id="known-details-heading" className="type-control block text-text">
              Set the concrete details you already know
            </span>
            <span className="mt-0.5 block type-caption text-text-muted">
              Use controls for fixed choices; the assistant will reason through everything else.
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

      <p className="mt-4 max-w-[58ch] type-caption text-text-muted">
        Supported lane: comparative coding-task studies using TERN-captured developer activity. The protocol draft on the right is the record that will be validated before anything runs.
      </p>

      <div className="mt-6">
        <p className="type-caption text-text-muted">Try an example</p>
        <ul className="mt-2 divide-y divide-border overflow-hidden rounded-plate border border-border bg-surface">
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
        <p className="mt-2 type-caption text-text-muted">Examples fill the composer; nothing is sent until you press send.</p>
      </div>
    </section>
  );
}
