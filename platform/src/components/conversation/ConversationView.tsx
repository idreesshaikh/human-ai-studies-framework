import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StreamingTurn } from "./StreamingTurn";
import { DraftRail } from "./DraftRail";
import { RecommenderRail } from "./RecommenderRail";
import { FinishReview } from "./FinishReview";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { compileAll } from "@/lib/compiler";
import { openingTurn, respondTo } from "@/lib/designStub";
import type { Recommendation } from "@/lib/types";
import {
  conversationApi,
  loadConversation,
  type CompileResult,
} from "@/lib/conversationApi";
import { evolutionStore } from "@/lib/evolutionStub";
import { studyApi } from "@/lib/studyApi";
import { cn } from "@/lib/cn";
import type { DesignMove, Turn } from "@/lib/types";

const FEEDBACK_CUES = [
  "it would be better",
  "i wish",
  "the platform should",
  "confusing",
  "hard to",
  "frustrating",
  "too many clicks",
  "couldn't find",
  "why doesn't",
  "annoying",
  "unclear",
];

function readsAsFeedback(text: string): boolean {
  const low = text.toLowerCase();
  return FEEDBACK_CUES.some((c) => low.includes(c));
}

export function ConversationView({
  studyId = "study",
  /** Static previews stay on the deterministic stub only. */
  stubOnly = false,
}: {
  studyId?: string;
  stubOnly?: boolean;
}) {
  const [turns, setTurns] = useState<Turn[]>(() => [openingTurn()]);
  const [input, setInput] = useState("");
  const [addedRefs, setAddedRefs] = useState<Set<string>>(new Set());
  const [markedTurns, setMarkedTurns] = useState<Set<string>>(new Set());
  const [live, setLive] = useState(!stubOnly);
  const [busy, setBusy] = useState(false);
  /* The reply's prose while it streams; null once the real turn lands. */
  const [streamingText, setStreamingText] = useState<string | null>(null);
  const [compileResult, setCompileResult] = useState<CompileResult | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);
  const [showFinish, setShowFinish] = useState(false);
  const [showDraft, setShowDraft] = useState(false);
  // Right rail toggles between the protocol draft (primary) and the surfaced
  // literature (secondary). The draft is the study's document of record, so it
  // leads; the recommender is one toggle away.
  const [rail, setRail] = useState<"papers" | "draft">("draft");
  const threadEnd = useRef<HTMLDivElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);

  // The composer grows with what's typed instead of clipping or scrolling
  // inside a fixed single row — capped so a very long message still scrolls
  // rather than pushing the send button off-screen.
  const growComposer = useCallback(() => {
    const el = composer.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, []);

  useEffect(() => {
    growComposer();
  }, [input, growComposer]);

  useEffect(() => {
    let cancelled = false;
    loadConversation(studyId, stubOnly).then((t) => {
      if (!cancelled) {
        setTurns(t);
        setLive(!stubOnly);
      }
    }).catch(() => {
      if (!cancelled) {
        setTurns([openingTurn()]);
        setLive(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [studyId, stubOnly]);

  const allMoves: DesignMove[] = useMemo(
    () => turns.flatMap((t) => t.moves),
    [turns],
  );
  const clientDraft = useMemo(() => compileAll(allMoves), [allMoves]);

  // The literature the conversation has surfaced, de-duplicated by ref, newest
  // turns first — the recommender rail's source. Refreshes as turns arrive.
  const recommendations = useMemo<Recommendation[]>(() => {
    const seen = new Set<string>();
    const out: Recommendation[] = [];
    for (const t of [...turns].reverse()) {
      for (const r of t.recommendations) {
        if (!seen.has(r.ref)) {
          seen.add(r.ref);
          out.push(r);
        }
      }
    }
    return out;
  }, [turns]);

  const refreshCompile = useCallback(async () => {
    if (!live || stubOnly) return;
    try {
      const result = await conversationApi.compile(studyId);
      setCompileResult(result);
    } catch {
      setCompileResult(null);
    }
  }, [live, stubOnly, studyId]);

  useEffect(() => {
    if (live && !stubOnly) void refreshCompile();
  }, [allMoves, live, stubOnly, refreshCompile]);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;

    // "finish" / "wrap up" / "done" opens the protocol-review moment rather
    // than sending a turn — the researcher is signalling they're ready to
    // compile, not asking another question.
    if (/^\s*(finish|wrap up|wrap-up|done|i'?m done|that'?s it)\b/i.test(text)) {
      setInput("");
      await refreshCompile();
      setShowFinish(true);
      return;
    }

    // Optimistic: show the researcher's message and clear the composer
    // immediately — before any network/LLM round-trip — so the thread never
    // sits with the box full while the model "thinks". The pending id is
    // swapped for the server-assigned researcher turn once the reply lands
    // (the real id is what feedback-marking keys on).
    const pendingId = `pending-${Date.now()}-${turns.length}`;
    const researcherTurn: Turn = {
      turnId: pendingId,
      role: "researcher",
      author: "You",
      text,
      moves: [],
      recommendations: [],
    };
    setTurns((prev) => [...prev, researcherTurn]);
    setInput("");
    setBusy(true);
    const scrollDown = () =>
      queueMicrotask(() => threadEnd.current?.scrollIntoView({ block: "end" }));
    scrollDown();

    try {
      if (live && !stubOnly) {
        // sendTurn returns [researcher(server id), platform]; replace our
        // optimistic turn with the server pair so ids reconcile without a
        // duplicated message.
        // Streamed: the reply's prose appears as the model writes it, so the
        // thread is alive instead of blank for the whole round-trip. The
        // streamed text is presentation only — the resolved turns are the
        // same ones the blocking call returns, and replace it wholesale.
        setStreamingText("");
        const appended = await conversationApi.sendTurnStreaming(
          studyId,
          text,
          "You",
          (fragment) => setStreamingText((prev) => prev + fragment),
        );
        setStreamingText(null);
        setTurns((prev) => [
          ...prev.filter((t) => t.turnId !== pendingId),
          ...appended.turns,
        ]);
      } else {
        setTurns((prev) => [...prev, respondTo(text)]);
      }
      scrollDown();
    } catch {
      // Offline fallback: keep the message we already showed, answer from the
      // built-in assistant, and flip to stub mode until the server returns.
      setTurns((prev) => [...prev, respondTo(text)]);
      setLive(false);
      setNote("You're offline — replies are coming from the built-in assistant until the connection returns.");
      scrollDown();
    } finally {
      setStreamingText(null);
      setBusy(false);
    }
  }

  function decide(moveId: string, status: "accepted" | "rejected") {
    setTurns((prev) =>
      prev.map((t) => ({
        ...t,
        moves: t.moves.map((m) =>
          m.moveId === moveId ? { ...m, status } : m,
        ),
      })),
    );
    if (live && !stubOnly) {
      conversationApi.decide(studyId, moveId, status).catch(() => {});
    }
  }

  async function addPaper(ref: string) {
    // Optimistic: mark it added immediately so the card settles.
    setAddedRefs((prev) => new Set(prev).add(ref));
    // Offline previews stay local-only — there's no study to write to.
    if (!live || stubOnly) return;
    const rec = turns
      .flatMap((t) => t.recommendations)
      .find((r) => r.ref === ref);
    try {
      // Actually ingest it into the study's Library, keeping the match reason.
      await studyApi.addPaperFromMatch(studyId, ref, rec?.matchReason ?? "");
    } catch {
      // Roll the flag back so the researcher can retry — silent success on a
      // no-op was the old bug.
      setAddedRefs((prev) => {
        const next = new Set(prev);
        next.delete(ref);
        return next;
      });
      setNote("Couldn't add that paper to your library — check your connection and try again.");
    }
  }

  async function applyDraft() {
    if (!compileResult?.valid || applying) return;
    setApplying(true);
    try {
      await conversationApi.approve(studyId, compileResult.compilationId);
      setApplied(true);
      setNote("Draft applied to the protocol.");
      await refreshCompile();
    } catch {
      setNote("Couldn't apply the draft — check your connection and try again.");
    } finally {
      setApplying(false);
    }
  }

  function markFeedback(turn: Turn, seq: number, note: string, kind: string) {
    evolutionStore.markFeedback({
      studyId,
      turnId: turn.turnId,
      seq,
      note,
      kind,
    });
    setMarkedTurns((prev) => new Set(prev).add(turn.turnId));
  }

  return (
    <div
      data-agent="conversation"
      className="grid h-full grid-cols-1 lg:grid-cols-[1fr_440px]"
    >
      <section className="flex h-full min-h-0 flex-col">
        <div className="min-h-0 flex-1 space-y-6 overflow-auto p-4 sm:p-6">
          {turns.map((t, i) => (
            <StreamingTurn
              key={t.turnId}
              turn={t}
              onDecide={decide}
              feedback={
                t.role === "researcher"
                  ? {
                      suggested: readsAsFeedback(t.text),
                      marked: markedTurns.has(t.turnId),
                      onMark: (note, kind) => markFeedback(t, i, note, kind),
                    }
                  : undefined
              }
            />
          ))}
          {busy && live && !stubOnly && (
            <div className="flex flex-col items-start gap-3" data-agent="conversation-thinking">
              <div className="max-w-[46ch] animate-in fade-in rounded-card border border-border bg-surface px-4 py-3 text-sm duration-entrance">
                <span className="mb-1 block text-xs text-text-muted opacity-70">
                  Platform
                </span>
                {streamingText ? (
                  /* The reply as it is being written. Live for a screen
                   * reader too, but polite — it must not interrupt. */
                  <span
                    className="whitespace-pre-wrap text-text"
                    aria-live="polite"
                    data-agent="conversation-streaming"
                  >
                    {streamingText}
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 animate-pulse text-text-muted">
                    <span className="size-1.5 rounded-full bg-text-muted" />
                    <span className="size-1.5 rounded-full bg-text-muted" />
                    <span className="size-1.5 rounded-full bg-text-muted" />
                  </span>
                )}
              </div>
            </div>
          )}
          <div ref={threadEnd} />
        </div>

        {note && (
          <p className="border-t border-border bg-surface px-4 py-2 text-xs text-text-muted sm:px-6">
            {note}
          </p>
        )}

        <form
          data-agent="conversation-composer"
          className="flex items-end gap-2 border-t border-border-strong bg-surface p-3 sm:p-4"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <span
            aria-hidden
            className="select-none self-stretch pt-2.5 font-mono text-base font-medium text-accent hidden sm:inline"
          >
            &gt;
          </span>
          <textarea
            ref={composer}
            className="min-h-11 max-h-40 flex-1 resize-none overflow-y-auto rounded-input border border-border-strong bg-bg px-3 py-2 font-mono text-sm text-text focus-visible:border-accent"
            placeholder="What do you want to find out?"
            value={input}
            rows={1}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            aria-label="Message the design assistant"
          />
          <Button
            type="submit"
            size="icon"
            data-agent="conversation-send"
            aria-label="Send"
            disabled={busy}
          >
            <Send aria-hidden />
          </Button>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="lg:hidden"
            aria-label={showDraft ? "Hide draft" : "Show draft"}
            onClick={() => setShowDraft((v) => !v)}
          >
            {showDraft ? "×" : "≡"}
          </Button>
        </form>
      </section>

      {/* Right rail: toggle between the surfaced literature and the protocol
          draft. On mobile it's hidden until the composer's toggle opens it. */}
      <div className={cn("flex min-h-0 flex-col lg:flex", showDraft ? "flex" : "hidden")}>
        <div className="border-l border-b border-border-strong bg-surface p-2">
          <SegmentedControl
            value={rail}
            onChange={setRail}
            aria-label="Right panel: literature or protocol draft"
            options={[
              { value: "draft", label: "Protocol draft" },
              { value: "papers", label: "Literature" },
            ]}
          />
        </div>
        <div className="min-h-0 flex-1 overflow-hidden">
          {rail === "papers" ? (
            <RecommenderRail
              recommendations={recommendations}
              addedRefs={addedRefs}
              onAdd={addPaper}
            />
          ) : (
            <DraftRail
              draft={clientDraft}
              serverYaml={compileResult?.yaml}
              compileValid={compileResult?.valid}
              onApply={live && !stubOnly ? applyDraft : undefined}
              applying={applying}
              onFinish={live && !stubOnly ? () => { void refreshCompile(); setShowFinish(true); } : undefined}
            />
          )}
        </div>
      </div>

      <FinishReview
        open={showFinish}
        onOpenChange={setShowFinish}
        moves={allMoves}
        compile={compileResult}
        applying={applying}
        applied={applied}
        onApply={applyDraft}
      />
    </div>
  );
}
