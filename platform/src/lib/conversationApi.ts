import type { DesignMove, Grounding, Recommendation, Turn } from "./types";
import { getAuthToken, notifyUnauthorized } from "./api.ts";
import { OfflineError } from "./studyApi";
import { openingTurn, respondTo } from "./designStub";

const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
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
    // proxy) means there's no real API behind this origin — same offline
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
      tier: (row.tier as Grounding["tier"]) ?? "B",
      confidence: typeof row.confidence === "number" ? row.confidence : undefined,
      title: String(row.title ?? row.ref ?? ""),
      year: typeof row.year === "number" ? row.year : undefined,
      venue: typeof row.venue === "string" ? row.venue : undefined,
      why: String(row.why ?? ""),
    };
  });
}

function mapMove(raw: Record<string, unknown>): DesignMove {
  const patch = raw.patch as Record<string, unknown> | undefined;
  let draftPatch: DesignMove["patch"];
  if (patch && typeof patch.section === "string" && patch.op) {
    draftPatch = {
      section: patch.section as DesignMove["patch"] extends infer P
        ? P extends { section: infer S }
          ? S
          : never
        : never,
      op: patch.op as "append" | "set",
      key: typeof patch.key === "string" ? patch.key : undefined,
      value: String(patch.value ?? ""),
    };
  }
  return {
    moveId: String(raw.moveId ?? ""),
    kind: (raw.kind as DesignMove["kind"]) ?? "add-rq",
    target: String(raw.target ?? ""),
    proposal: String(raw.proposal ?? ""),
    patch: draftPatch,
    grounding: mapGrounding((raw.grounding as unknown[]) ?? []),
    status: (raw.status as DesignMove["status"]) ?? "proposed",
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
    source: raw.source === "llm" ? "llm" : raw.source === "scripted" ? "scripted" : undefined,
  };
}

export interface CompileResult {
  compilationId: string;
  valid: boolean;
  errors: string[];
  unresolved: string[];
  diff: string;
  yaml: string;
  templateId: string | null;
}

export const conversationApi = {
  async get(studyId: string): Promise<Turn[]> {
    const data = await req<{ turns: Record<string, unknown>[] }>(
      `/studies/${encodeURIComponent(studyId)}/conversation`,
    );
    const turns = data.turns.map(mapTurn);
    return turns.length ? turns : [openingTurn()];
  },

  async sendTurn(
    studyId: string,
    text: string,
    author = "You",
  ): Promise<{ turns: Turn[] }> {
    const reply = await post<{
      researcherTurnId: string;
      platformTurnId: string;
      text: string;
      moves: Record<string, unknown>[];
      recommendations: Recommendation[];
      source?: "llm" | "scripted";
    }>(`/studies/${encodeURIComponent(studyId)}/conversation/turns`, {
      text,
      author,
    });
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
    return { turns: [researcher, platform] };
  },

  /** The public hero's real-LLM demo turn (FR-CONV-1.4): stateless and
   * unauthenticated, so the visitor's prior turns ride along as history and
   * nothing is persisted. Rate-limited server-side. */
  async demoTurn(
    text: string,
    history: { role: "user" | "assistant"; content: string }[],
  ): Promise<Turn> {
    const reply = await post<{
      text: string;
      moves: Record<string, unknown>[];
      recommendations: Recommendation[];
      source?: "llm" | "scripted";
    }>(`/demo/conversation/turns`, { text, history });
    return {
      turnId: `demo-${history.length}`,
      role: "platform",
      author: "Platform",
      text: reply.text,
      moves: reply.moves.map(mapMove),
      recommendations: reply.recommendations ?? [],
      source: reply.source,
    };
  },

  decide(studyId: string, moveId: string, status: "accepted" | "rejected") {
    return post<{ moveId: string; status: string }>(
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
    return post<{ applied: boolean }>(
      `/studies/${encodeURIComponent(studyId)}/conversation/approve`,
      { compilationId, rationale, approvedBy: "Researcher" },
    );
  },

  markFeedback(
    studyId: string,
    turnId: string,
    note: string,
    kind: string,
  ) {
    return post<{ findingId: number }>(
      `/studies/${encodeURIComponent(studyId)}/conversation/turns/${encodeURIComponent(turnId)}/feedback`,
      { note, kind },
    );
  },

  /** Offline-only path: deterministic stub reply (hero / no middleware). */
  stubSend(text: string, turnsLength: number): Turn[] {
    const researcherTurn: Turn = {
      turnId: `r-${turnsLength}`,
      role: "researcher",
      author: "You",
      text,
      moves: [],
      recommendations: [],
    };
    return [researcherTurn, respondTo(text)];
  },
};

/** Callers (`ConversationView`) need to tell a genuine live load apart from
 * an offline fallback so `live` state stays accurate — swallowing
 * `OfflineError` here would report success either way and leave the caller
 * stuck retrying doomed live calls. Let it throw; the caller's own catch
 * already falls back to `[openingTurn()]` and flips `live` off. */
export function loadConversation(studyId: string, stubOnly: boolean): Promise<Turn[]> {
  if (stubOnly) return Promise.resolve([openingTurn()]);
  return conversationApi.get(studyId);
}
