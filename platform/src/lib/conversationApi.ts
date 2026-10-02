import { steerStop, type SteerLevel } from "./steer.ts";
import type {
  DesignMove,
  Grounding,
  MoveStatus,
  ProtocolDraft,
  Recommendation,
  Turn,
  Understanding,
} from "./types.ts";
import { getAuthToken, notifyUnauthorized, request as req, apiBase } from "./api.ts";
import { openingTurn } from "./conversationOpening.ts";

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

const API_BASE = apiBase().replace(/\/+$/, "");

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function newRequestId(): string {
  return globalThis.crypto?.randomUUID?.() ??
    `conversation-${Date.now()}-${Math.random().toString(36).slice(2)}`;
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

export interface CompileResult {
  compilationId: string;
  valid: boolean;
  errors: string[];
  unresolved: string[];

  warnings?: string[];
  diff: string;
  yaml: string;

  protocol?: Record<string, unknown>;
  templateId: string | null;
}

export const conversationApi = {
  async get(
    studyId: string,
  ): Promise<{ turns: Turn[]; understanding?: Understanding; }> {
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

    steer?: SteerLevel,
    decision?: DecisionTrigger,
    requestId?: string,
  ): Promise<{ turns: Turn[]; understanding?: Understanding; }> {
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
    return { turns: [researcher, platform], understanding: reply.understanding };
  },

  async sendTurnStreaming(
    studyId: string,
    text: string,
    author = "You",
    onToken?: (fragment: string) => void,
    steer?: SteerLevel,
    decision?: DecisionTrigger,
    requestId = newRequestId(),
  ): Promise<{ turns: Turn[]; understanding?: Understanding; }> {
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
      for (; ;) {
        const { value, done: finished } = await reader.read();
        if (finished) break;
        buffer += decoder.decode(value, { stream: true });
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
    return post<{ moveId: string; status: string; }>(
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

  approve(studyId: string, compilationId: string, rationale = "") {
    return post<{ applied: boolean; }>(
      `/studies/${encodeURIComponent(studyId)}/conversation/approve`,
      { compilationId, rationale, approvedBy: "Researcher" },
    );
  },

};

export function loadConversation(
  studyId: string,
): Promise<{ turns: Turn[]; understanding?: Understanding; }> {
  return conversationApi.get(studyId);
}
