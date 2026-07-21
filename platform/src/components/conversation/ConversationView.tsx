import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StreamingTurn } from "./StreamingTurn";
import { DraftRail } from "./DraftRail";
import { compileAll } from "@/lib/compiler";
import { openingTurn, respondTo } from "@/lib/designStub";
import {
  conversationApi,
  loadConversation,
  type CompileResult,
} from "@/lib/conversationApi";
import { evolutionStore } from "@/lib/evolutionStub";
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
  /** Hero and static previews stay on the deterministic stub only. */
  stubOnly = false,
  /** A fixed, already-captured transcript to show read-only, with no
   * composer — for the showcase, not a live or stub conversation. */
  replay,
}: {
  studyId?: string;
  stubOnly?: boolean;
  replay?: Turn[];
}) {
  const [turns, setTurns] = useState<Turn[]>(() => replay ?? [openingTurn()]);
  const [input, setInput] = useState("");
  const [addedRefs, setAddedRefs] = useState<Set<string>>(new Set());
  const [markedTurns, setMarkedTurns] = useState<Set<string>>(new Set());
  const [live, setLive] = useState(!stubOnly);
  const [busy, setBusy] = useState(false);
  const [compileResult, setCompileResult] = useState<CompileResult | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const [showDraft, setShowDraft] = useState(false);
  const threadEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (replay) return;
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
  }, [studyId, stubOnly, replay]);

  const allMoves: DesignMove[] = useMemo(
    () => turns.flatMap((t) => t.moves),
    [turns],
  );
  const clientDraft = useMemo(() => compileAll(allMoves), [allMoves]);

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
    setBusy(true);
    try {
      if (live && !stubOnly) {
        const appended = await conversationApi.sendTurn(studyId, text);
        setTurns((prev) => [...prev, ...appended.turns]);
      } else {
        const researcherTurn: Turn = {
          turnId: `r-${turns.length}`,
          role: "researcher",
          author: "You",
          text,
          moves: [],
          recommendations: [],
        };
        const reply = respondTo(text);
        setTurns((prev) => [...prev, researcherTurn, reply]);
      }
      setInput("");
      queueMicrotask(() =>
        threadEnd.current?.scrollIntoView({ block: "end" }),
      );
    } catch {
      // Offline fallback
      const researcherTurn: Turn = {
        turnId: `r-${turns.length}`,
        role: "researcher",
        author: "You",
        text,
        moves: [],
        recommendations: [],
      };
      const reply = respondTo(text);
      setTurns((prev) => [...prev, researcherTurn, reply]);
      setInput("");
      setLive(false);
      setNote("You're offline — replies are coming from the built-in assistant until the connection returns.");
      queueMicrotask(() =>
        threadEnd.current?.scrollIntoView({ block: "end" }),
      );
    } finally {
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

  function addPaper(ref: string) {
    setAddedRefs((prev) => new Set(prev).add(ref));
  }

  async function applyDraft() {
    if (!compileResult?.valid || applying) return;
    setApplying(true);
    try {
      await conversationApi.approve(studyId, compileResult.compilationId);
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
      className="grid h-full grid-cols-1 lg:grid-cols-[1fr_380px]"
    >
      <section className="flex h-full min-h-0 flex-col">
        <div className="min-h-0 flex-1 space-y-6 overflow-auto p-4 sm:p-6">
          {turns.map((t, i) => (
            <StreamingTurn
              key={t.turnId}
              turn={t}
              addedRefs={addedRefs}
              onDecide={decide}
              onAddPaper={addPaper}
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
              <div className="max-w-[46ch] animate-in fade-in rounded-card border border-border bg-surface px-4 py-3 text-sm text-text-muted duration-entrance">
                <span className="mb-1 block text-xs opacity-70">Platform</span>
                <span className="inline-flex items-center gap-1 animate-pulse">
                  <span className="size-1.5 rounded-full bg-text-muted" />
                  <span className="size-1.5 rounded-full bg-text-muted" />
                  <span className="size-1.5 rounded-full bg-text-muted" />
                </span>
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

        {replay ? (
          <div className="border-t border-border-strong bg-surface px-4 py-3 text-center text-xs text-text-muted sm:px-6">
            A real, finished conversation. Start your own to talk it through live.
          </div>
        ) : (
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
              className="min-h-11 flex-1 resize-none rounded-input border border-border-strong bg-bg px-3 py-2 font-mono text-sm text-text focus-visible:border-accent"
              placeholder="Describe what you want to find out…"
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
        )}
      </section>

      <div className={cn("lg:block", showDraft ? "block" : "hidden")}>
        <DraftRail
          draft={clientDraft}
          serverYaml={compileResult?.yaml}
          compileValid={compileResult?.valid}
          onApply={live && !stubOnly ? applyDraft : undefined}
          applying={applying}
        />
      </div>
    </div>
  );
}
