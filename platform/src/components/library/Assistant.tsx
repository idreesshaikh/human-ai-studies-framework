import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SegmentedControl, type SegmentOption } from "@/components/ui/segmented-control";
import { studyApi, OfflineError, type AssistantConfig } from "@/lib/studyApi";
import { cn } from "@/lib/cn";

/* The model tier, named for the trade the researcher is actually making rather
 * than as raw model names.
 *
 * It used to read Low / Medium / High, which collided head-on with the steer
 * dial in the conversation: two adjacent controls, both apparently setting
 * "how much assistance", in two different vocabularies, and neither saying
 * which. They govern completely different things. Steer is how much the
 * assistant DRIVES the design conversation; this is how much compute answers a
 * question in the library, which is a speed-against-depth trade and nothing
 * more. Naming it for speed and depth makes the two impossible to confuse. */
const TIERS: SegmentOption<string>[] = [
  { value: "mistral-small-latest", label: "Fast", hint: "Quickest answers, lightest model" },
  { value: "mistral-medium-latest", label: "Balanced", hint: "The default" },
  { value: "mistral-large-latest", label: "Deep", hint: "Most capable, slower" },
];

/* The grounded assistant (FR-LIT-4). It answers only from the study's papers
 * and *aggregate* data — never row-level participant events (FR-ETH-4, enforced
 * server-side) — and every claim carries a citation. First person for what the
 * platform did; the model tier is selectable (D32). With no key it degrades to
 * a calm notice, and every other surface keeps working. */

type ChatMsg = {
  role: "user" | "assistant";
  content: string;
  citations?: string[];
};

export function Assistant({ studyId }: { studyId: string }) {
  const [chat, setChat] = useState<ChatMsg[]>([]);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [config, setConfig] = useState<AssistantConfig | null>(null);
  const [model, setModel] = useState<string | undefined>(undefined);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let live = true;
    studyApi.assistantConfig(studyId).then((c) => {
      if (!live) return;
      setConfig(c);
      setModel((m) => (m && c.models.includes(m) ? m : c.defaultModel || undefined));
    });
    return () => {
      live = false;
    };
  }, [studyId]);

  async function ask() {
    const q = question.trim();
    if (!q || asking) return;
    const next = [...chat, { role: "user" as const, content: q }];
    setChat(next);
    setQuestion("");
    setAsking(true);
    setNote(null);
    try {
      const history = next.map((m) => ({ role: m.role, content: m.content }));
      const res = await studyApi.assistant(studyId, q, history.slice(0, -1), model);
      setChat((c) => [
        ...c,
        { role: "assistant", content: res.answer, citations: res.citations },
      ]);
    } catch (e) {
      setNote(
        e instanceof OfflineError
          ? e.message
          : String(e).includes("503")
            ? "The assistant needs MISTRAL_API_KEY set on the middleware. Every other surface works without it."
            : String(e),
      );
    } finally {
      setAsking(false);
      queueMicrotask(() => end.current?.scrollIntoView({ block: "end" }));
    }
  }

  return (
    <section className="flex h-full min-h-0 flex-col rounded-card border border-border bg-surface">
      <header className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3">
        <h3 className="type-subhead text-text">Assistant</h3>
        {config && config.models.length > 1 && model && (
          <SegmentedControl
            aria-label="Answer speed and depth"
            value={model}
            onChange={setModel}
            options={TIERS.filter((t) => config.models.includes(t.value))}
          />
        )}
        <span className="ml-auto type-caption text-text-muted">aggregates only</span>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-auto p-4">
        {chat.length === 0 && !note && (
          <p className="type-body text-text-muted">
            Ask about the papers, the protocol, or the aggregate data. Answers
            are grounded in what I can retrieve, and always cited.
          </p>
        )}
        {chat.map((m, i) => (
          <div
            key={i}
            className={cn(
              "flex flex-col gap-1",
              m.role === "user" ? "items-end" : "items-start",
            )}
          >
            <div
              className={cn(
                "max-w-[46ch] whitespace-pre-wrap rounded-card px-3 py-2 type-body",
                m.role === "user"
                  ? "border border-border bg-zone-9 text-text"
                  : "border border-border bg-surface text-text",
              )}
            >
              {m.content}
            </div>
            {m.citations && m.citations.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {m.citations.map((c) => (
                  <span
                    key={c}
                    className="rounded-chip border border-accent px-2 py-0.5 type-legend text-accent"
                  >
                    {c}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {asking && <p className="type-body text-text-muted">thinking…</p>}
        {note && (
          <p className="rounded-input border border-border bg-bg p-3 type-body text-text-muted">
            {note}
          </p>
        )}
        <div ref={end} />
      </div>

      <form
        className="flex items-end gap-2 border-t border-border p-3"
        onSubmit={(e) => {
          e.preventDefault();
          ask();
        }}
      >
        <Input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question…"
          aria-label="Ask the assistant"
          className="flex-1"
        />
        <Button type="submit" size="icon" disabled={asking} aria-label="Ask">
          <Send aria-hidden />
        </Button>
      </form>
    </section>
  );
}
