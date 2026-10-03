import type { Role } from "./capabilities.ts";

/** Typed HTTP client for projects, membership, enrollment, and preferences. */

export interface Membership {
  projectSlug: string;
  projectName: string;
  role: Role;
}

export interface Me {
  sub: string;
  displayName: string;
  mode: "none" | "token" | "clerk";
  memberships: Membership[];
  /** Server-persisted display and conversation preferences. */
  preferences: Preferences;
}

/** Researcher experience changes conversational register, not validation rules. */
export type ResearcherProfile =
  | "student"
  | "new-researcher"
  | "experienced"
  | "industry";

/** Offline fallback only  -  mirrors `elicitation.PROFILES` on the server,
 * which is the source of truth (`researcherProfiles()` fetches the real
 * catalogue live). Kept here, not re-typed ad hoc at each call site, so
 * there's exactly one place this can drift from the server's copy. */
export const FALLBACK_RESEARCHER_PROFILES: {
  id: ResearcherProfile;
  label: string;
  description: string;
}[] = [
  { id: "student", label: "Student", description: "Learning research methods; this may be a first study." },
  { id: "new-researcher", label: "New researcher", description: "Research training, first empirical studies in this area." },
  { id: "experienced", label: "Experienced researcher", description: "Designs and runs empirical studies regularly." },
  { id: "industry", label: "Industry practitioner", description: "Studying developers inside a company (e.g. a platform team)." },
];

export interface Preferences {
  theme?: "light" | "dark" | "system";
  savedViews?: string[];
  researcherProfile?: ResearcherProfile;
}

export interface ProjectSummary {
  id: string;
  slug: string;
  name: string;
  role: Role;
  createdAt: string;
  /** How many studies the project holds. Carried on the list response so
   * the project list can say what a project *is* without a request per row. */
  studyCount: number;
}

export interface StudyRef {
  id: string;
}

export interface Member {
  identitySub: string;
  role: Role;
  invitedBy?: string;
  joinedAt?: string;
}

export interface Invitation {
  id: string;
  role: Role;
  token?: string;
  url?: string;
  createdAt?: string;
  expiresAt: string;
}

export interface ProjectHome {
  id: string;
  slug: string;
  name: string;
  studies: StudyRef[];
  members: Member[];
  invitations: Invitation[];
}

export interface EnrollmentTokenCaptureConfig {
  captureConfigVersion: string;
  enabledInstruments: { name: string; enabled: boolean }[];
  producerStates?: Record<string, string>;
  privacyPolicy?: Record<string, unknown>;
}

export interface ToggleCatalogEntry {
  instrument: string;
  leg?: string;
  path: string[];
  label: string;
  description: string;
  grounding: { ref?: string; source?: string; unsourced?: boolean };
  currentValue: unknown;
}

export interface ToggleResult {
  applied: boolean;
  error?: string;
}

export interface EnrollmentTokenView {
  id: string;
  participantId: string;
  condition: string;
  grain: "participant" | "session";
  status: "unredeemed" | "paired" | "streaming" | "revoked";
  /** Present only right after minting  -  the participant's one-paste link. */
  connectionString?: string;
  /** The capture config the IDE will run under (FR-DASH-10 pre-flight
   * visibility); null for an agent-participant study with no overlay. */
  captureConfig?: EnrollmentTokenCaptureConfig | null;
  /** Per-mint toggle overrides layered on the protocol-derived defaults. */
  captureOverrides?: CaptureOverrides | null;
}

/** A mint-time capture-config override: one instrument toggle addressed by path. */
export interface CaptureOverrides {
  toggles: ToggleCatalogOverride[];
}

export interface ToggleCatalogOverride {
  instrument: string;
  path: string[];
  value: unknown;
}

export interface Api {
  me(): Promise<Me>;
  listProjects(): Promise<ProjectSummary[]>;
  createProject(name: string): Promise<ProjectSummary>;
  projectHome(slug: string): Promise<ProjectHome>;
  createStudy(
    slug: string,
    name: string,
    protocol?: Record<string, unknown>,
  ): Promise<{ id: string }>;
  deleteStudy(studyId: string): Promise<void>;
  renameProject(slug: string, name: string): Promise<void>;
  deleteProject(slug: string, confirm: string): Promise<void>;
  members(slug: string): Promise<Member[]>;
  changeRole(slug: string, sub: string, role: Role): Promise<void>;
  removeMember(slug: string, sub: string): Promise<void>;
  createInvitation(slug: string, role: Role): Promise<Invitation>;
  revokeInvitation(slug: string, id: string): Promise<void>;
  acceptInvitation(token: string): Promise<{ projectSlug: string; role: Role }>;
  mintEnrollmentTokens(
    studyId: string,
    count: number,
    grain: "participant" | "session",
    overrides?: CaptureOverrides | null,
  ): Promise<EnrollmentTokenView[]>;
  listEnrollmentTokens(studyId: string): Promise<EnrollmentTokenView[]>;
  revokeEnrollmentToken(studyId: string, tokenId: string): Promise<void>;
  toggleCatalog(studyId: string): Promise<ToggleCatalogEntry[]>;
  applyToggle(studyId: string, body: { instrument: string; path: string[]; value: unknown; rationale: string }): Promise<ToggleResult>;
  /** Persist this identity's profile preferences (FR-OPS-7) and return the
   * server's merged copy. */
  updatePreferences(prefs: Partial<Preferences>): Promise<Preferences>;

  /** The researcher profiles the design conversation adapts to (FR-CONV-9),
   * from the server's own `elicitation.PROFILES`  -  the source of truth, so
   * this list can't drift from what `Settings` used to hardcode. */
  researcherProfiles(): Promise<{
    profiles: { id: string; label: string; description: string }[];
    default: string;
  }>;
}

/** Raised by both backends so callers can show the server's plain-language
 * message. */
export class ApiError extends Error {
  status: number;
  /** Whether `message` is a sentence somebody wrote for a person  -  the API's
   * own `detail` ("slug 'lab' is taken"), or one of this module's offline
   * messages. False means it was reconstructed from the HTTP status because
   * the response carried no `detail`: a proxy's error page, an edge
   * rate-limiter, a dev server's SPA 404. "Not Found" is a status, not an
   * error message, and a surface that prints it is showing the researcher
   * plumbing. Callers show `message` only when this is true. */
  fromServer: boolean;
  constructor(status: number, message: string, fromServer = true) {
    super(message);
    this.status = status;
    this.fromServer = fromServer;
  }
}

/** The server is unreachable or did not return an API response. */
export class OfflineError extends Error {
  constructor() {
    super("Could not reach the study server. Check your connection and try again.");
    this.name = "OfflineError";
  }
}

/** A bearer token to send with every request, refreshed on demand  -  Clerk
 * session JWTs are short-lived, so this is called per request rather than
 * cached. Set by the auth layer once a Clerk session exists; defaults to the
 * pasted-token fallback (`localStorage['middleware.token']`), matching
 * `studyApi.ts`'s auth header. */
let tokenProvider: () => Promise<string | null> = async () =>
  localStorage.getItem("middleware.token");

export function setTokenProvider(provider: () => Promise<string | null>): void {
  tokenProvider = provider;
}

/** Notified whenever the server answers 401  -  the auth layer subscribes to
 * show the sign-in surface without every page needing to catch it itself. */
const unauthorizedListeners = new Set<() => void>();

export function onUnauthorized(listener: () => void): () => void {
  unauthorizedListeners.add(listener);
  return () => unauthorizedListeners.delete(listener);
}

/** The live bearer token (Clerk session JWT, or the pasted-token fallback)
 *  -  exported so `studyApi.ts`/`conversationApi.ts` share
 * the exact same token source as this module instead of each re-reading
 * `localStorage` directly, which never sees a Clerk-issued token at all. */
export async function getAuthToken(): Promise<string | null> {
  return tokenProvider();
}

/** Fires the same "show the sign-in surface" signal `HttpBackend` fires on
 * its own 401s  -  shared so every API client's 401 converges on one global
 * gate instead of each page rendering the raw error text itself. */
export function notifyUnauthorized(): void {
  unauthorizedListeners.forEach((l) => l());
}

// --------------------------------------------------------------- HTTP backend

class HttpBackend implements Api {
  private base: string;
  constructor(base: string) {
    this.base = base;
  }

  private async call<T>(method: string, path: string, body?: unknown): Promise<T> {
    const token = await tokenProvider();
    let res: Response;
    try {
      res = await fetch(this.base + path, {
        method,
        headers: {
          ...(body ? { "content-type": "application/json" } : {}),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: body ? JSON.stringify(body) : undefined,
        credentials: "include",
      });
    } catch {
      throw new OfflineError();
    }
    if (!res.ok) {
      const contentType = (res.headers.get("content-type") ?? "").toLowerCase();
      // Vite's SPA fallback answers an API-shaped request with an HTML 404 when
      // the middleware is not running. That is an offline shell condition, not a
      // real server-side "study not found" response. FastAPI's genuine 404s are
      // JSON, so they still surface as ApiError below and are never masked.
      if (res.status === 404 && !contentType.includes("application/json")) {
        throw new OfflineError();
      }
      // `res.statusText` is blank over HTTP/2 (no reason phrase on the
      // wire), so a non-JSON error body  -  an edge/proxy rate-limit page,
      // not our own JSON errors  -  used to leave `detail` as "", which
      // `{err && ...}` then renders as nothing: a real failure with no
      // visible feedback at all.
      let detail = res.statusText || `Request failed (${res.status})`;
      let fromServer = false;
      try {
        const body = await res.json();
        if (typeof body?.detail === "string" && body.detail.trim()) {
          detail = body.detail;
          fromServer = true;
        }
      } catch {
        /* non-JSON error body */
      }
      if (res.status === 401) unauthorizedListeners.forEach((l) => l());
      throw new ApiError(res.status, detail, fromServer);
    }
    if (res.status === 204) return undefined as T;
    try {
      return (await res.json()) as T;
    } catch {
      // A 200 that isn't real JSON (e.g. a dev server's SPA-fallback
      // index.html, or a misconfigured proxy) means there's no real API
      // behind this origin  -  the same offline posture as an unreachable
      // server, so it degrades the same way instead of throwing a raw
      // parse error at the UI.
      throw new OfflineError();
    }
  }

  me = () => this.call<Me>("GET", "/me");
  listProjects = () => this.call<ProjectSummary[]>("GET", "/projects");
  createProject = (name: string) =>
    this.call<ProjectSummary>("POST", "/projects", { name });
  projectHome = (slug: string) => this.call<ProjectHome>("GET", `/projects/${slug}`);
  createStudy = (slug: string, name: string, protocol?: Record<string, unknown>) =>
    this.call<{ id: string }>("POST", `/projects/${slug}/studies`, {
      name,
      ...(protocol ? { protocol } : {}),
    });
  deleteStudy = (studyId: string) =>
    this.call<void>("DELETE", `/studies/${studyId}`);
  renameProject = (slug: string, name: string) =>
    this.call<void>("PATCH", `/projects/${slug}`, { name });
  deleteProject = (slug: string, confirm: string) =>
    this.call<void>("DELETE", `/projects/${slug}`, { confirm });
  members = (slug: string) => this.call<Member[]>("GET", `/projects/${slug}/members`);
  changeRole = (slug: string, sub: string, role: Role) =>
    this.call<void>("PATCH", `/projects/${slug}/members/${sub}`, { role });
  removeMember = (slug: string, sub: string) =>
    this.call<void>("DELETE", `/projects/${slug}/members/${sub}`);
  createInvitation = (slug: string, role: Role) =>
    this.call<Invitation>("POST", `/projects/${slug}/invitations`, { role });
  revokeInvitation = (slug: string, id: string) =>
    this.call<void>("DELETE", `/projects/${slug}/invitations/${id}`);
  acceptInvitation = (token: string) =>
    this.call<{ projectSlug: string; role: Role }>(
      "POST",
      `/invitations/${token}/accept`);
  mintEnrollmentTokens = (
    studyId: string,
    count: number,
    grain: "participant" | "session",
    overrides?: CaptureOverrides | null,
  ) =>
    this.call<EnrollmentTokenView[]>("POST", `/studies/${studyId}/enrollment/tokens`, {
      count,
      grain,
      ...(overrides ? { overrides } : {}),
    });
  listEnrollmentTokens = (studyId: string) =>
    this.call<EnrollmentTokenView[]>("GET", `/studies/${studyId}/enrollment/tokens`);
  revokeEnrollmentToken = (studyId: string, tokenId: string) =>
    this.call<void>("DELETE", `/studies/${studyId}/enrollment/tokens/${tokenId}`);
  toggleCatalog = (studyId: string) =>
    this.call<ToggleCatalogEntry[]>("GET", `/studies/${studyId}/enrollment/toggles/catalog`);
  applyToggle = (studyId: string, body: { instrument: string; path: string[]; value: unknown; rationale: string }) =>
    this.call<ToggleResult>("POST", `/studies/${studyId}/enrollment/toggles`, body);
  updatePreferences = (prefs: Partial<Preferences>) =>
    this.call<{ sub: string; preferences: Preferences }>(
      "PUT",
      "/me/preferences",
      { preferences: prefs },
    ).then((r) => r.preferences);
  researcherProfiles = () =>
    this.call<{
      profiles: { id: string; label: string; description: string }[];
      default: string;
    }>("GET", "/conversation/profiles");
}

/** Same-origin by default; override only for a separate API deployment. */
export function apiBase(): string {
  return (
    (typeof import.meta !== "undefined" ? import.meta.env?.VITE_API_BASE : undefined) ?? ""
  );
}

export function createApi(): Api {
  return new HttpBackend(apiBase());
}
