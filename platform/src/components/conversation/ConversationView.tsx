import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StreamingTurn } from "./StreamingTurn";
import { DraftRail } from "./DraftRail";
import { RecommenderRail } from "./RecommenderRail";
import { FinishReview } from "./FinishReview";
import { UnderstandingLine } from "./UnderstandingLine";
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
import type { StudyChange } from "@/lib/presence";
import type { Understanding } from "@/lib/types";
import { cn } from "@/lib/cn";
import type { DesignMove, MoveStatus, Turn } from "@/lib/types";

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
  /** The last change another viewer made to this study (FR-PLAT
   *  collaboration). Carries only what changed; the thread re-reads. */
  remoteChange = null,
}: {
  studyId?: string;
  stubOnly?: boolean;
  remoteChange?: StudyChange | null;
}) {
  const [turns, setTurns] = useState<Turn[]>(() => [openingTurn()]);
  const [input, setInput] = useState("");
  const [addedRefs, setAddedRefs] = useState<Set<string>>(new Set());
  const [markedTurns, setMarkedTurns] = useState<Set<string>>(new Set());
  const [live, setLive] = useState(!stubOnly);
  const [busy, setBusy] = useState(false);
  /* The reply's prose while it streams; null once the real turn lands. */
  const [streamingText, setStreamingText] = useState<string | null>(null);
  /* What the platform understands about the study so far (FR-CONV-10) — used
   * to explain why it hasn't proposed a design yet. */
  const [understanding, setUnderstanding] = useState<Understanding | undefined>();
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

  /* A colleague changed this study: re-read the thread instead of trusting
   * the event, and skip a change this client just made itself (our own turn
   * is already on screen). */
  const knownTurnIds = useRef<Set<string>>(new Set());
  const knownMoveIds = useRef<Set<string>>(new Set());
  useEffect(() => {
    knownTurnIds.current = new Set(turns.map((t) => t.turnId));
    knownMoveIds.current = new Set(
      turns.flatMap((t) => t.moves.map((m) => m.moveId)),
    );
  }, [turns]);

  useEffect(() => {
    if (!remoteChange || !live || stubOnly) return;
    if (remoteChange.turnId && knownTurnIds.current.has(remoteChange.turnId)) return;
    // A decision on a card already on screen changes exactly one status —
    // patch it in place instead of replacing the thread. The full re-read
    // used to run even for this client's own decisions (a move event carries
    // no turnId, so the guard above never fired) and would clobber any
    // still-in-flight optimistic decision. The patch mirrors what a re-read
    // would return, so the stream stays a nudge, not a source of truth.
    if (
      remoteChange.changed === "move" &&
      remoteChange.moveId &&
      remoteChange.status &&
      knownMoveIds.current.has(remoteChange.moveId)
    ) {
      const { moveId } = remoteChange;
      const status = remoteChange.status as MoveStatus;
      setTurns((prev) =>
        prev.map((t) => ({
          ...t,
          moves: t.moves.map((m) => (m.moveId === moveId ? { ...m, status } : m)),
        })),
      );
      return;
    }
    let cancelled = false;
    loadConversation(studyId, stubOnly)
      .then(({ turns: t, understanding: u }) => {
        if (!cancelled) {
          setTurns(t);
          setUnderstanding(u);
        }
      })
      .catch(() => {
        /* A failed catch-up leaves the thread as it was — never blanked. */
      });
    return () => {
      cancelled = true;
    };
    // Re-runs per pushed change. `turns` is deliberately not a dependency:
    // the already-known ids are read from a ref, so a re-read can't retrigger
    // itself.
  }, [remoteChange, studyId, stubOnly, live]);

  useEffect(() => {
    let cancelled = false;
    loadConversation(studyId, stubOnly).then(({ turns: t, understanding: u }) => {
      if (!cancelled) {
        setTurns(t);
        setUnderstanding(u);
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
        setUnderstanding(appended.understanding);
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
      setNote("You're offline. Replies are coming from the built-in assistant until the connection returns.");
      scrollDown();
    } finally {
      setStreamingText(null);
      setBusy(false);
    }
  }

  function decide(moveId: string, status: MoveStatus) {
    let previousStatus: MoveStatus | undefined;
    setTurns((prev) =>
      prev.map((t) => ({
        ...t,
        moves: t.moves.map((m) => {
          if (m.moveId !== moveId) return m;
          previousStatus = m.status;
          return { ...m, status };
        }),
      })),
    );
    if (live && !stubOnly) {
      // A rejected decision used to be swallowed, so the card showed a
      // decision the draft never received — the researcher would compile and
      // find the move missing with no explanation. Rolling back only this
      // one move (not the whole thread) matters once Undo exists: another
      // request can be in flight when this one fails, and a whole-thread
      // snapshot would wipe that unrelated activity too.
      conversationApi.decide(studyId, moveId, status).catch(() => {
        setTurns((prev) =>
          prev.map((t) => ({
            ...t,
            moves: t.moves.map((m) =>
              m.moveId === moveId && previousStatus !== undefined
                ? { ...m, status: previousStatus }
                : m,
            ),
          })),
        );
        setNote("That decision didn't reach the server. Try it again.");
      });
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
      setNote("Couldn't add that paper to your library. Check your connection and try again.");
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
      setNote("Couldn't apply the draft. Check your connection and try again.");
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
      className="split-rail h-full"
    >
      <section className="flex h-full min-h-0 flex-col">
        <div className="min-h-0 flex-1 overflow-auto p-4 sm:p-6">
          {/* The rail only looked slim because this column was unbounded —
           * centring the thread at the reading measure is what actually
           * fixed it, not the rail's own width. */}
          <div className="mx-auto flex w-full max-w-reading flex-col space-y-6">
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
                {streamingText && (
                  <div className="max-w-bubble animate-in fade-in rounded-card border border-border bg-surface px-4 py-3 text-sm duration-entrance">
                    <span className="mb-1 block text-xs text-text-muted opacity-70">
                      Platform
                    </span>
                    {/* The reply as it is being written. Live for a screen
                     * reader too, but polite — it must not interrupt. */}
                    <span
                      className="whitespace-pre-wrap text-text"
                      aria-live="polite"
                      data-agent="conversation-streaming"
                    >
                      {streamingText}
                    </span>
                  </div>
                )}
                {/* The model streams `text` before `moves` in the same
                 * completion, so the prose can finish well before the move
                 * cards are ready — this stays its own card, separate from
                 * the reply bubble above, through that whole gap instead of
                 * disappearing the moment text appears (which read as the
                 * reply being done when it wasn't). */}
                <div className="max-w-bubble animate-in fade-in rounded-card border border-border bg-surface px-4 py-3 text-sm duration-entrance">
                  <span className="inline-flex items-center gap-1 animate-pulse text-text-muted">
                    <span className="size-1.5 rounded-full bg-text-muted" />
                    <span className="size-1.5 rounded-full bg-text-muted" />
                    <span className="size-1.5 rounded-full bg-text-muted" />
                  </span>
                </div>
              </div>
            )}
            <div ref={threadEnd} />
          </div>
        </div>

        <UnderstandingLine understanding={understanding} />

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
          draft. On mobile it's hidden until the composer's toggle opens it.
          The one left hairline lives here, on the container — DraftRail and
          RecommenderRail used to each draw their own, redundantly. */}
      <div
        className={cn(
          "flex min-h-0 flex-col border-l border-border-strong lg:flex",
          showDraft ? "flex" : "hidden",
        )}
      >
        <div className="border-b border-border-strong bg-surface p-2">
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
