import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PanelRight, PanelRightClose, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { StreamingTurn } from "./StreamingTurn";
import { DraftRail } from "./DraftRail";
import { RecommenderRail } from "./RecommenderRail";
import { FinishReview } from "./FinishReview";
import { SteerDial } from "./SteerDial";
import { ConversationStart } from "./ConversationStart";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { compileAll } from "@/lib/compiler";
import { openingTurn } from "@/lib/conversationOpening";
import type { Recommendation } from "@/lib/types";
import {
  conversationApi,
  loadConversation,
  type CompileResult,
} from "@/lib/conversationApi";
import { ApiError } from "@/lib/api";
import { studyApi } from "@/lib/studyApi";
import type { Understanding } from "@/lib/types";
import { cn } from "@/lib/cn";
import type { DesignMove, MoveStatus, Turn } from "@/lib/types";
import {
  DEFAULT_STEER,
  readSteer,
  writeSteer,
  type SteerLevel,
} from "@/lib/steer";
import { readRail, usePanel, togglePanel, writeRail, type RailId } from "@/lib/panels";

/** The first still-undecided move across these turns  -  the one a reply hands
 *  the caret to, so `a` / `r` act on the top proposal rather than the last. */
function firstProposed(turns: Turn[]): string | null {
  for (const t of turns) {
    for (const m of t.moves) if (m.status === "proposed") return m.moveId;
  }
  return null;
}

export function ConversationView({
  studyId = "study",
  opening = "",
}: {
  studyId?: string;
  /** A first line to send on arrival, typed by the researcher elsewhere  -
   *  the "what do you want to find out?" answer given while creating the
   *  project. Sent once, then never again for this study. */
  opening?: string;
}) {
  const [turns, setTurns] = useState<Turn[]>(() => [openingTurn(opening)]);
  const [input, setInput] = useState("");
  const [addedRefs, setAddedRefs] = useState<Set<string>>(new Set());
  const [live, setLive] = useState(true);
  const [busy, setBusy] = useState(false);
  /* The reply's prose while it streams; null once the real turn lands. */
  const [streamingText, setStreamingText] = useState<string | null>(null);
  /* What the platform understands about the study so far (FR-CONV-10)  -  used
   * to explain why it hasn't proposed a design yet. */
  const [understanding, setUnderstanding] = useState<Understanding | undefined>();
  const [compileResult, setCompileResult] = useState<CompileResult | null>(null);
  /** The protocol as a reader sees it, when this identity may not compile. */
  const [readOnlyProtocol, setReadOnlyProtocol] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);
  const [showFinish, setShowFinish] = useState(false);
  const draftFolded = usePanel("draft", studyId);
  const [rail, setRail] = useState<RailId>(() => readRail(studyId));
  /* The one move the caret goes to, set only when a reply lands in answer
   * to something this researcher just sent. Never on a page they merely
   * opened, and never for a colleague's change arriving over the stream:
   * `a` and `r` decide a move from one unmodified keystroke. */
  const [focusMoveId, setFocusMoveId] = useState<string | null>(null);
  /* A project-opening idea is already the researcher's first contribution. Keep
   * the hand-off idempotent while the empty conversation is being replaced by
   * the real LLM turn. */
  const openingSubmitted = useRef<string | null>(null);
  /* How much the assistant drives this conversation (see lib/steer.ts).
   * Per-study and read lazily, so a reload lands back on the setting this
   * study was left at rather than on the default. */
  const [steer, setSteer] = useState<SteerLevel>(DEFAULT_STEER);

  const threadEnd = useRef<HTMLDivElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setSteer(readSteer(studyId, DEFAULT_STEER));
    setRail(readRail(studyId));
  }, [studyId]);

  const changeRail = (next: RailId) => {
    setRail(next);
    writeRail(studyId, next);
  };

  const changeSteer = useCallback(
    (next: SteerLevel) => {
      setSteer(next);
      writeSteer(studyId, next);
    },
    [studyId],
  );

  // The composer grows with what's typed instead of clipping or scrolling
  // inside a fixed single row  -  capped so a very long message still scrolls
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

  // Keep the newest turn in view while the optimistic message and streamed
  // reply arrive. The frame throttle prevents a token stream from issuing a
  // scroll for every fragment, while smooth scrolling keeps the thread from
  // jumping under the reader's eyes.
  useEffect(() => {
    if (!busy && streamingText == null) return;
    const frame = requestAnimationFrame(() =>
      threadEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" }),
    );
    return () => cancelAnimationFrame(frame);
  }, [busy, streamingText]);

  useEffect(() => {
    let cancelled = false;
    loadConversation(studyId).then(({ turns: t, understanding: u }) => {
      if (!cancelled) {
        const emptyConversation = t.length === 1 && t[0].turnId === "opening";
        const initial = emptyConversation ? [openingTurn(opening)] : t;
        const openingText = opening.trim();
        const openingKey = `${studyId}:${openingText}`;
        if (
          emptyConversation &&
          openingText &&
          openingSubmitted.current !== openingKey
        ) {
          openingSubmitted.current = openingKey;
          setTurns([]);
          /* Let the empty state settle for one frame, then hand the opening
           * idea to the same streaming path as every later turn. The platform
           * greeting is therefore generated by the configured assistant, not
           * a static sentence that forces the researcher to start twice. */
          queueMicrotask(() => {
            if (!cancelled) void sendText(openingText);
          });
        } else {
          setTurns(initial);
        }
        setUnderstanding(u);
        setLive(true);
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
  }, [opening, studyId]);

  const allMoves: DesignMove[] = useMemo(
    () => turns.flatMap((t) => t.moves),
    [turns],
  );

  /* Nothing of the study's own is on the sheet yet: the platform has not
   * answered and no move has been proposed. The blank record teaches the
   * first move here.
   *
   * The researcher's OWN opening question does not end the blank state. It
   * used to: a study opened from "Start a project" carries that question in
   * as its first turn, which flipped this to false before the workspace had
   * ever painted  -  so the one screen that explains how the record gets
   * written was skipped by exactly the researchers who had never seen it,
   * and what they got instead was a single unanswered bubble above half a
   * screen of bare ground. A question you asked and nothing has answered is
   * still a blank plate. */
  /* `opening` is a client-side prompt, not an answered turn. Treating it as
   * conversation content made the durable first-run guide disappear before a
   * researcher had written anything, especially on a newly created study. */
  const threadEmpty =
    !turns.some(
      (t) => t.role === "platform" && t.turnId !== "opening",
    ) && allMoves.length === 0;
  const openingKey = `${studyId}:${opening.trim()}`;
  const openingPending =
    Boolean(opening.trim()) && openingSubmitted.current === openingKey;
  const clientDraft = useMemo(() => compileAll(allMoves), [allMoves]);

  // The literature the conversation has surfaced, de-duplicated by ref, newest
  // turns first  -  the recommender rail's source. Refreshes as turns arrive.
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
    if (!live) return;
    try {
      const result = await conversationApi.compile(studyId);
      setCompileResult(result);
      setReadOnlyProtocol(null);
    } catch {
      setCompileResult(null);
      /* Compiling is a contribute-level action, so a viewer 403s here  -  and
       * used to be shown an empty "no design shape yet" rail over a protocol
       * that exists and is fully compiled (the read-only demo made this
       * unmissable: Data and Planning rendered the protocol while this rail
       * claimed there wasn't one). Fall back to the view-capability document
       * so a reader sees the study's record; they still can't compile it. */
      try {
        setReadOnlyProtocol(await studyApi.protocol(studyId));
      } catch {
        setReadOnlyProtocol(null);
      }
    }
  }, [live, studyId]);

  useEffect(() => {
    if (live) void refreshCompile();
  }, [allMoves, live, refreshCompile]);

  /* An opening taken from the blank record: it lands in the composer for the
   * researcher to edit, and the caret goes with it. Never sent for them  -
   * the human sends. */
  function takeOpening(text: string) {
    setInput(text);
    queueMicrotask(() => {
      const el = composer.current;
      if (!el) return;
      el.focus();
      el.setSelectionRange(text.length, text.length);
    });
  }

  async function send() {
    await sendText(input.trim());
  }

  /* The turn itself, given its text. Split out from `send` so an opening
   * line the researcher already typed  -  in the "what do you want to find
   * out?" field on project creation  -  can be sent on arrival without being
   * round-tripped through the composer's state first. */
  async function sendText(text: string) {
    if (!text || busy) return;

    // "finish" / "wrap up" / "done" opens the protocol-review moment rather
    // than sending a turn  -  the researcher is signalling they're ready to
    // compile, not asking another question.
    if (/^\s*(finish|wrap up|wrap-up|done|i'?m done|that'?s it)\b/i.test(text)) {
      setInput("");
      await refreshCompile();
      setShowFinish(true);
      return;
    }

    // Optimistic: show the researcher's message and clear the composer
    // immediately  -  before any network/LLM round-trip  -  so the thread never
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
      queueMicrotask(() =>
        threadEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" }),
      );
    scrollDown();

    try {
      if (live) {
        // sendTurn returns [researcher(server id), platform]; replace our
        // optimistic turn with the server pair so ids reconcile without a
        // duplicated message.
        // Streamed: the reply's prose appears as the model writes it, so the
        // thread is alive instead of blank for the whole round-trip. The
        // streamed text is presentation only  -  the resolved turns are the
        // same ones the blocking call returns, and replace it wholesale.
        setStreamingText("");
        const appended = await conversationApi.sendTurnStreaming(
          studyId,
          text,
          "You",
          (fragment) => setStreamingText((prev) => prev + fragment),
          steer,
        );
        setStreamingText(null);
        setUnderstanding(appended.understanding);
        setTurns((prev) => {
          /* The first platform prompt is a real part of the user's reading
           * path even though it is not stored as a researcher turn. Keep it
           * in front of the first server response; replacing the optimistic
           * pair wholesale made the user's first message appear to be the
           * conversation opener, and made the opening prompt flash and vanish. */
          const openingPrompt = prev.find((t) => t.turnId === "opening");
          return [
            ...(openingPrompt ? [openingPrompt] : []),
            ...prev.filter(
              (t) => t.turnId !== pendingId && t.turnId !== "opening",
            ),
            ...appended.turns,
          ];
        });
        setFocusMoveId(firstProposed(appended.turns));
      }
      scrollDown();
    } catch (e) {
      /* No invented reply. The platform used to answer from a keyword script
       * whenever the server was unreachable, which read as a design
       * conversation and was not one  -  a researcher had no way to tell the
       * difference until they acted on it. What they typed stays on screen,
       * and the reason it went unanswered is stated. */
      setLive(false);
      setNote(
        e instanceof ApiError && e.status === 503
          ? e.message
          : "That didn't reach the server, so it hasn't been answered yet. Your message is still here. Try again when you're back online.",
      );
      scrollDown();
    } finally {
      setStreamingText(null);
      setBusy(false);
    }
  }

  function decide(moveId: string, status: MoveStatus) {
    let previousStatus: MoveStatus | undefined;
    const move = turns.flatMap((t) => t.moves).find((m) => m.moveId === moveId);
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
    if (live) {
      // A rejected decision used to be swallowed, so the card showed a
      // decision the draft never received  -  the researcher would compile and
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
        setNote("This decision is still local. It didn't reach the server, so nothing was changed. Try again.");
      });

      // Accepting a move that cites papers is the researcher endorsing that
      // evidence, not just the move's text  -  the grounding chips already
      // read as "these papers back this", so leaving them out of the
      // Library made that reading false: the assistant could describe a
      // cited paper as already part of the study while the Library and
      // citation graph had no record of it. Every resolved grounding.ref is
      // a real corpus paper (the server only attaches metadata it actually
      // found  -  see design_assistant._resolve_grounding), so this is safe
      // to fire for all of them, not just a filtered subset.
      if (status === "accepted" && move && move.grounding.length > 0) {
        for (const g of move.grounding) {
          if (addedRefs.has(g.ref)) continue;
          setAddedRefs((prev) => new Set(prev).add(g.ref));
          studyApi.addPaperFromMatch(studyId, g.ref, g.why).catch(() => {
            setAddedRefs((prev) => {
              const next = new Set(prev);
              next.delete(g.ref);
              return next;
            });
            setNote(
              "Accepted, but couldn't add its cited paper to your library. Try again from the Literature panel.",
            );
          });
        }
      }
    }
  }

  async function addPaper(ref: string) {
    // Optimistic: mark it added immediately so the card settles.
    setAddedRefs((prev) => new Set(prev).add(ref));
    // Offline previews stay local-only  -  there's no study to write to.
    if (!live) return;
    const rec = turns
      .flatMap((t) => t.recommendations)
      .find((r) => r.ref === ref);
    try {
      // Actually ingest it into the study's Library, keeping the match reason.
      await studyApi.addPaperFromMatch(studyId, ref, rec?.matchReason ?? "");
    } catch {
      // Roll the flag back so the researcher can retry  -  silent success on a
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

  return (
    <div
      data-agent="conversation"
      className={cn("split-rail h-full", draftFolded && "rail-folded")}
    >
      <section className="flex h-full min-h-0 min-w-0 flex-col">
        <div className="flex min-h-0 flex-1 flex-col overflow-auto scroll-smooth p-4 sm:p-6">
          {/* The rail only looked slim because this column was unbounded  -
           * centring the thread at the reading measure is what actually
           * fixed it, not the rail's own width.
           *
           * `mt-auto` anchors the thread to the BOTTOM of the scroller while
           * it is shorter than the viewport, and does nothing once it is
           * taller. A record grows downward toward the hand writing it, so a
           * two-line conversation belongs against the composer, not pinned to
           * the top of 500px of bare ground  -  which is what a study opened
           * from "Start a project" showed: one seeded turn floating alone
           * above half a screen of empty grid. */}
          <div className="mx-auto mt-auto flex w-full max-w-reading flex-col space-y-4">
            {/* Above the turns, not after them. It is what is printed on the
              * blank plate, so it belongs where the record starts  -  a
              * researcher who arrived with an opening question already asked
              * should read it before their own unanswered line, not under
              * it. */}
            {threadEmpty && !openingPending && (
              <ConversationStart onUse={takeOpening} />
            )}
            {turns.map((t) => (
              <StreamingTurn
                key={t.turnId}
                turn={t}
                onDecide={decide}
                focusMoveId={focusMoveId}
              />
            ))}
            {busy && live && (
              <div className="flex flex-col items-start gap-3" data-agent="conversation-thinking">
                {streamingText && (
                  <div className="max-w-[62ch] animate-in fade-in px-1 py-1 type-body duration-entrance">
                    <span className="mb-1 block type-caption text-text-muted opacity-70">
                      Platform
                    </span>
                    {/* The reply as it is being written. Live for a screen
                     * reader too, but polite  -  it must not interrupt. */}
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
                 * cards are ready  -  this stays its own card, separate from
                 * the reply bubble above, through that whole gap instead of
                 * disappearing the moment text appears (which read as the
                 * reply being done when it wasn't). */}
                <div className="max-w-[62ch] animate-in fade-in px-1 py-1 type-body duration-entrance">
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

        {note && (
          <div className="border-t border-border bg-surface px-4 py-2 sm:px-6">
            <Notice kind="offline" className="mx-auto w-full max-w-bubble">
              {note}
            </Notice>
          </div>
        )}

        <form
          data-agent="conversation-composer"
          className="border-t border-border bg-surface px-4 py-2 sm:px-6"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          {/* One command bar: the message is primary, the conversation mode is
            * adjacent and compact, and send closes the row. The mode picker
            * opens above its button, so the composer never grows a second
            * permanent band or makes the input compete with a full-width
            * slider. */}
          <div className="mx-auto flex w-full max-w-reading items-end gap-1.5 rounded-card border border-control-edge bg-surface px-2 focus-within:border-accent">
            <textarea
              ref={composer}
              className="type-body min-h-7 min-w-0 flex-1 resize-none overflow-y-auto border-0 bg-transparent px-0 py-0.5 text-text placeholder:text-text-muted"
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
            <SteerDial value={steer} onChange={changeSteer} />
            <Button
              type="submit"
              size="sm"
              className="!size-8 !px-0"
              data-agent="conversation-send"
              aria-label="Send"
              disabled={busy}
            >
              <Send aria-hidden />
            </Button>
          </div>
        </form>
      </section>

      {/* Right rail: toggle between literature and protocol draft.
          Desktop: minimizable via fold button, persisted per device.

          Folded, this used to be a 2.125rem (34px) column with the panel's
          full-width contents still rendering inside it  -  a `p-gutter` aside
          needs 64px for its padding alone, so what actually painted was a
          30px-wide vertical slice of clipped words hanging off the edge of
          the window, and the only control that could restore it lived on the
          composer, three hundred pixels away and unlabelled. Folded is now a
          real icon strip that says what it is and reopens itself. */}
      <div
        className={cn(
          "hidden min-h-0 flex-col border-l border-border-strong bg-surface transition-all duration-fast lg:flex",
          /* Expanded, the rail fills the track the grid gave it  -  it must not
           * name its own width. `.split-rail` sizes this column as
           * `clamp(--rail-min, --rail-share, --rail-max)`, and `--rail-share`
           * is `32vw`, so on any window narrower than 90rem the track lands
           * BELOW the 30rem this div used to hardcode: at 1440px the track
           * computed to 460.8px against a 480px div, and the extra 19px of
           * the protocol draft hung past the right edge of the window and was
           * clipped. Two widths for one column can only agree by coincidence.
           *
           * Folded is the reverse case and stays explicit: that track is
           * `auto`, so it takes its width FROM this div. */
          draftFolded ? "w-11" : "w-full",
        )}
      >
        {draftFolded ? (
          <div className="flex flex-col items-center gap-1 py-2">
            <Button
              variant="ghost"
              size="icon"
              aria-label="Show protocol draft"
              aria-expanded={false}
              onClick={() => togglePanel("draft", studyId)}
            >
              <PanelRight className="size-4" aria-hidden />
            </Button>
            {/* Set along the rail it reopens, so a folded panel still names
              * itself instead of leaving one unexplained glyph in a gutter. */}
            <span
              className="type-legend select-none text-text-muted [writing-mode:vertical-rl]"
              aria-hidden
            >
              {rail === "papers" ? "Literature" : "Protocol draft"}
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-2 border-b border-border-strong bg-surface p-2">
            <SegmentedControl
              value={rail}
              onChange={changeRail}
              className="min-w-0 flex-1"
              aria-label="Right panel: literature or protocol draft"
              options={[
                { value: "draft", label: "Protocol draft" },
                { value: "papers", label: "Literature" },
              ]}
            />
            <Button
              variant="ghost"
              size="icon"
              className="shrink-0"
              aria-label="Hide protocol draft"
              aria-expanded
              onClick={() => togglePanel("draft", studyId)}
            >
              <PanelRightClose className="size-4" aria-hidden />
            </Button>
          </div>
        )}
        <div className={cn("min-h-0 flex-1 overflow-hidden", draftFolded && "hidden")}>
          {rail === "papers" ? (
            <RecommenderRail
              recommendations={recommendations}
              addedRefs={addedRefs}
              onAdd={addPaper}
            />
          ) : (
            <DraftRail
              understanding={understanding}
              draft={clientDraft}
              serverYaml={compileResult?.yaml}
              protocol={compileResult?.protocol ?? readOnlyProtocol ?? undefined}
              compileValid={compileResult?.valid}
              unresolved={compileResult?.unresolved}
              /* A reader can see the record; only a contributor can change it,
               * so the actions stay off when the compile came back 403. */
              onApply={live && compileResult ? applyDraft : undefined}
              applying={applying}
              onFinish={
                live && compileResult
                  ? () => { void refreshCompile(); setShowFinish(true); }
                  : undefined
              }
            />
          )}
        </div>
        {/* The fold control lives in this panel's header, beside the name of
          * the thing it folds  -  not pinned to the far bottom corner, and not
          * duplicated onto the composer. One toggle, where its own title is. */}
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
