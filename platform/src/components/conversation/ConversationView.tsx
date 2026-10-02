import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Check, PanelRight, PanelRightClose, Send } from "lucide-react";
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
  type DecisionTrigger,
} from "@/lib/conversationApi";
import { ApiError } from "@/lib/api";
import { studyApi } from "@/lib/studyApi";
import type { Understanding } from "@/lib/types";
import { cn } from "@/lib/cn";
import {
  MANDATORY_SLOTS,
  type DesignMove,
  type MoveStatus,
  type Turn,
} from "@/lib/types";
import {
  DEFAULT_STEER,
  readSteer,
  writeSteer,
  type SteerLevel,
} from "@/lib/steer";
import { readRail, usePanel, togglePanel, writeRail, type RailId } from "@/lib/panels";

function firstProposed(turns: Turn[]): string | null {
  for (const t of turns) {
    for (const m of t.moves) if (m.status === "proposed") return m.moveId;
  }
  return null;
}

function compactText(text: string, max = 104): string {
  const clean = text.replace(/\s+/g, " ").trim();
  return clean.length > max ? `${clean.slice(0, max - 1)}…` : clean;
}

function isDecisionEcho(text: string): boolean {
  return /^(I )?(accepted|rejected|noted)\b/i.test(text.trim());
}

function HistoryRow({ turn }: { turn: Turn }) {
  const decisions = turn.moves.filter((move) => move.status !== "proposed");
  const label = turn.role === "researcher"
    ? isDecisionEcho(turn.text)
      ? "Decision recorded"
      : "Your note"
    : "Platform guidance";

  return (
    <li className="flex items-start gap-3 border-t border-border py-3 first:border-t-0">
      <span
        aria-hidden
        className={cn(
          "mt-1.5 size-1.5 shrink-0 rounded-dot",
          turn.role === "researcher" ? "bg-accent" : "bg-border-strong",
        )}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <span className="type-caption font-medium text-text">{label}</span>
          {decisions.length > 0 && (
            <span className="type-legend text-text-muted">
              {decisions.length} {decisions.length === 1 ? "choice" : "choices"}
            </span>
          )}
        </div>
        {decisions.length > 0 ? (
          <ul className="mt-1 flex flex-col gap-1">
            {decisions.map((move) => (
              <li key={move.moveId} className="flex min-w-0 items-start gap-1.5 type-caption text-text-muted">
                {move.status === "accepted" ? (
                  <Check className="mt-0.5 size-3 shrink-0 text-accent" aria-hidden />
                ) : (
                  <span aria-hidden className="mt-1 size-2 shrink-0 rounded-dot border border-border-strong" />
                )}
                <span className="min-w-0">{compactText(move.proposal, 116)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-0.5 type-caption text-text-muted">{compactText(turn.text)}</p>
        )}
      </div>
    </li>
  );
}

export function ConversationView({
  studyId = "study",
  opening = "",
}: {
  studyId?: string;

  opening?: string;
}) {
  const [turns, setTurns] = useState<Turn[]>(() => [openingTurn(opening)]);
  const [input, setInput] = useState("");
  const [addedRefs, setAddedRefs] = useState<Set<string>>(new Set());
  const [live, setLive] = useState(true);
  const [busy, setBusy] = useState(false);
  const [conversationLoading, setConversationLoading] = useState(true);

  const [streamingText, setStreamingText] = useState<string | null>(null);

  const [understanding, setUnderstanding] = useState<Understanding | undefined>();
  const [compileResult, setCompileResult] = useState<CompileResult | null>(null);

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
  const [mobileDraft, setMobileDraft] = useState(false);

  const [focusMoveId, setFocusMoveId] = useState<string | null>(null);

  const openingSubmitted = useRef<string | null>(null);

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

          queueMicrotask(() => {
            if (!cancelled) void sendText(openingText);
          });
        } else {
          setTurns(initial);
        }
        setUnderstanding(u);
        setLive(true);
        setConversationLoading(false);
      }
    }).catch(() => {
      if (!cancelled) {
        const openingText = opening.trim();
        setTurns(
          openingText
            ? [
                {
                  turnId: `offline-opening-${studyId}`,
                  role: "researcher",
                  author: "You",
                  text: openingText,
                  moves: [],
                  recommendations: [],
                },
              ]
            : [openingTurn()],
        );
        setLive(false);
        if (openingText) {
          setNote(
            "Your brief is still here, but the assistant needs the running middleware before it can configure the protocol.",
          );
        }
        setConversationLoading(false);
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

  const threadEmpty =
    !turns.some(
      (t) => t.role === "platform" && t.turnId !== "opening",
    ) && allMoves.length === 0;
  const openingKey = `${studyId}:${opening.trim()}`;
  const openingPending =
    Boolean(opening.trim()) && openingSubmitted.current === openingKey;
  const clientDraft = useMemo(() => compileAll(allMoves), [allMoves]);
  const missingCoreSlots = useMemo(
    () => MANDATORY_SLOTS.filter((slot) => clientDraft[slot].length === 0),
    [clientDraft],
  );

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

    if (!live || conversationLoading) return;
    try {
      const result = await conversationApi.compile(studyId);
      setCompileResult(result);
      setReadOnlyProtocol(null);
    } catch {
      setCompileResult(null);

      try {
        setReadOnlyProtocol(await studyApi.protocol(studyId));
      } catch {
        setReadOnlyProtocol(null);
      }
    }
  }, [conversationLoading, live, studyId]);

  useEffect(() => {
    if (live) void refreshCompile();
  }, [allMoves, live, refreshCompile]);

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

  async function sendText(text: string, decision?: DecisionTrigger) {
    if (!text || busy) return;

    if (/^\s*(finish|wrap up|wrap-up|done|i'?m done|that'?s it)\b/i.test(text)) {
      setInput("");
      await refreshCompile();
      setShowFinish(true);
      return;
    }

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

        setStreamingText("");
        const appended = await conversationApi.sendTurnStreaming(
          studyId,
          text,
          "You",
          (fragment) => setStreamingText((prev) => prev + fragment),
          steer,
          decision,
        );
        setStreamingText(null);
        setUnderstanding(appended.understanding);
        setTurns((prev) => {

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

  async function decide(
    moveId: string,
    status: MoveStatus,
    renderedMove?: DesignMove,
  ) {
    const move =
      renderedMove ?? turns.flatMap((t) => t.moves).find((m) => m.moveId === moveId);
    if (!move || busy) return;
    const previousStatus = move.status;
    setTurns((prev) =>
      prev.map((t) => ({
        ...t,
        moves: t.moves.map((m) => {
          if (m.moveId !== moveId) return m;
          return { ...m, status };
        }),
      })),
    );
    if (live && status !== "proposed") {

      try {
        await conversationApi.decide(studyId, moveId, status);
      } catch {
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
        return;
      }

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

      const action: DecisionTrigger["action"] =
        status === "rejected"
          ? "rejected"
          : move.kind === "caution"
            ? "noted"
            : "accepted";
      const actionText =
        action === "rejected"
          ? `I rejected the proposed ${move.kind.replaceAll("-", " ")} move.`
          : action === "noted"
            ? `I noted the caution about ${move.proposal}`
            : `I accepted: ${move.proposal}`;
      try {
        await sendText(actionText, { moveId, action });
      } catch {
        setNote("The decision was saved, but the next question could not be generated. Try sending a short reply to continue.");
      }
    } else if (live && status === "proposed") {
      try {
        await conversationApi.decide(studyId, moveId, status);
      } catch {
        setTurns((prev) =>
          prev.map((t) => ({
            ...t,
            moves: t.moves.map((m) =>
              m.moveId === moveId ? { ...m, status: previousStatus } : m,
            ),
          })),
        );
        setNote("This decision is still local. It didn't reach the server, so nothing was changed. Try again.");
      }
    }
  }

  async function acceptBatch(moves: DesignMove[]) {
    const pending = moves.filter(
      (move) => move.status === "proposed" && move.kind !== "caution",
    );
    if (pending.length < 2 || busy) return;
    setBusy(true);
    setTurns((prev) =>
      prev.map((turn) => ({
        ...turn,
        moves: turn.moves.map((move) =>
          pending.some((candidate) => candidate.moveId === move.moveId)
            ? { ...move, status: "accepted" as const }
            : move,
        ),
      })),
    );
    const saved: DesignMove[] = [];
    try {
      if (live) {

        for (const move of pending) {
          await conversationApi.decide(studyId, move.moveId, "accepted");
          saved.push(move);
        }
      } else {
        saved.push(...pending);
      }
      if (live) {
        for (const grounding of pending.flatMap((move) => move.grounding)) {
          if (addedRefs.has(grounding.ref)) continue;
          setAddedRefs((prev) => new Set(prev).add(grounding.ref));
          studyApi
            .addPaperFromMatch(studyId, grounding.ref, grounding.why)
            .catch(() => {
              setAddedRefs((prev) => {
                const next = new Set(prev);
                next.delete(grounding.ref);
                return next;
              });
              setNote("Some cited papers could not be added to the library. Try again from Literature.");
            });
        }
      }
      setNote(`${saved.length} choices from your brief were accepted together. Review the draft, then continue with any open detail.`);
    } catch {
      setTurns((prev) =>
        prev.map((turn) => ({
          ...turn,
          moves: turn.moves.map((move) =>
            pending.some((candidate) => candidate.moveId === move.moveId)
              ? {
                  ...move,
                  status: saved.some(
                    (candidate) => candidate.moveId === move.moveId,
                  )
                    ? ("accepted" as const)
                    : ("proposed" as const),
                }
              : move,
          ),
        })),
      );
      setNote(`${saved.length} choices were saved; the rest remain open. Try the batch again when the connection is stable.`);
    } finally {
      setBusy(false);
    }
  }

  async function addPaper(ref: string) {

    setAddedRefs((prev) => new Set(prev).add(ref));

    if (!live) return;
    const rec = turns
      .flatMap((t) => t.recommendations)
      .find((r) => r.ref === ref);
    try {

      await studyApi.addPaperFromMatch(studyId, ref, rec?.matchReason ?? "");
    } catch {

      setAddedRefs((prev) => {
        const next = new Set(prev);
        next.delete(ref);
        return next;
      });
      setNote("Couldn't add that paper to your library. Check your connection and try again.");
    }
  }

  async function applyDraft() {
    if (!compileResult?.valid || missingCoreSlots.length > 0 || applying) return;
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

  const activePlatformIndex = [...turns]
    .map((turn, index) => ({ turn, index }))
    .reverse()
    .find(({ turn }) => turn.role === "platform" && turn.turnId !== "opening")?.index ?? -1;
  const latestResearcherIndex = [...turns]
    .map((turn, index) => ({ turn, index }))
    .reverse()
    .find(({ turn }) => turn.role === "researcher")?.index ?? -1;
  const activeResearcherIndex = latestResearcherIndex > activePlatformIndex
    ? latestResearcherIndex
    : [...turns]
        .map((turn, index) => ({ turn, index }))
        .reverse()
        .find(({ turn, index }) => turn.role === "researcher" && index < activePlatformIndex)?.index ?? -1;
  const activePlatform = activePlatformIndex >= 0 ? turns[activePlatformIndex] : null;
  const activeResearcherTurn = activeResearcherIndex >= 0 ? turns[activeResearcherIndex] : null;

  const activeResearcher = activeResearcherTurn && !isDecisionEcho(activeResearcherTurn.text)
    ? activeResearcherTurn
    : null;
  const historyTurns = turns
    .filter((turn) => turn.turnId !== "opening")
    .filter((turn) => turn !== activePlatform && turn !== activeResearcher);
  const filledSections = MANDATORY_SLOTS.length - missingCoreSlots.length;

  const progressDone = filledSections;
  const visibleCompile = compileResult && missingCoreSlots.length > 0
    ? {
        ...compileResult,
        valid: false,
        unresolved: [...new Set([...compileResult.unresolved, ...missingCoreSlots])],
      }
    : compileResult;
  const displayedPlatform = activePlatform && missingCoreSlots.length > 0 &&
      /protocol is complete.*ready to (?:compile|apply)/i.test(activePlatform.text)
    ? {
        ...activePlatform,
        text: "The draft still needs a few sections before it can be reviewed and applied. Follow the next question in the study map to continue.",
      }
    : activePlatform;
  const scopeBlocked = activePlatform?.source === "scope";

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="shrink-0 border-b border-border bg-surface px-3 py-1 lg:hidden">
        <Button
          variant="ghost"
          size="sm"
          aria-pressed={mobileDraft}
          onClick={() => {
            if (!mobileDraft && draftFolded) togglePanel("draft", studyId);
            setMobileDraft(!mobileDraft);
          }}
        >
          {mobileDraft ? "Back to conversation" : "Show protocol draft"}
        </Button>
      </div>
    <div
      className={cn("split-rail h-full min-h-0 flex-1", draftFolded && "rail-folded")}
    >
      <section className={cn("h-full min-h-0 min-w-0 flex-col overflow-hidden lg:flex", mobileDraft ? "hidden" : "flex")}>
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-auto scroll-smooth">
          <header className="border-b border-border bg-surface px-4 py-4 sm:px-8 sm:py-5">
            <div className="mx-auto flex w-full max-w-reading items-start justify-between gap-4">
              <div>
                <h2 className="type-section text-text">Build a runnable study</h2>
                <p className="mt-1 max-w-[52ch] type-caption text-text-muted">
                  Paste the whole brief or set the concrete details below. I’ll handle the
                  methodological reasoning, teach the trade-offs, and turn settled decisions
                  into a validated protocol.
                </p>
              </div>
              <div className="shrink-0 text-right">
                <span className="type-quantity-lg text-text">{progressDone}</span>
                <span className="type-caption text-text-muted"> / {MANDATORY_SLOTS.length}</span>
                <p className="type-legend mt-1 text-text-muted">core sections drafted</p>
              </div>
            </div>
          </header>

          <div className="mx-auto flex w-full max-w-reading flex-col gap-5 px-4 py-5 sm:px-8 sm:py-8">
            {conversationLoading ? (
              <div className="space-y-3 py-2" aria-busy="true" aria-label="Loading conversation">
                <div className="h-3 w-24 animate-pulse rounded-full bg-border" />
                <div className="h-4 w-4/5 animate-pulse rounded-full bg-border" />
                <div className="h-4 w-3/5 animate-pulse rounded-full bg-border" />
              </div>
            ) : threadEmpty && !openingPending && !activeResearcher ? (
              <ConversationStart onUse={takeOpening} />
            ) : (
              <div className="flex flex-col gap-5">
                {activeResearcher && (
                  <div className="ml-auto max-w-[48ch] rounded-card border border-border bg-zone-9 px-3.5 py-2.5">
                    <p className="type-caption text-text-muted">You</p>
                    <p className="mt-0.5 type-body text-text">{compactText(activeResearcher.text, 240)}</p>
                  </div>
                )}

                {displayedPlatform && (
                  <StreamingTurn
                    turn={displayedPlatform}
                    onDecide={decide}
                    onAcceptBatch={acceptBatch}
                    focusMoveId={focusMoveId}
                    active
                  />
                )}

                {busy && live && (
                  <div className="flex flex-col items-start gap-3">
                    {streamingText && (
                      <div className="max-w-bubble animate-in fade-in px-1 py-1 type-body duration-entrance">
                        <span className="mb-1 block type-caption text-text-muted">Platform</span>
                        <span className="whitespace-pre-wrap text-text" aria-live="polite">
                          {streamingText}
                        </span>
                      </div>
                    )}
                    <div className="flex items-center gap-1 px-1 py-1 type-caption text-text-muted" aria-label="Platform is thinking">
                      <span className="size-1.5 animate-pulse rounded-full bg-text-muted" />
                      <span className="size-1.5 animate-pulse rounded-full bg-text-muted [animation-delay:var(--motion-fast)]" />
                      <span className="size-1.5 animate-pulse rounded-full bg-text-muted [animation-delay:var(--motion-standard)]" />
                      <span className="ml-1">Preparing the next decision</span>
                    </div>
                  </div>
                )}
              </div>
            )}

            {historyTurns.length > 0 && (
              <details className="border-t border-border pt-4">
                <summary className="type-control flex cursor-pointer items-center justify-between text-text-muted hover:text-text">
                  <span>Earlier decisions</span>
                  <span className="type-caption">{historyTurns.length} turns</span>
                </summary>
                <ol className="mt-2 border-b border-border">
                  {historyTurns.map((turn) => <HistoryRow key={turn.turnId} turn={turn} />)}
                </ol>
              </details>
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
          className="border-t border-border bg-surface px-4 py-2 sm:px-6"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <div className="mx-auto flex w-full max-w-reading items-end gap-1.5 rounded-card border border-control-edge bg-surface px-2.5 py-1.5 focus-within:border-accent">
            <textarea
              ref={composer}
              className="type-body min-h-7 min-w-0 flex-1 resize-none overflow-y-auto border-0 bg-transparent px-0 py-0.5 text-text placeholder:text-text-muted"
              placeholder="Answer the prompt or add a detail…"
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
              aria-label="Send"
              disabled={busy}
            >
              <Send aria-hidden />
            </Button>
          </div>
          <p className="mx-auto mt-1.5 hidden w-full max-w-reading px-1 type-legend text-text-muted sm:block">
            Enter to send · Shift + Enter for a new line
          </p>
        </form>
      </section>

      <div
        className={cn(
          "min-h-0 min-w-0 flex-col border-l border-border-strong bg-surface transition-all duration-fast lg:flex",
          mobileDraft ? "flex" : "hidden",

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
              className="hidden shrink-0 lg:flex"
              aria-label="Hide protocol draft"
              aria-expanded
              onClick={() => togglePanel("draft", studyId)}
            >
              <PanelRightClose className="size-4" aria-hidden />
            </Button>
          </div>
        )}
        <div className={cn("min-h-0 min-w-0 flex-1 overflow-hidden", draftFolded && "hidden")}>
          {rail === "papers" ? (
            <RecommenderRail
              recommendations={recommendations}
              addedRefs={addedRefs}
              onAdd={addPaper}
            />
          ) : (
            <DraftRail
              understanding={understanding}
              scopeBlocked={scopeBlocked}
              loading={conversationLoading}
              draft={clientDraft}
              serverYaml={conversationLoading ? undefined : compileResult?.yaml}
              protocol={
                conversationLoading
                  ? undefined
                  : compileResult?.protocol ?? readOnlyProtocol ?? undefined
              }
              compileValid={visibleCompile?.valid}
              unresolved={visibleCompile?.unresolved}
              compileErrors={compileResult?.errors}
              compileWarnings={compileResult?.warnings}

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

      </div>

      <FinishReview
        open={showFinish}
        onOpenChange={setShowFinish}
        moves={allMoves}
        compile={visibleCompile}
        applying={applying}
        applied={applied}
        onApply={applyDraft}
      />
    </div>
    </div>
  );
}
