import { steerStop, type SteerLevel } from "./steer";
import type {
  DesignMove,
  Grounding,
  MoveStatus,
  ProtocolDraft,
  Recommendation,
  Turn,
  Understanding,
} from "./types.ts";
import { getAuthToken, notifyUnauthorized } from "./api.ts";
import { OfflineError } from "./studyApi.ts";
import { openingTurn } from "./conversationOpening.ts";
import { isDemoStudy } from "./demo.ts";

export type DecisionTrigger = {
  moveId: string;
  action: "accepted" | "rejected" | "noted";
};

type ConversationReply = {
  researcherTurnId: string;
  platformTurnId: string;
  text: string;
  moves: Record<string, unknown>[];
  recommendations: Recommendation[];
  source?: "llm" | "scripted" | "unavailable" | "scope";
  understanding?: Understanding;
};

const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function newRequestId(): string {
  return globalThis.crypto?.randomUUID?.() ??
    `conversation-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(API_BASE + path, {
      ...init,
      headers: { ...(await authHeaders()), ...(init.headers ?? {}) },
      credentials: "include",
    });
  } catch {
    throw new OfflineError();
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-JSON */
    }
    if (res.status === 401) notifyUnauthorized();
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  try {
    return (await res.json()) as T;
  } catch {
    // A 200 that isn't real JSON (dev-server SPA fallback, misconfigured
    // proxy) means there's no real API behind this origin  -  same offline
    // posture as an unreachable server.
    throw new OfflineError();
  }
}

function post<T>(path: string, body: unknown): Promise<T> {
  return req<T>(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

function mapGrounding(raw: unknown[]): Grounding[] {
  return (raw ?? []).map((g) => {
    const row = g as Record<string, unknown>;
    return {
      ref: String(row.ref ?? ""),
      confidence: typeof row.confidence === "number" ? row.confidence : undefined,
      title: String(row.title ?? row.ref ?? ""),
      year: typeof row.year === "number" ? row.year : undefined,
      venue: typeof row.venue === "string" ? row.venue : undefined,
      why: String(row.why ?? ""),
    };
  });
}

function mapPatch(raw: unknown): DesignMove["patch"] {
  if (!raw || typeof raw !== "object") return undefined;
  const patch = raw as Record<string, unknown>;
  // A choose-template move's patch: {templateId, parameters}  -  no
  // section/op at all, so it must be checked before the generic shape.
  if (typeof patch.templateId === "string" && patch.templateId) {
    return {
      templateId: patch.templateId,
      parameters:
        patch.parameters && typeof patch.parameters === "object"
          ? (patch.parameters as Record<string, unknown>)
          : undefined,
    };
  }
  if (typeof patch.recipeId === "string" && patch.recipeId) {
    return {
      recipeId: patch.recipeId,
      rq: typeof patch.rq === "string" ? patch.rq : undefined,
    };
  }
  if (
    patch.section === "instruments" &&
    typeof patch.op === "string" &&
    ["add-instrument", "set-instrument", "reconfigure"].includes(patch.op) &&
    typeof patch.name === "string" &&
    patch.name
  ) {
    return {
      section: "instruments",
      op: patch.op as "add-instrument" | "set-instrument" | "reconfigure",
      name: patch.name,
      config:
        patch.config && typeof patch.config === "object"
          ? (patch.config as Record<string, unknown>)
          : undefined,
      path: Array.isArray(patch.path) ? (patch.path as string[]) : undefined,
      value: patch.value,
    };
  }
  if (
    patch.op === "set-field" &&
    Array.isArray(patch.path) &&
    patch.path.every((part) => typeof part === "string") &&
    patch.path.length > 0 &&
    "value" in patch
  ) {
    return {
      op: "set-field",
      path: patch.path as string[],
      value: patch.value,
    };
  }
  if (typeof patch.section === "string" && (patch.op === "append" || patch.op === "set")) {
    return {
      section: patch.section as keyof ProtocolDraft,
      op: patch.op,
      key: typeof patch.key === "string" ? patch.key : undefined,
      value: String(patch.value ?? ""),
    };
  }
  return undefined;
}

function mapMove(raw: Record<string, unknown>): DesignMove {
  const rawMerge = raw.mergeData as Record<string, unknown> | undefined;
  return {
    moveId: String(raw.moveId ?? ""),
    kind: (raw.kind as DesignMove["kind"]) ?? "add-rq",
    target: String(raw.target ?? ""),
    proposal: String(raw.proposal ?? ""),
    patch: mapPatch(raw.patch),
    grounding: mapGrounding((raw.grounding as unknown[]) ?? []),
    status: (raw.status as DesignMove["status"]) ?? "proposed",
    mergeData:
      rawMerge &&
      Array.isArray(rawMerge.templateIds) &&
      typeof rawMerge.reason === "string"
        ? {
            templateIds: rawMerge.templateIds.map(String),
            reason: rawMerge.reason,
          }
        : undefined,
  };
}

function mapTurn(raw: Record<string, unknown>): Turn {
  return {
    turnId: String(raw.turnId ?? ""),
    role: raw.role === "researcher" ? "researcher" : "platform",
    author: String(raw.author ?? ""),
    text: String(raw.text ?? ""),
    moves: ((raw.moves as Record<string, unknown>[]) ?? []).map(mapMove),
    recommendations: ((raw.recommendations as Recommendation[]) ?? []),
    source:
      raw.source === "llm" || raw.source === "scripted" || raw.source === "unavailable" || raw.source === "scope"
        ? raw.source
        : undefined,
  };
}

function demoDecisionReply(
  decision: DecisionTrigger,
): ConversationReply {
  const actionText =
    decision.action === "rejected"
      ? "Understood. That proposal stays out of the draft. What should be different: the participants, the task, or the comparison?"
      : decision.action === "noted"
        ? "I’ve noted that caution beside the draft. What will each participant actually do during the session?"
        : "That choice is now part of the draft. What will each participant actually do during the session?";
  return {
    researcherTurnId: `demo-decision-${decision.moveId}-${Date.now()}`,
    platformTurnId: `demo-followup-${decision.moveId}-${Date.now()}`,
    text: actionText,
    moves: [],
    recommendations: [],
    source: "scripted",
  };
}

const DEMO_CONVERSATION: Turn[] = [
  {
    turnId: "demo-turn-researcher",
    role: "researcher",
    author: "Demo Researcher",
    text: "I want to know whether AI assistance changes developer productivity and how carefully developers review the code it suggests.",
    moves: [],
    recommendations: [],
  },
  {
    turnId: "demo-turn-platform",
    role: "platform",
    author: "Platform",
    source: "llm",
    text: "A within-subjects comparison fits this question because the same developer can be compared across matched maintenance tasks with and without AI assistance.",
    moves: [
      {
        moveId: "demo-move-design",
        kind: "choose-template",
        target: "design",
        proposal: "Use a counterbalanced within-subjects design so each developer completes matched tasks in both conditions.",
        patch: { templateId: "within-subjects-crossover-v1", parameters: {} },
        grounding: [
          {
            ref: "corpus:metr-early-2025-dev-productivity",
            confidence: 0.94,
            title: "Measuring the Impact of Early-2025 AI on Developer Productivity",
            year: 2025,
            venue: "METR",
            why: "Pairs perceived productivity with observed task completion and correctness.",
          },
        ],
        status: "accepted",
      },
      {
        moveId: "demo-move-measure",
        kind: "add-measure",
        target: "measures[]",
        proposal: "Measure task completion time, correctness, self-reported fatigue, and review latency in both conditions.",
        patch: { section: "measures", op: "append", value: "task time, correctness, fatigue, and review latency" },
        grounding: [
          {
            ref: "corpus:trust-in-ai-code-generation",
            confidence: 0.98,
            title: "Investigating and Designing for Trust in AI-powered Code Generation",
            year: 2024,
            venue: "Empirical Software Engineering",
            why: "Measures whether developers verify AI-generated code before accepting it.",
          },
        ],
        status: "proposed",
      },
    ],
    recommendations: [
      {
        ref: "corpus:trust-in-ai-code-generation",
        confidence: 0.98,
        title: "Investigating and Designing for Trust in AI-powered Code Generation",
        year: 2024,
        venue: "Empirical Software Engineering",
        matchReason: "Measures whether developers verify AI-generated code before accepting it.",
        inStudy: false,
      },
      {
        ref: "corpus:metr-early-2025-dev-productivity",
        confidence: 0.94,
        title: "Measuring the Impact of Early-2025 AI on Developer Productivity",
        year: 2025,
        venue: "METR",
        matchReason: "Pairs perceived productivity with observed task completion and correctness.",
        inStudy: false,
      },
    ],
  },
];

export interface CompileResult {
  compilationId: string;
  valid: boolean;
  errors: string[];
  unresolved: string[];
  /** Non-blocking compiler notes (e.g. a skipped broken template move);
   * optional so replies from an older server still parse. */
  warnings?: string[];
  diff: string;
  yaml: string;
  /** The compiled protocol as structured data (same dict the server dumps
   * to `yaml`)  -  lets the UI render prose instead of parsing YAML text.
   * Optional so replies from an older server still parse. */
  protocol?: Record<string, unknown>;
  templateId: string | null;
}

export const conversationApi = {
  async get(
    studyId: string,
  ): Promise<{ turns: Turn[]; understanding?: Understanding }> {
    let data: { turns: Record<string, unknown>[]; understanding?: Understanding };
    try {
      data = await req<{
        turns: Record<string, unknown>[];
        understanding?: Understanding;
      }>(`/studies/${encodeURIComponent(studyId)}/conversation`);
    } catch (error) {
      if (error instanceof OfflineError && isDemoStudy(studyId)) {
        return {
          turns: DEMO_CONVERSATION,
          understanding: {
            facets: { population: true, task: true, comparison: true, measures: true },
            known: ["population", "task", "comparison", "measures"],
            missing: [],
            missingLabels: [],
            readyForDesign: true,
            facetsNeeded: 4,
            nextQuestion: "",
          },
        };
      }
      throw error;
    }
    const turns = data.turns.map(mapTurn);
    return {
      turns: turns.length ? turns : [openingTurn()],
      understanding: data.understanding,
    };
  },

  async sendTurn(
    studyId: string,
    text: string,
    author = "You",
    /* How much the researcher wants the assistant to drive this
     * conversation (see lib/steer.ts). Optional so an older client, and the
     * agent-facing API, both still post a valid turn without it; the server
     * falls back to the account's declared profile. */
    steer?: SteerLevel,
    decision?: DecisionTrigger,
    requestId?: string,
  ): Promise<{ turns: Turn[]; understanding?: Understanding }> {
    let reply: ConversationReply;
    try {
      reply = await post<ConversationReply>(
        `/studies/${encodeURIComponent(studyId)}/conversation/turns`,
        {
          text,
          author,
          ...(steer == null ? {} : { steer: steerStop(steer).id }),
          ...(decision ? { decision } : {}),
          ...(requestId ? { requestId } : {}),
        },
      );
    } catch (error) {
      /* The demo is intentionally useful without a middleware process. Its
       * decision cards still need to demonstrate the same interaction as a
       * live study, but normal demo messages must remain honest about offline
       * model access. */
      if (!(isDemoStudy(studyId) && decision)) throw error;
      reply = demoDecisionReply(decision);
    }
    const researcher: Turn = {
      turnId: reply.researcherTurnId,
      role: "researcher",
      author,
      text,
      moves: [],
      recommendations: [],
    };
    const platform: Turn = {
      turnId: reply.platformTurnId,
      role: "platform",
      author: "Platform",
      text: reply.text,
      moves: reply.moves.map(mapMove),
      recommendations: reply.recommendations ?? [],
      source: reply.source,
    };
    return { turns: [researcher, platform], understanding: reply.understanding };
  },

  /** `sendTurn`, with the reply's prose surfaced as the model writes it.
   *
   * `onToken` is called with each prose fragment; the resolved value is the
   * same `{turns}` the blocking call returns, so a caller can treat the
   * stream as presentation only. Any streaming failure  -  no SSE support, a
   * proxy that buffers, a mid-stream drop  -  falls back to `sendTurn`, so
   * the turn is never lost to a display feature. */
  async sendTurnStreaming(
    studyId: string,
    text: string,
    author = "You",
    onToken?: (fragment: string) => void,
    steer?: SteerLevel,
    decision?: DecisionTrigger,
    requestId = newRequestId(),
  ): Promise<{ turns: Turn[]; understanding?: Understanding }> {
    let done: {
      researcherTurnId: string;
      platformTurnId: string;
      text: string;
      moves: Record<string, unknown>[];
      recommendations: Recommendation[];
      source?: "llm" | "scripted" | "unavailable" | "scope";
      understanding?: Understanding;
    } | null = null;
    try {
      const res = await fetch(
        `${API_BASE}/studies/${encodeURIComponent(studyId)}/conversation/turns/stream`,
        {
          method: "POST",
          headers: {
            ...(await authHeaders()),
            "content-type": "application/json",
            accept: "text/event-stream",
          },
          credentials: "include",
          body: JSON.stringify({
            text,
            author,
            ...(steer == null ? {} : { steer: steerStop(steer).id }),
            ...(decision ? { decision } : {}),
            requestId,
          }),
        },
      );
      if (res.status === 401) notifyUnauthorized();
      if (!res.ok || !res.body) throw new Error("stream unavailable");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { value, done: finished } = await reader.read();
        if (finished) break;
        buffer += decoder.decode(value, { stream: true });
        // SSE frames are separated by a blank line; keep the partial tail.
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          const event = /^event: (.+)$/m.exec(frame)?.[1];
          const raw = /^data: (.*)$/m.exec(frame)?.[1];
          if (!event || raw == null) continue;
          const payload = JSON.parse(raw);
          if (event === "token") onToken?.(String(payload.text ?? ""));
          else if (event === "done") done = payload;
          else if (event === "error") throw new Error(String(payload.detail));
        }
      }
      if (!done) throw new Error("stream ended without a turn");
    } catch {
      return this.sendTurn(studyId, text, author, steer, decision, requestId);
    }

    const researcher: Turn = {
      turnId: done.researcherTurnId,
      role: "researcher",
      author,
      text,
      moves: [],
      recommendations: [],
    };
    const platform: Turn = {
      turnId: done.platformTurnId,
      role: "platform",
      author: "Platform",
      text: done.text,
      moves: done.moves.map(mapMove),
      recommendations: done.recommendations ?? [],
      source: done.source,
    };
    return { turns: [researcher, platform], understanding: done.understanding };
  },

  async decide(studyId: string, moveId: string, status: MoveStatus) {
    try {
      return await post<{ moveId: string; status: string }>(
        `/studies/${encodeURIComponent(studyId)}/conversation/moves/${encodeURIComponent(moveId)}/decision`,
        { status, decidedBy: "Researcher" },
      );
    } catch (error) {
      if (isDemoStudy(studyId)) return { moveId, status };
      throw error;
    }
  },

  compile(studyId: string, baseYaml?: string | null): Promise<CompileResult> {
    return post<CompileResult>(
      `/studies/${encodeURIComponent(studyId)}/conversation/compile`,
      { baseYaml: baseYaml ?? null },
    );
  },

  approve(studyId: string, compilationId: string, rationale = "") {
    return post<{ applied: boolean }>(
      `/studies/${encodeURIComponent(studyId)}/conversation/approve`,
      { compilationId, rationale, approvedBy: "Researcher" },
    );
  },

};

/** Callers (`ConversationView`) need to tell a genuine live load apart from
 * an offline fallback so `live` state stays accurate  -  swallowing
 * `OfflineError` here would report success either way and leave the caller
 * stuck retrying doomed live calls. Let it throw; the caller's own catch
 * keeps the thread as it is and says why. */
export function loadConversation(
  studyId: string,
): Promise<{ turns: Turn[]; understanding?: Understanding }> {
  return conversationApi.get(studyId);
}
