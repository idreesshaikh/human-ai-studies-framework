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

export interface MergeResult {
  protocol: Record<string, unknown>;
  templateIds: string[];
  sources: { templateId: string; papers: string[] }[];
}

export interface CorpusHit {
  ref: string;
  title: string;
  year: number | null;
  venue: string;
  confidence: number | null;
  inStudy?: boolean;
  matchReason: string;
}

export interface DerivedTemplate {
  template: {
    templateId: string;
    title: string;
    description: string;
    designType: string;
    source: TemplateSource[];
  };
  paper: { ref: string; title: string; confidence: number | null };
  /** The derived template already filled with its defaults  -  what a new
   *  study's draft is seeded from. The template itself is never registered,
   *  so there is no id anything else could instantiate it by. */
  protocol: Record<string, unknown>;
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
  list: () =>
    req<{ templates: TemplateSummary[]; count: number }>(`/templates`).then(
      (d) => d.templates,
    ),
  repertoire: (limitRefs = 4) =>
    req<{
      repertoire: RepertoireEntry[];
      count: number;
      minReferenceConfidence: number;
      corpus: CorpusStatus;
    }>(`/templates/repertoire?limitRefs=${limitRefs}`),
  plan: (id: string) =>
    req<{ templateId: string; explanation: string[] }>(
      `/templates/${encodeURIComponent(id)}/plan`,
    ),
  merge: (templateIds: string[]) =>
    req<MergeResult>(`/templates/merge`, {
      method: "POST",
      body: JSON.stringify({ templateIds }),
    }),
  searchCorpus: (q: string) =>
    req<{ results: CorpusHit[] }>(
      `/corpus/search?q=${encodeURIComponent(q)}&limit=8`,
    ).then((d) => d.results),
  fromPaper: (paperRef: string, baseTemplateId: string) =>
    req<DerivedTemplate>(`/templates/from-paper`, {
      method: "POST",
      body: JSON.stringify({ paperRef, baseTemplateId }),
    }),
};
