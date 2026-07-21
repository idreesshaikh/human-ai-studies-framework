import type { Amendment, AmendmentState, PlatformFinding, RetrospectiveProposal } from "./types";
import { getAuthToken, notifyUnauthorized } from "./api.ts";
import { OfflineError } from "./studyApi";
import { deriveProposal, evolutionStore } from "./evolutionStub";

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
      /* ignore */
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

function mapAmendment(a: Record<string, unknown>): Amendment {
  return {
    id: String(a.id ?? ""),
    fromVersion: Number(a.fromVersion ?? 1),
    toVersion: Number(a.toVersion ?? 1),
    summary: String(a.summary ?? ""),
    changes: (a.changes as string[]) ?? [],
    rationale: String(a.rationale ?? ""),
    grounding: (a.grounding as string[]) ?? [],
    consentRelevant: Boolean(a.consentRelevant),
    consentReasons: (a.consentReasons as string[]) ?? [],
    approvedBy: String(a.approvedBy ?? ""),
    reapprovalArtifact: (a.reapprovalArtifact as string | null) ?? null,
    at: String(a.at ?? ""),
  };
}

function mapState(studyId: string, raw: Record<string, unknown>): AmendmentState {
  return {
    studyId,
    currentVersion: Number(raw.currentVersion ?? 1),
    ethicsApprovedAt: String(raw.ethicsApprovedAt ?? ""),
    pendingReapproval: String(raw.pendingReapproval ?? ""),
    amendments: ((raw.amendments as Record<string, unknown>[]) ?? []).map(mapAmendment),
  };
}

export const evolutionApi = {
  async amendments(studyId: string): Promise<AmendmentState> {
    const raw = await req<Record<string, unknown>>(
      `/studies/${encodeURIComponent(studyId)}/amendments`,
    );
    return mapState(studyId, raw);
  },

  recordReapproval(studyId: string, artifact = "ethics-reapproval.pdf") {
    return post<{ reapproved: boolean }>(
      `/studies/${encodeURIComponent(studyId)}/reapproval`,
      { artifact },
    );
  },

  async platformFindings(): Promise<PlatformFinding[]> {
    const raw = await req<{ findings: Record<string, unknown>[] }>("/platform/findings");
    return (raw.findings ?? []).map((f) => ({
      id: Number(f.id),
      at: String(f.at ?? ""),
      note: String(f.note ?? f.message ?? ""),
      status: (f.status as PlatformFinding["status"]) ?? "open",
      locus: {
        studyId: String((f.locus as Record<string, unknown>)?.studyId ?? ""),
        turnId: String((f.locus as Record<string, unknown>)?.turnId ?? ""),
        seq: Number((f.locus as Record<string, unknown>)?.seq ?? 0),
        kind: String((f.locus as Record<string, unknown>)?.kind ?? "unclassified"),
      },
    }));
  },

  async retrospectiveProposal(): Promise<RetrospectiveProposal> {
    return req<RetrospectiveProposal>("/platform/retrospective/proposal");
  },
};

/** Live amendments when middleware is up; otherwise the offline demo store. */
export async function fetchAmendmentState(studyId: string): Promise<AmendmentState | null> {
  try {
    return await evolutionApi.amendments(studyId);
  } catch (e) {
    if (e instanceof OfflineError) {
      const snap = evolutionStore.getSnapshot();
      return snap.amendmentState.studyId === studyId ? snap.amendmentState : null;
    }
    throw e;
  }
}

export { deriveProposal };
