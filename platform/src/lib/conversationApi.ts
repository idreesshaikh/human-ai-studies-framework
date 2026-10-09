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
import { ApiError, getAuthToken, notifyUnauthorized } from "./api.ts";
import { OfflineError } from "./studyApi.ts";
import { openingTurn } from "./conversationOpening.ts";
import { shouldResendAfterStreamFailure } from "./streamRecovery.ts";

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

export function newRequestId(): string {
  return (
    globalThis.crypto?.randomUUID?.() ??
    `conversation-${Date.now()}-${Math.random().toString(36).slice(2)}`
  );
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
    throw new ApiError(
      res.status,
      typeof detail === "string" && detail
        ? detail
        : `Request failed (${res.status})`,
    );
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
      confidence:
        typeof row.confidence === "number" ? row.confidence : undefined,
      title: String(row.title ?? row.ref ?? ""),
      year: typeof row.year === "number" ? row.year : undefined,
      venue: typeof row.venue === "string" ? row.venue : undefined,
      why: String(row.why ?? ""),
      evidence: row.evidence as Grounding["evidence"],
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
      manual: patch.manual === true || undefined,
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
  if (
    typeof patch.section === "string" &&
    (patch.op === "append" || patch.op === "set")
  ) {
    return {
      section: patch.section as keyof ProtocolDraft,
      op: patch.op,
      key: typeof patch.key === "string" ? patch.key : undefined,
      value: patch.value && typeof patch.value === "object"
        ? patch.value as Record<string, unknown> | unknown[]
        : String(patch.value ?? ""),
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
    recommendations: (raw.recommendations as Recommendation[]) ?? [],
    source:
      raw.source === "llm" ||
      raw.source === "scripted" ||
      raw.source === "unavailable" ||
      raw.source === "scope"
        ? raw.source
        : undefined,
  };
}

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

/** The protocol fields a researcher can enter directly (server: QuickProtocolIn). */
export interface ManualProtocolFields {
  title: string;
  researchQuestions: string[];
  design: "within-subjects" | "between-subjects";
  conditions: string[];
  participantDescription: string;
  plannedParticipants: number;
  taskDescription: string;
  sessionMinutes: number;
  measures: string[];
  measureIds?: string[];
  existingMeasureIds?: string[];
  typedMeasures?: boolean;
  counterbalanced: boolean;
}

export interface MeasureChoice {
  id: string;
  construct: string;
  description: string;
  instrument: string;
  fields: string[];
  aliases: string[];
  recipeByDesign: Record<ManualProtocolFields["design"], string | null>;
  designCompatible?: boolean;
}

export const conversationApi = {
  async measureCatalog(): Promise<MeasureChoice[]> {
    const catalog = await req<{ measures: MeasureChoice[] }>("/measure-catalog");
    return catalog.measures;
  },

  measureSuggestions(studyId: string, text: string, design: ManualProtocolFields["design"], signal?: AbortSignal) {
    return req<{ suggestions: MeasureChoice[]; abstain: boolean }>(
      `/studies/${encodeURIComponent(studyId)}/measure-suggestions`,
      { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text, design }), signal },
    );
  },

  async get(
    studyId: string,
  ): Promise<{ turns: Turn[]; understanding?: Understanding }> {
    const data = await req<{
      turns: Record<string, unknown>[];
      understanding?: Understanding;
    }>(`/studies/${encodeURIComponent(studyId)}/conversation`);
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
     * conversation (see lib/steer.ts). Optional so older clients can still
     * post a valid turn without it; the server falls back to the account's
     * declared profile. */
    steer?: SteerLevel,
    decision?: DecisionTrigger,
    requestId?: string,
  ): Promise<{ turns: Turn[]; understanding?: Understanding }> {
    const reply = await post<ConversationReply>(
      `/studies/${encodeURIComponent(studyId)}/conversation/turns`,
      {
        text,
        author,
        ...(steer == null ? {} : { steer: steerStop(steer).id }),
        ...(decision ? { decision } : {}),
        ...(requestId ? { requestId } : {}),
      },
    );
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
    return {
      turns: [researcher, platform],
      understanding: reply.understanding,
    };
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
    /* Lets the researcher cancel a reply that is taking too long (the Stop
     * button). A cancelled turn rejects with an AbortError and is never
     * resent. */
    signal?: AbortSignal,
  ): Promise<{ turns: Turn[]; understanding?: Understanding }> {
    let eventsReceived = 0;
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
          signal,
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
          eventsReceived += 1;
          if (event === "token") onToken?.(String(payload.text ?? ""));
          else if (event === "done") done = payload;
          else if (event === "error") throw new Error(String(payload.detail));
        }
      }
      if (!done) throw new Error("stream ended without a turn");
    } catch (error) {
      /* Resend only when the server had not started answering and the
       * researcher did not cancel. Otherwise the reply may already be
       * persisted, so surface the failure; the caller keeps their text. The
       * resend reuses `requestId`, which the server treats as the same turn. */
      if (
        !shouldResendAfterStreamFailure({
          aborted: signal?.aborted ?? false,
          eventsReceived,
        })
      ) {
        throw error;
      }
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
    return await post<{ moveId: string; status: string }>(
      `/studies/${encodeURIComponent(studyId)}/conversation/moves/${encodeURIComponent(moveId)}/decision`,
      { status, decidedBy: "Researcher" },
    );
  },

  compile(studyId: string, baseYaml?: string | null): Promise<CompileResult> {
    return post<CompileResult>(
      `/studies/${encodeURIComponent(studyId)}/conversation/compile`,
      { baseYaml: baseYaml ?? null },
    );
  },

  enterProtocol(
    studyId: string,
    fields: ManualProtocolFields,
  ): Promise<CompileResult> {
    return post<CompileResult>(
      `/studies/${encodeURIComponent(studyId)}/quick-protocol`,
      fields,
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
