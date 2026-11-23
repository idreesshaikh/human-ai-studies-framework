import { compileOnOpenAllowed, type RoleState } from "@/lib/role";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MoreHorizontal, PanelRight, PanelRightClose, Send, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { StreamingTurn } from "./StreamingTurn";
import { StreamingReply } from "./StreamingReply";
import { DraftRail } from "./DraftRail";
import { RecommenderRail } from "./RecommenderRail";
import { FinishReview } from "./FinishReview";
import { SteerDial } from "./SteerDial";
import { ConversationStart } from "./ConversationStart";
import { ManualProtocolDialog } from "./ManualProtocolDialog";
import { EvidencePanel } from "./EvidencePanel";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { compileAll, sinceManualEntry } from "@/lib/compiler";
import { openingTurn } from "@/lib/conversationOpening";
import {
  acceptedBatchText,
  acceptedMoveText,
  nextFocusAfterDecision,
  notedMoveText,
  rejectedMoveText,
  shouldFollowUpAfterDecision,
  nextStepPrompt,
  plainErrorMessage,
} from "@/lib/uiText";
import type { Recommendation } from "@/lib/types";
import {
  conversationApi,
  newRequestId,
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

/** The first still-undecided move across these turns; a reply hands the caret to it. */
function firstProposed(turns: Turn[]): string | null {
  for (const t of turns) {
    for (const m of t.moves) if (m.status === "proposed") return m.moveId;
  }
  return null;
}

const LOADING_ROLE: RoleState = { status: "loading" };

type NoteKind = "note" | "problem" | "offline";

export function ConversationView({
  studyId = "study",
  opening: initialOpening = "",
  roleState = LOADING_ROLE,
  onProtocolChanged,
}: {
  studyId?: string;
  /** My access to this study; a viewer's open never issues the compile POST. */
  roleState?: RoleState;
  /** A first line to send once on arrival, typed while starting the study. */
  opening?: string;
  onProtocolChanged?: () => void;
}) {
  const [opening] = useState(initialOpening);
  const [turns, setTurns] = useState<Turn[]>(() => [openingTurn(opening)]);
  const [input, setInput] = useState("");
  const [addedRefs, setAddedRefs] = useState<Set<string>>(new Set());
  const [live, setLive] = useState(true);
  const [busy, setBusy] = useState(false);
  const [conversationLoading, setConversationLoading] = useState(true);
  const [conversationLoadFailed, setConversationLoadFailed] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [streaming, setStreaming] = useState(false);
  const incomingReply = useRef("");
  const preview = useRef<{ update: () => void }>(null);
  const [announcedReply, setAnnouncedReply] = useState("");
  /* What the platform understands so far (FR-CONV-10); explains why no design is proposed yet. */
  const [understanding, setUnderstanding] = useState<Understanding | undefined>();
  const [compileResult, setCompileResult] = useState<CompileResult | null>(null);
  const [compiling, setCompiling] = useState(false);
  const [decisionsSaving, setDecisionsSaving] = useState(0);
  const compileRequest = useRef(0);
  /** The protocol as a reader sees it, when this identity may not compile. */
  const [readOnlyProtocol, setReadOnlyProtocol] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [note, setNoteState] = useState<{ text: string; kind: NoteKind } | null>(null);
  const setNote = useCallback(
    (text: string | null, kind: NoteKind = "note") => setNoteState(text ? { text, kind } : null),
    [],
  );
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [applied, setApplied] = useState(false);
  const [showFinish, setShowFinish] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const draftFolded = usePanel("draft", studyId);
  const [rail, setRail] = useState<RailId>(() => readRail(studyId));
  /* The caret target: set only when a reply answers something the researcher just sent,
  * because `a` and `r` decide a move from one unmodified keystroke. */
  const [focusMoveId, setFocusMoveId] = useState<string | null>(null);
  /* Keeps the opening-idea hand-off idempotent while the empty conversation is replaced. */
  const openingSubmitted = useRef<string | null>(null);
  /* Cancels the reply in flight (Stop). */
  const abortRef = useRef<AbortController | null>(null);
  const activeRequest = useRef<{ text: string; id: string; pendingId: string; decision?: DecisionTrigger } | null>(null);
  /* The last turn that failed or was stopped, so resending the same text reuses
   * its request id and the server can recognise it as the same turn. */
  const failedRequest = useRef<{ text: string; id: string } | null>(null);
  /* A decision that finished the last pending card mid-stream waits here for that reply. */
  const queuedFollowUp = useRef<{ text: string; decision: DecisionTrigger } | null>(null);
  const sendTextRef = useRef<
    (text: string, decision?: DecisionTrigger, fromQueue?: boolean) => Promise<void>
  >(async () => {});
  /* How much the assistant drives the conversation (lib/steer.ts); stored per study. */
  const [steer, setSteer] = useState<SteerLevel>(DEFAULT_STEER);

  const threadEnd = useRef<HTMLDivElement>(null);
  const followReply = useRef(true);
  const composer = useRef<HTMLTextAreaElement>(null);
  const mayCompile = compileOnOpenAllowed(roleState);

  useEffect(() => () => {
    abortRef.current?.abort();
    abortRef.current = null;
    queuedFollowUp.current = null;
  }, []);

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

  // Grows with the text, capped so a long message scrolls instead of pushing Send off-screen.
  const growComposer = useCallback(() => {
    const el = composer.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, []);

  useEffect(() => {
    growComposer();
  }, [input, growComposer]);

  const followThread = useCallback(() => {
    if (followReply.current) threadEnd.current?.scrollIntoView({ behavior: "instant", block: "end" });
  }, []);

  useEffect(() => {
    let cancelled = false;
    conversationApi.get(studyId).then(({ turns: t, understanding: u }) => {
      if (!cancelled) {
        const emptyConversation = t.length === 1 && t[0].turnId === "opening";
        const initial = emptyConversation ? [openingTurn(opening)] : t;
        const openingText = opening.trim();
        const openingKey = `${studyId}:${openingText}`;
        if (
          emptyConversation && mayCompile && loadAttempt === 0 &&
          openingText &&
          openingSubmitted.current !== openingKey
        ) {
          openingSubmitted.current = openingKey;
          setTurns([]);
          /* Wait one frame so the empty state settles, then send the opening idea through the normal streaming path. */
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
        setLive(false);
        setInput((current) => current || opening.trim());
        setConversationLoadFailed(true);
        setConversationLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [opening, studyId, loadAttempt, mayCompile]);

  const allMoves: DesignMove[] = useMemo(
    () => turns.flatMap((t) => t.moves),
    [turns],
  );
  // Ties a compile result to the move ledger it compiled, so a stale result cannot
  // enable Apply while the next compile is in flight.
  const movesSignature = useMemo(() => JSON.stringify(allMoves), [allMoves]);
  const movesSignatureRef = useRef(movesSignature);
  movesSignatureRef.current = movesSignature;
  const [compiledMovesSignature, setCompiledMovesSignature] = useState<string | null>(null);
  const currentCompileResult = compiledMovesSignature === movesSignature ? compileResult : null;

  /* `opening` is a client-side prompt, not an answered turn, so it does not end the empty state. */
  const threadEmpty =
    !turns.some(
      (t) => t.role === "platform" && t.turnId !== "opening",
    ) && allMoves.length === 0;
  const openingKey = `${studyId}:${opening.trim()}`;
  const openingPending =
    Boolean(opening.trim()) && openingSubmitted.current === openingKey;
  const clientDraft = useMemo(
    () => compileAll(allMoves, currentCompileResult?.protocol),
    [allMoves, currentCompileResult],
  );
  const missingCoreSlots = useMemo(
    () => MANDATORY_SLOTS.filter((slot) => clientDraft[slot].length === 0),
    [clientDraft],
  );

  // The literature the conversation has surfaced, de-duplicated by ref, newest first.
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

  /* Primitives, so the callback's identity only changes when the answer does. */
  const roleLoading = roleState.status === "loading";

  const refreshCompile = useCallback(async () => {
    /* Wait for the conversation to load so the read-only protocol fallback cannot paint a different rail first. */
    if (!live || conversationLoading || decisionsSaving > 0) return;
    const request = ++compileRequest.current;
    if (!mayCompile) {
      /* Read-only (or role not yet known): never POST. A viewer sees the
       * study's record from the view-capability document instead. */
      if (roleLoading) return;
      setCompileResult(null);
      setCompiledMovesSignature(null);
      try {
        const protocol = await studyApi.protocol(studyId);
        if (request === compileRequest.current) setReadOnlyProtocol(protocol);
      } catch {
        if (request === compileRequest.current) setReadOnlyProtocol(null);
      }
      return;
    }
    setCompiling(true);
    const requestedMovesSignature = movesSignatureRef.current;
    try {
      const result = await conversationApi.compile(studyId);
      if (request !== compileRequest.current) return;
      setCompileResult(result);
      setCompiledMovesSignature(requestedMovesSignature);
      setReadOnlyProtocol(null);
    } catch {
      if (request !== compileRequest.current) return;
      setCompileResult(null);
      setCompiledMovesSignature(null);
      // Readers can load the recorded protocol even when they cannot compile.
      try {
        const protocol = await studyApi.protocol(studyId);
        if (request === compileRequest.current) setReadOnlyProtocol(protocol);
      } catch {
        if (request === compileRequest.current) setReadOnlyProtocol(null);
      }
    } finally {
      if (request === compileRequest.current) setCompiling(false);
    }
  }, [conversationLoading, decisionsSaving, live, studyId, mayCompile, roleLoading]);

  useEffect(() => {
    if (live) void refreshCompile();
  }, [movesSignature, live, refreshCompile]);

  async function reloadConversation() {
    const { turns: t, understanding: u } = await conversationApi.get(studyId);
    setTurns(t);
    setUnderstanding(u);
    return t;
  }

  /* Puts an opening into the composer for the researcher to edit; only the human sends. */
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
    if (!mayCompile || conversationLoading || conversationLoadFailed) return;
    const hadFocus = document.activeElement === composer.current;
    const sent = sendText(input.trim());
    const restoreFocus = () => {
      if (hadFocus && document.activeElement === document.body) composer.current?.focus();
    };
    requestAnimationFrame(restoreFocus);
    await sent;
    requestAnimationFrame(restoreFocus);
  }

  /* The turn itself, so an opening typed elsewhere is sent on arrival without passing through the composer. */
  async function sendText(text: string, decision?: DecisionTrigger, fromQueue = false) {
    if (!text || abortRef.current || (busy && !fromQueue)) return;

    setNote(null);
    // Optimistic: show the message and clear the composer before the round-trip; the pending
    // id is swapped for the server's researcher turn when the reply lands.
    const pendingId = newRequestId();
    const researcherTurn: Turn = {
      turnId: pendingId,
      role: "researcher",
      author: "You",
      text,
      moves: [],
      recommendations: [],
    };
    setTurns((prev) => [...prev, researcherTurn]);
    if (!decision) setInput("");
    setBusy(true);
    setAnnouncedReply("");
    followReply.current = true;
    const controller = new AbortController();
    abortRef.current = controller;
    const requestId =
      failedRequest.current?.text === text
        ? failedRequest.current.id
        : newRequestId();
    failedRequest.current = null;
    activeRequest.current = { text, id: requestId, pendingId, decision };
    queueMicrotask(followThread);

    try {
      // sendTurnStreaming resolves to [researcher(server id), platform], which replaces the optimistic turn.
      // The streamed text is presentation only.
      incomingReply.current = "";
      setStreaming(true);
      const appended = await conversationApi.sendTurnStreaming(
        studyId,
        text,
        "You",
        (fragment) => {
          if (abortRef.current !== controller) return;
          incomingReply.current += fragment;
          preview.current?.update();
        },
        steer,
        decision,
        requestId,
        controller.signal,
      );
      if (abortRef.current !== controller) return;
      setStreaming(false);
      setLive(true);
      setUnderstanding(appended.understanding);
      setAnnouncedReply(appended.turns.find((turn) => turn.role === "platform")?.text ?? "");
      setTurns((prev) => {
        /* The opening prompt is not a stored turn; keep it ahead of the server's turns. */
        const openingPrompt = prev.find((t) => t.turnId === "opening");
        return [
          ...(openingPrompt ? [openingPrompt] : []),
          ...prev.filter(
            (t) => t.turnId !== pendingId && t.turnId !== "opening" && !appended.turns.some((next) => next.turnId === t.turnId),
          ),
          ...appended.turns,
        ];
      });
      /* A reply to a decision never takes the caret; focus stays where the researcher put it. */
      if (!decision && followReply.current) setFocusMoveId(firstProposed(appended.turns));
      queueMicrotask(followThread);
      const queued = queuedFollowUp.current;
      if (queued) {
        queuedFollowUp.current = null;
        queueMicrotask(() => void sendTextRef.current(queued.text, queued.decision, true));
      }
    } catch (e) {
      if (abortRef.current !== controller) return;
      /* No invented reply when the server is unreachable. The typed text returns to the composer,
      * so a retry does not show it twice. */
      failedRequest.current = { text, id: requestId };
      setTurns((prev) => prev.filter((t) => t.turnId !== pendingId));
      if (!decision) setInput((current) => current || text);
      setLive(e instanceof ApiError);
      if (e instanceof ApiError) {
        setNote(plainErrorMessage(e, "Your message could not be sent. Try again."), "problem");
      } else {
        setNote(
          decision
            ? "The decision is saved. The assistant could not follow up."
            : "Connection interrupted. Your message is back in the box.",
          "offline",
        );
      }
      queueMicrotask(followThread);
    } finally {
      if (abortRef.current === controller) {
        setStreaming(false);
        setBusy(false);
        abortRef.current = null;
        activeRequest.current = null;
      }
    }
  }

  sendTextRef.current = sendText;

  function stopReply() {
    const request = activeRequest.current;
    if (!request) return;
    queuedFollowUp.current = null;
    abortRef.current?.abort();
    abortRef.current = null;
    activeRequest.current = null;
    failedRequest.current = { text: request.text, id: request.id };
    setTurns((prev) => prev.filter((turn) => turn.turnId !== request.pendingId));
    if (!request.decision) setInput((current) => current || request.text);
    setStreaming(false);
    setBusy(false);
    setNote(request.decision ? "Stopped the assistant’s follow-up." : "Stopped. Your message is back in the box.");
    requestAnimationFrame(() => composer.current?.focus());
  }

  /* Undo remounts the card in the open list; the caret follows it instead of dropping to body. */
  function focusDecidedCard(moveId: string) {
    requestAnimationFrame(() =>
      requestAnimationFrame(() =>
        document
          .querySelector<HTMLElement>(`[data-move-id="${CSS.escape(moveId)}"]`)
          ?.focus(),
      ),
    );
  }

  function restoreMove(moveId: string, status: MoveStatus | undefined) {
    if (status === undefined) return;
    setTurns((prev) =>
      prev.map((t) => ({
        ...t,
        moves: t.moves.map((m) => (m.moveId === moveId ? { ...m, status } : m)),
      })),
    );
  }

  /* Marks each paper added only once its save is under way; a failed save unmarks it for retry. */
  function addPapers(papers: { ref: string; why: string }[], failure: string) {
    if (!live) return;
    for (const { ref, why } of papers) {
      if (addedRefs.has(ref)) continue;
      setAddedRefs((prev) => new Set(prev).add(ref));
      studyApi.addPaperFromMatch(studyId, ref, why).catch(() => {
        setAddedRefs((prev) => {
          const next = new Set(prev);
          next.delete(ref);
          return next;
        });
        setNote(failure, "problem");
      });
    }
  }

  async function decide(
    moveId: string,
    status: MoveStatus,
    renderedMove?: DesignMove,
  ) {
    if (!live) return;
    const move =
      renderedMove ?? turns.flatMap((t) => t.moves).find((m) => m.moveId === moveId);
    if (!move) return;
    const previousStatus = move.status;
    /* Its other cards decide whether the assistant is asked for another turn. */
    const ownTurnMoves = turns.find((t) => t.moves.some((m) => m.moveId === moveId))?.moves ?? [];
    const followUp = shouldFollowUpAfterDecision(ownTurnMoves, moveId, status);
    /* A card that had the caret is about to lose its Accept/Reject controls:
     * hand focus to the next undecided card, or to this card's Undo. */
    const heldFocus =
      status !== "proposed" &&
      document.activeElement?.closest<HTMLElement>("[data-move-id]")?.dataset
        .moveId === moveId;
    if (status === "proposed" && document.activeElement?.closest<HTMLElement>("[data-move-undo]")?.dataset.moveUndo === moveId) {
      focusDecidedCard(moveId);
    }
    if (heldFocus) {
      const target = nextFocusAfterDecision(
        ownTurnMoves.length ? ownTurnMoves : turns.flatMap((t) => t.moves),
        moveId,
      );
      requestAnimationFrame(() =>
        requestAnimationFrame(() => {
          const el =
            target.kind === "move"
              ? document.querySelector<HTMLElement>(
                  `[data-move-id="${CSS.escape(target.moveId)}"]`,
                )
              : document.querySelector<HTMLElement>(
                  `[data-move-undo="${CSS.escape(target.moveId)}"]`,
                );
          const history = el?.closest("details");
          if (history && target.kind === "undo") history.open = true;
          el?.focus();
        }),
      );
    }
    setDecisionsSaving((current) => current + 1);
    setTurns((prev) =>
      prev.map((t) => ({
        ...t,
        moves: t.moves.map((m) => (m.moveId === moveId ? { ...m, status } : m)),
      })),
    );
    try {
      await conversationApi.decide(studyId, moveId, status);
    } catch {
      restoreMove(moveId, previousStatus);
      setNote("Decision not saved: the server did not respond. Try again.", "problem");
      return;
    } finally {
      setDecisionsSaving((current) => current - 1);
    }
    if (status === "proposed") return;

    if (move.grounding.some((g) => g.evidence)) return;
    /* Accepting a card endorses the papers it cites, so they join the study. */
    if (status === "accepted") {
      addPapers(
        move.grounding.map((g) => ({ ref: g.ref, why: g.why })),
        "Accepted, but its cited paper was not added to the study. Retry from Literature.",
      );
    }

    /* The action also travels as structured context so the model cannot mistake it for a new idea. */
    if (!followUp) return;
    const action: DecisionTrigger["action"] =
      status === "rejected" ? "rejected" : move.kind === "caution" ? "noted" : "accepted";
    const actionText =
      action === "rejected"
        ? rejectedMoveText(move.kind)
        : action === "noted"
          ? notedMoveText(move.proposal)
          : acceptedMoveText(move.proposal);
    if (busy) {
      queuedFollowUp.current = { text: actionText, decision: { moveId, action } };
      setNote("Saved. The assistant will answer once its current reply has finished.");
    } else {
      await sendText(actionText, { moveId, action });
    }
  }

  async function acceptBatch(moves: DesignMove[]) {
    if (!live) return;
    const pending = moves.filter(
      (move) => move.status === "proposed" && move.kind !== "caution",
    );
    if (pending.length < 2) return;
    const streaming = busy;
    if (!streaming) setBusy(true);
    setDecisionsSaving((current) => current + 1);
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
      // In order, so a failure part-way never claims the whole batch saved.
      for (const move of pending) {
        await conversationApi.decide(studyId, move.moveId, "accepted");
        saved.push(move);
      }
      addPapers(
        pending.flatMap((move) => move.grounding).filter((g) => !g.evidence).map((g) => ({ ref: g.ref, why: g.why })),
        "Some cited papers were not added to the study. Retry from Literature.",
      );
      setNote(`${saved.length} choices were accepted together. Review the draft, then continue with any open detail.`);
    } catch {
      setTurns((prev) =>
        prev.map((turn) => ({
          ...turn,
          moves: turn.moves.map((move) =>
            pending.some((candidate) => candidate.moveId === move.moveId)
              ? {
                  ...move,
                  status: saved.some((candidate) => candidate.moveId === move.moveId)
                    ? ("accepted" as const)
                    : ("proposed" as const),
                }
              : move,
          ),
        })),
      );
      setNote(`${saved.length} choices were saved; the rest remain open. Try again when the connection is stable.`, "problem");
    } finally {
      setDecisionsSaving((current) => current - 1);
      if (!streaming) setBusy(false);
    }
    /* One follow-up for the whole batch, not one per card. */
    if (saved.length === pending.length) {
      const text = acceptedBatchText(saved.length);
      const decision: DecisionTrigger = { moveId: pending[pending.length - 1].moveId, action: "accepted" };
      if (streaming) {
        queuedFollowUp.current = { text, decision };
      } else {
        await sendText(text, decision, true);
      }
    }
  }

  function addPaper(ref: string) {
    const rec = turns.flatMap((t) => t.recommendations).find((r) => r.ref === ref);
    addPapers([{ ref, why: rec?.matchReason ?? "" }], "Paper not added: check the connection and retry.");
  }

  async function showSavedDraft() {
    setLive(true);
    onProtocolChanged?.();
    try {
      await reloadConversation();
    } catch {
      setNote("Draft saved. Reload the workspace to see the latest decisions.", "problem");
    }
  }

  function openReview() {
    setApplyError(null);
    setApplied(false);
    setShowFinish(true);
    if (!currentCompileResult && !compiling) void refreshCompile();
  }

  async function applyDraft() {
    if (!currentCompileResult?.valid || missingCoreSlots.length > 0 || compiling || decisionsSaving > 0 || applying) return;
    setApplying(true);
    setApplyError(null);
    try {
      await conversationApi.approve(studyId, currentCompileResult.compilationId);
      setApplied(true);
      onProtocolChanged?.();
      setNote("Draft applied to the protocol.");
      await refreshCompile();
    } catch (error) {
      setApplyError(plainErrorMessage(error, "The protocol could not be applied. Try again."));
      if (error instanceof ApiError && error.status === 409) {
        setCompileResult(null);
        setCompiledMovesSignature(null);
        try {
          const updated = await reloadConversation();
          if (JSON.stringify(updated.flatMap((turn) => turn.moves)) === movesSignature) {
            await refreshCompile();
          }
        } catch {
          // Keep the conflict visible and the stale draft disabled.
        }
      }
    } finally {
      setApplying(false);
    }
  }

  const activePlatformIndex = [...turns]
    .map((turn, index) => ({ turn, index }))
    .reverse()
    .find(({ turn }) => turn.role === "platform" && turn.turnId !== "opening")?.index ?? -1;
  const activePlatform = activePlatformIndex >= 0 ? turns[activePlatformIndex] : null;
  // Keep researcher messages visible even when their wording resembles a card decision.
  const conversationTurns = turns.filter(turn => turn.turnId !== "opening");
  const visibleCompile = currentCompileResult && missingCoreSlots.length > 0
    ? {
        ...currentCompileResult,
        valid: false,
        // The server's compile names gaps in its own words; merging the client's slot keys
        // as well would list the same gap twice.
        unresolved: currentCompileResult.unresolved.length > 0
          ? currentCompileResult.unresolved
          : missingCoreSlots,
      }
    : currentCompileResult;
  const scopeBlocked = activePlatform?.source === "scope";
  const welcome = !conversationLoading && !conversationLoadFailed && threadEmpty && !openingPending && conversationTurns.length === 0;
  const mayDecide = mayCompile && live;
  const messageComposer = mayCompile && !conversationLoadFailed ? (
    <form
      className={cn("mx-auto w-full max-w-reading bg-surface", !welcome && "px-4 pb-4 pt-2 sm:px-8")}
      onSubmit={(event) => { event.preventDefault(); send(); }}
    >
      <div className="composer focus-ring-owned mx-auto flex w-full max-w-reading items-end gap-2 rounded-card border border-border bg-surface px-3 py-2 has-[textarea:focus]:outline has-[textarea:focus]:outline-2 has-[textarea:focus]:outline-accent">
        <SteerDial value={steer} onChange={changeSteer} />
        <textarea
          ref={composer}
          className="focus-ring-owned outline-none type-body-lg min-h-8 min-w-0 flex-1 resize-none overflow-y-auto border-0 bg-transparent px-1 py-1 text-text placeholder:text-text-muted"
          placeholder={welcome ? "Describe your research question…" : "Message the design assistant…"}
          value={input}
          rows={1}
          readOnly={streaming && !activeRequest.current?.decision}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault(); send();
            }
          }}
          aria-label="Message the design assistant"
        />
          {streaming ? (
            <Button type="button" size="icon" variant="outline" aria-label="Stop reply" onClick={(event) => { event.preventDefault(); stopReply(); }}><Square aria-hidden /></Button>
          ) : (
            <Button type="submit" size="icon" aria-label="Send" title="Send message" disabled={busy || !input.trim() || conversationLoading}><Send aria-hidden /></Button>
          )}
      </div>
    </form>
  ) : null;

  return (
    <div
      className={cn("split-rail chat-workspace h-full bg-surface", draftFolded && "rail-folded")}
    >
      <section className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden">
        <div
          className="flex min-h-0 min-w-0 flex-1 flex-col overflow-auto"
          onWheel={(event) => { if (event.deltaY < 0) followReply.current = false; }}
          onKeyDown={(event) => {
            if (["PageUp", "Home", "ArrowUp"].includes(event.key)) followReply.current = false;
          }}
          onScroll={(event) => {
            const thread = event.currentTarget;
            followReply.current = thread.scrollHeight - thread.scrollTop - thread.clientHeight < 80;
          }}
        >
          <header className="mx-auto w-full max-w-reading bg-surface px-4 py-1 sm:px-8">
            <h2 className="sr-only">Study design chat</h2>
            <div className="mx-auto flex w-full max-w-reading items-center justify-end gap-1">
                {mayDecide && <Button className={cn(!draftFolded && "md:hidden")} variant="ghost" size="sm" onClick={openReview}>
                  Review draft
                </Button>}
                {mayDecide && <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" aria-label="Research tools" title="Research tools"><MoreHorizontal aria-hidden /></Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onSelect={() => setEvidenceOpen(open => !open)}>{evidenceOpen ? "Close method comparison" : "Compare methods"}</DropdownMenuItem>
                    {live && <DropdownMenuItem onSelect={() => setManualOpen(true)}>Enter protocol manually</DropdownMenuItem>}
                  </DropdownMenuContent>
                </DropdownMenu>}
            </div>
          </header>

          {evidenceOpen && <EvidencePanel studyId={studyId} onClose={() => { setEvidenceOpen(false); queueMicrotask(() => composer.current?.focus()); }} onProposed={async () => { const updated = await reloadConversation(); setLive(true); setNote(null); setEvidenceOpen(false); setFocusMoveId(firstProposed(updated)); }} />}

          <div className={cn("mx-auto flex w-full max-w-reading flex-col gap-5 px-4 py-5 sm:px-8 sm:py-8", welcome && "flex-1 justify-center pb-12")}>
            {conversationLoading ? (
              <div className="space-y-3 py-2" role="status" aria-busy="true" aria-label="Loading conversation">
                <div className="h-3 w-24 animate-pulse rounded-full bg-border" />
                <div className="h-4 w-4/5 animate-pulse rounded-full bg-border" />
                <div className="h-4 w-3/5 animate-pulse rounded-full bg-border" />
              </div>
            ) : conversationLoadFailed ? (
              <div className="space-y-3">
                <Notice kind="problem">The study conversation couldn’t be loaded.</Notice>
                <Button variant="outline" onClick={() => {
                  setConversationLoading(true);
                  setConversationLoadFailed(false);
                  setLoadAttempt((attempt) => attempt + 1);
                }}>Retry conversation</Button>
              </div>
            ) : welcome && mayCompile ? (
              <ConversationStart
                onUse={takeOpening}
                onEnterManually={live ? () => setManualOpen(true) : undefined}
                composer={messageComposer}
              />
            ) : welcome ? (
              <p className="type-body text-text-muted">No messages have been recorded for this study.</p>
            ) : (
              <div className="flex flex-col gap-5">
                {conversationTurns.map(turn => (
                  <div key={turn.turnId}>
                    <StreamingTurn
                      turn={turn === activePlatform ? turn : { ...turn, moves: [] }}
                      onDecide={mayDecide ? decide : undefined}
                      onAcceptBatch={mayDecide && turn === activePlatform ? acceptBatch : undefined}
                      focusMoveId={turn === activePlatform ? focusMoveId : null}
                      active
                      showKeyHint={turn === activePlatform}
                    />
                    {/* Pending choices stay open after a later turn lands; only fully decided turns fold away. */}
                    {turn !== activePlatform && turn.moves.some(move => move.status === "proposed") && (
                      <StreamingTurn
                        turn={{ ...turn, text: "" }}
                        onDecide={mayDecide ? decide : undefined}
                        onAcceptBatch={mayDecide ? acceptBatch : undefined}
                        active
                      />
                    )}
                    {turn !== activePlatform && turn.moves.length > 0 && !turn.moves.some(move => move.status === "proposed") && (
                      <details className="mt-2">
                        <summary className="type-caption cursor-pointer text-text-muted">
                          Decisions ({turn.moves.length})
                        </summary>
                        <StreamingTurn turn={{ ...turn, text: "" }} onDecide={mayDecide ? decide : undefined} />
                      </details>
                    )}
                  </div>
                ))}
                {streaming && (
                  <StreamingReply
                    key={activeRequest.current?.pendingId}
                    ref={preview}
                    source={incomingReply}
                    follow={followThread}
                  />
                )}
              </div>
            )}

            {/* Announced once, when a reply finishes streaming: a live region
              * whose text changes per token would read the stream aloud. */}
            <div className="sr-only" role="status" aria-live="polite" data-testid="turn-announcer">
              {announcedReply}
            </div>
            <div ref={threadEnd} />
          </div>
        </div>

        {/* Always mounted so a screen reader announces a note that appears
          * (Stopped, Saved, failures) rather than missing a new region. */}
        <div role="status">
          {note && !evidenceOpen && (
            <div className="border-t border-border bg-surface px-4 py-2 sm:px-6">
              {/* role none: the wrapper's status region already announces it. */}
              <Notice kind={note.kind} role="none" className="mx-auto w-full max-w-bubble">
                {note.text}
              </Notice>
            </div>
          )}
        </div>

        {!welcome && messageComposer}
      </section>

      {/* Right rail, from 768px: the protocol draft or the chat's papers.
          It folds to a labelled strip; the choice persists per study. */}
      <div
        className={cn(
          "hidden min-h-0 min-w-0 flex-col border-l border-border bg-surface md:flex",
          /* The expanded rail takes its width from the grid; the folded rail sizes the auto track. */
          draftFolded ? "w-12" : "w-full",
        )}
      >
        {draftFolded ? (
          <div className="flex h-full flex-col items-center py-3">
            <button
              type="button"
              aria-expanded={false}
              className="type-caption flex flex-col items-center gap-3 rounded-control px-2 py-3 text-text-muted hover:bg-zone-9 hover:text-text"
              onClick={() => togglePanel("draft", studyId)}
            >
              <PanelRight className="size-4" aria-hidden />
              <span className="[writing-mode:vertical-rl]">Protocol draft</span>
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2 border-b border-border-strong bg-surface p-2">
            <SegmentedControl
              value={rail}
              onChange={changeRail}
              className="min-w-0 flex-1"
              aria-label="Right panel"
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
        <div className={cn("min-h-0 min-w-0 flex-1 overflow-hidden", draftFolded && "hidden")}>
          {rail === "papers" ? (
            <RecommenderRail
              recommendations={recommendations}
              addedRefs={addedRefs}
              onAdd={mayDecide ? addPaper : undefined}
            />
          ) : (
            <DraftRail
              onNextStep={mayDecide ? (label) => takeOpening(nextStepPrompt(label)) : undefined}
              understanding={understanding}
              scopeBlocked={scopeBlocked}
              loading={conversationLoading}
              draft={clientDraft}
              serverYaml={conversationLoading ? undefined : currentCompileResult?.yaml}
              protocol={
                conversationLoading
                  ? undefined
                  : currentCompileResult?.protocol ?? readOnlyProtocol ?? undefined
              }
              compileValid={visibleCompile?.valid}
              unresolved={visibleCompile?.unresolved}
              compileErrors={currentCompileResult?.errors}
              /* A reader can see the record; only a contributor can change it,
               * so the actions stay off when the compile came back 403. */
              onEdit={live && currentCompileResult ? () => setManualOpen(true) : undefined}
              onFinish={
                live && currentCompileResult
                  ? openReview
                  : undefined
              }
            />
          )}
        </div>
      </div>

      {manualOpen && (
        <ManualProtocolDialog
          studyId={studyId}
          protocol={currentCompileResult?.protocol}
          moves={allMoves}
          onClose={() => setManualOpen(false)}
          onEntered={() => void showSavedDraft()}
        />
      )}
      <FinishReview
        open={showFinish}
        onOpenChange={setShowFinish}
        moves={sinceManualEntry(allMoves)}
        earlierMoves={allMoves.slice(0, allMoves.length - sinceManualEntry(allMoves).length)}
        compile={visibleCompile}
        compiling={compiling || decisionsSaving > 0}
        applying={applying}
        applyError={applyError}
        applied={applied}
        onApply={applyDraft}
      />
    </div>
  );
}
