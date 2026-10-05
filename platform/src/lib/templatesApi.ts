import { getAuthToken, notifyUnauthorized } from "./api.ts";
import { OfflineError } from "./studyApi";

/* The template registry (FR-TPL): published, citable study designs that
 * instantiate into protocols. Not study-scoped, so its own tiny client. */

const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");

export interface TemplateSource {
  paperRef: string;
  role: string;
}

export interface TemplateSummary {
  id: string;
  version: number;
  title: string;
  description: string;
  designType: string;
  dataPath: string;
  source: TemplateSource[];
}

/* One paper attached to a design shape: either a paper the template cites as
 * its source, or a corpus paper that describes itself with the shape's design
 * vocabulary. Ranked by confidence, never by provenance. */
export interface DesignReference {
  ref: string;
  title: string;
  year: number | null;
  venue: string;
  confidence: number | null;
  role: string;
  matchReason: string;
}

/* A design shape in the repertoire, with how widely the corpus uses it. */
export interface RepertoireEntry extends TemplateSummary {
  support: number;
  signature: string[];
  band: "common" | "established" | "rare";
  admitted: boolean;
  admissionNote: string;
  references: DesignReference[];
  unresolvedSources: string[];
}

export interface CorpusStatus {
  state: "idle" | "empty" | "loading" | "partial" | "ready" | "error";
  papers: number;
  expected: number;
  error: string;
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(API_BASE + path, {
      ...init,
      headers: {
        ...(init.body ? { "content-type": "application/json" } : {}),
        ...((await getAuthToken()) ? { Authorization: `Bearer ${await getAuthToken()}` } : {}),
        ...(init.headers ?? {}),
      },
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
  return (await res.json()) as T;
}

export const templatesApi = {
  repertoire: (limitRefs = 4) =>
    req<{
      repertoire: RepertoireEntry[];
      count: number;
      minReferenceConfidence: number;
      corpus: CorpusStatus;
    }>(`/templates/repertoire?limitRefs=${limitRefs}`),
};
