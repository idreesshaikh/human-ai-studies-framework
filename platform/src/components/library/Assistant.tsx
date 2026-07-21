import { useEffect, useRef, useState } from "react";
import { Send, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { studyApi, OfflineError, type AssistantConfig } from "@/lib/studyApi";
import { cn } from "@/lib/cn";

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
        <Sparkles className="size-4 text-accent" aria-hidden />
        <h3 className="text-sm font-medium text-text">Assistant</h3>
        {config && config.models.length > 1 && (
          <select
            className="rounded-input border border-border bg-bg px-2 py-1 text-xs text-text"
            value={model ?? ""}
            onChange={(e) => setModel(e.target.value)}
            aria-label="Assistant model"
          >
            {config.models.map((m) => (
              <option key={m} value={m}>
                {m.replace("mistral-", "").replace("-latest", "")}
              </option>
            ))}
          </select>
        )}
        <span className="ml-auto text-xs text-text-muted">aggregates only</span>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-auto p-4">
        {chat.length === 0 && !note && (
          <p className="text-sm text-text-muted">
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
                "max-w-[46ch] whitespace-pre-wrap rounded-card px-3 py-2 text-sm",
                m.role === "user"
                  ? "bg-accent text-accent-contrast"
                  : "border border-border bg-bg text-text",
              )}
            >
              {m.content}
            </div>
            {m.citations && m.citations.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {m.citations.map((c) => (
                  <span
                    key={c}
                    className="rounded-chip bg-accent-soft px-2 py-0.5 font-mono text-xs text-accent"
                  >
                    {c}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {asking && <p className="text-sm text-text-muted">thinking…</p>}
        {note && (
          <p className="rounded-input border border-border bg-bg p-3 text-sm text-text-muted">
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
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about the papers, protocol, or aggregate data…"
          aria-label="Ask the assistant"
          className="min-h-9 flex-1 rounded-input border border-border-strong bg-bg px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
        />
        <Button type="submit" size="icon" disabled={asking} aria-label="Ask">
          <Send aria-hidden />
        </Button>
      </form>
    </section>
  );
}
