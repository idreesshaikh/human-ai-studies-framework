import type { Role } from "./capabilities.ts";

/* The shell's data layer. One typed interface, two implementations:
 *
 *  - HttpBackend talks to the middleware (used when VITE_API_BASE is set);
 *  - InMemoryBackend is a self-contained fake that seeds a couple of
 *    projects and the demo, so the whole shell is explorable  -  and
 *    testable  -  with no server running. It also powers the hero's offline
 *    demo, mirroring how the conversation runs on a deterministic stub.
 *
 * Both enforce nothing: authorization is the server's job. The fake mimics
 * the server's *shape* (roles, single-use invitations, last-owner refusal)
 * so the UI behaves the same offline and online. */

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
  /** Per-user persisted preferences (FR-OPS-7): theme, default assistant
   * model, saved views. Empty until the identity saves one. */
  preferences: Preferences;
}

/** The shape the server persists per identity (FR-OPS-7). The server only
 * stores keys it recognises (`theme`, `savedViews`);
 * the UI owns their semantics. */
/** Who the design conversation is talking to (FR-CONV-9). Changes register,
 *  pacing, and which trade-offs get surfaced  -  never what counts as sound
 *  method. Unset means the platform uses its default posture. */
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
  /** The catalog of assistant model tiers the platform may pick
   * (FR-OPS-7 profile default). Unauthenticated catalog, never the key. */
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

/** The middleware is unreachable (no server, network down)  -  distinct from
 * `ApiError`, which means the server answered but refused. `createApi()`
 * catches this to fall back to the offline fake; callers that want to tell
 * "no server" apart from "signed out" can catch it directly. */
export class OfflineError extends Error {
  constructor() {
    super("This needs the running middleware (port 8000).");
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

// ---------------------------------------------------------- in-memory backend

interface FakeProject {
  id: string;
  slug: string;
  name: string;
  createdAt: string;
  studies: StudyRef[];
  members: Member[];
  invitations: Invitation[];
}

function slugify(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "").slice(0, 50);
}

export class InMemoryBackend implements Api {
  private projects = new Map<string, FakeProject>();
  private enrollments = new Map<string, EnrollmentTokenView[]>();
  private protocols = new Map<string, Record<string, unknown>>();
  private sub = "you";
  private seq = 0;
  private prefs: Preferences = {};

  constructor() {
    this.seed();
  }

  private id(prefix: string): string {
    this.seq += 1;
    return `${prefix}-${this.seq}`;
  }

  private seed() {
    // A project the signed-in person owns, so the shell isn't empty offline.
    this.projects.set("sample-lab", {
      id: "p-sample",
      slug: "sample-lab",
      name: "Sample Lab",
      createdAt: "2026-07-10T09:00:00.000Z",
      studies: [
        { id: "over-trust-2026" },
        { id: "sample-study-2026" },
      ],
      members: [
        { identitySub: "you", role: "owner", joinedAt: "2026-07-10T09:00:00.000Z" },
        { identitySub: "dana@lab.test", role: "member", joinedAt: "2026-07-11T09:00:00.000Z" },
      ],
      invitations: [],
    });
    // The shared, read-only demo project.
    this.projects.set("demo", {
      id: "p-demo",
      slug: "demo",
      name: "Demo: AI code trust study",
      createdAt: "2026-07-01T09:00:00.000Z",
      studies: [{ id: "demo-study" }],
      members: [{ identitySub: "you", role: "viewer" }],
      invitations: [],
    });

    // Seed protocol shapes so toggleCatalog/applyToggle work offline. Keyed
    // "tern" to match the real protocol schema's instrument name  -  this used
    // to say "cognitiveOverlay" (the pre-rename name), which the live
    // enrollment panel's toggle-chip lookup (filtered on "tern") could never
    // match: the offline demo's toggle popover silently never opened.
    const demoInstruments: Record<string, unknown> = {
      tern: {
        stuck: { enabled: true, thresholdSeconds: 90, cooldownMinutes: 5, languages: ["python"] },
        fatigue: { intervalMinutes: 15, waitForPauseSeconds: 4, jitterPercent: 20, quietTailMinutes: 5 },
        session: { durationMinutes: 45 },
        ideHealth: { enabled: false, debounceSeconds: 5 },
      },
    };
    for (const sid of ["sample-study-2026", "demo-study"]) {
      this.protocols.set(sid, { instruments: structuredClone(demoInstruments) });
    }
  }

  private roleOn(slug: string): Role | null {
    const p = this.projects.get(slug);
    return p?.members.find((m) => m.identitySub === this.sub)?.role ?? null;
  }

  private get(slug: string): FakeProject {
    const p = this.projects.get(slug);
    if (!p) throw new ApiError(404, "project not found");
    return p;
  }

  async me(): Promise<Me> {
    const memberships: Membership[] = [];
    for (const p of this.projects.values()) {
      const m = p.members.find((x) => x.identitySub === this.sub);
      if (m) memberships.push({ projectSlug: p.slug, projectName: p.name, role: m.role });
    }
    return { sub: this.sub, displayName: "You", mode: "none", memberships, preferences: { ...this.prefs } };
  }

  async listProjects(): Promise<ProjectSummary[]> {
    const out: ProjectSummary[] = [];
    for (const p of this.projects.values()) {
      const role = this.roleOn(p.slug);
      if (!role) continue;
      out.push({
        id: p.id,
        slug: p.slug,
        name: p.name,
        role,
        createdAt: p.createdAt,
        studyCount: p.studies.length,
      });
    }
    return out.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  }

  async createProject(name: string): Promise<ProjectSummary> {
    if (!name.trim()) throw new ApiError(400, "name is required");
    const slug = slugify(name) || this.id("project");
    if (this.projects.has(slug)) throw new ApiError(409, `slug ${slug} is taken`);
    const now = new Date().toISOString();
    const p: FakeProject = {
      id: this.id("p"),
      slug,
      name: name.trim(),
      createdAt: now,
      studies: [],
      members: [{ identitySub: this.sub, role: "owner", joinedAt: now }],
      invitations: [],
    };
    this.projects.set(slug, p);
    return {
      id: p.id,
      slug,
      name: p.name,
      role: "owner",
      createdAt: now,
      studyCount: 0,
    };
  }

  async projectHome(slug: string): Promise<ProjectHome> {
    const p = this.get(slug);
    return {
      id: p.id,
      slug: p.slug,
      name: p.name,
      studies: p.studies,
      members: p.members,
      invitations: p.invitations,
    };
  }

  async createStudy(
    slug: string,
    name: string,
    protocol?: Record<string, unknown>,
  ): Promise<{ id: string }> {
    const p = this.get(slug);
    const base = name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "study";
    let id = base;
    let suffix = 1;
    while (p.studies.some((st) => st.id === id)) {
      suffix += 1;
      id = `${base}-${suffix}`;
    }
    p.studies.push({ id });
    // Mirrors the real backend: an optional seed protocol (e.g. "start from
    // this template") lands as the study's draft immediately, offline the
    // same as live  -  a demo session starting a study from a template must
    // see the same design the live path would give it, not a blank one.
    if (protocol) this.protocols.set(id, protocol);
    return { id };
  }

  async deleteStudy(studyId: string): Promise<void> {
    for (const p of this.projects.values()) {
      const i = p.studies.findIndex((st) => st.id === studyId);
      if (i !== -1) {
        p.studies.splice(i, 1);
        return;
      }
    }
  }

  async renameProject(slug: string, name: string): Promise<void> {
    if (!name.trim()) throw new ApiError(400, "name is required");
    this.get(slug).name = name.trim();
  }

  async deleteProject(slug: string, confirm: string): Promise<void> {
    this.get(slug);
    if (confirm !== "DELETE") throw new ApiError(400, "type DELETE to confirm");
    this.projects.delete(slug);
  }

  async members(slug: string): Promise<Member[]> {
    return this.get(slug).members;
  }

  async changeRole(slug: string, sub: string, role: Role): Promise<void> {
    const m = this.get(slug).members.find((x) => x.identitySub === sub);
    if (!m) throw new ApiError(404, "member not found");
    m.role = role;
  }

  async removeMember(slug: string, sub: string): Promise<void> {
    const p = this.get(slug);
    const m = p.members.find((x) => x.identitySub === sub);
    if (!m) throw new ApiError(404, "member not found");
    if (m.role === "owner" && p.members.filter((x) => x.role === "owner").length <= 1) {
      throw new ApiError(409, "can't remove the last owner: transfer ownership first");
    }
    p.members = p.members.filter((x) => x.identitySub !== sub);
  }

  async createInvitation(slug: string, role: Role): Promise<Invitation> {
    const p = this.get(slug);
    const token = this.id("tok");
    const now = new Date().toISOString();
    const inv: Invitation = {
      id: this.id("inv"),
      role,
      token,
      url: `/invitations/${token}`,
      createdAt: now,
      expiresAt: new Date(Date.now() + 7 * 864e5).toISOString(),
    };
    p.invitations.push(inv);
    return inv;
  }

  async revokeInvitation(slug: string, id: string): Promise<void> {
    const p = this.get(slug);
    const before = p.invitations.length;
    p.invitations = p.invitations.filter((i) => i.id !== id);
    if (p.invitations.length === before) throw new ApiError(404, "invitation not found");
  }

  async acceptInvitation(token: string): Promise<{ projectSlug: string; role: Role }> {
    for (const p of this.projects.values()) {
      const inv = p.invitations.find((i) => i.token === token);
      if (inv) {
        const existing = p.members.find((m) => m.identitySub === this.sub);
        if (!existing) {
          p.members.push({ identitySub: this.sub, role: inv.role, invitedBy: inv.id });
          return { projectSlug: p.slug, role: inv.role };
        }
        return { projectSlug: p.slug, role: existing.role };
      }
    }
    throw new ApiError(404, "invitation not found: it may have expired or been revoked");
  }

  async mintEnrollmentTokens(
    studyId: string,
    count: number,
    grain: "participant" | "session",
    overrides?: CaptureOverrides | null,
  ): Promise<EnrollmentTokenView[]> {
    const rows = this.enrollments.get(studyId) ?? [];
    const conditions: string[] = ["ai-assisted", "unassisted"];
    const start = rows.length;
    const minted: EnrollmentTokenView[] = [];
    for (let i = 0; i < count; i++) {
      const n = start + i + 1;
      const row: EnrollmentTokenView = {
        id: this.id("tok"),
        participantId: `P${String(n).padStart(2, "0")}`,
        condition: conditions[(n - 1) % conditions.length],
        grain,
        status: "unredeemed",
        connectionString: `https://demo.local#${this.id("pair")}`,
        captureConfig: {
          captureConfigVersion: "demo000001",
          enabledInstruments: [{ name: "stuck", enabled: true }],
        },
        captureOverrides: overrides ?? null,
      };
      rows.push(row);
      minted.push(row);
    }
    this.enrollments.set(studyId, rows);
    return minted;
  }

  async listEnrollmentTokens(studyId: string): Promise<EnrollmentTokenView[]> {
    return (this.enrollments.get(studyId) ?? []).filter((t,) => t.status !== "revoked");
  }

  async revokeEnrollmentToken(studyId: string, tokenId: string): Promise<void> {
    const rows = this.enrollments.get(studyId) ?? [];
    const row = rows.find((t,) => t.id === tokenId);
    if (!row) throw new ApiError(404, "enrollment token not found");
    row.status = "revoked";
  }

  async toggleCatalog(studyId: string): Promise<ToggleCatalogEntry[]> {
    const protocol = this.protocols.get(studyId) as Record<string, unknown> | undefined;
    if (!protocol) return [];
    const instruments = (protocol.instruments ?? {}) as Record<string, unknown>;
    const entries: ToggleCatalogEntry[] = [];
    const addEntry = (instrument: string, path: string[], label: string, desc: string, grounding: ToggleCatalogEntry["grounding"]) => {
      let value: unknown = instruments[instrument];
      if (typeof value === "object" && value !== null) {
        for (const key of path) {
          if (typeof value === "object" && value !== null) value = (value as Record<string, unknown>)[key];
          else { value = undefined; break; }
        }
      }
      entries.push({ instrument, path, label, description: desc, grounding, currentValue: value });
    };
    addEntry("tern", ["stuck", "enabled"], "Stuck detection", "Detects dwell/scroll-thrash", { ref: "TERN stuck detector", source: "Instrumentation catalogue" });
    addEntry("tern", ["ideHealth", "enabled"], "IDE health stream", "Captures diagnostic counts", { ref: "TERN IDE health stream", source: "Instrumentation catalogue" });
    return entries;
  }

  async applyToggle(studyId: string, body: { instrument: string; path: string[]; value: unknown; rationale: string }): Promise<ToggleResult> {
    const protocol = this.protocols.get(studyId) as Record<string, unknown> | undefined;
    if (!protocol) throw new ApiError(404, "study not found");
    const instruments = (protocol.instruments ?? {}) as Record<string, unknown>;
    let node: Record<string, unknown> | undefined = instruments[body.instrument] as Record<string, unknown> | undefined;
    if (!node) throw new ApiError(400, "instrument not found");
    for (let i = 0; i < body.path.length - 1; i++) {
      const n = node[body.path[i]];
      if (typeof n !== "object" || n === null) throw new ApiError(400, "invalid path");
      node = n as Record<string, unknown>;
    }
    const lastKey = body.path[body.path.length - 1];
    node[lastKey] = body.value;
    return { applied: true };
  }

  async updatePreferences(prefs: Partial<Preferences>): Promise<Preferences> {
    this.prefs = { ...this.prefs, ...prefs };
    return { ...this.prefs };
  }


  async researcherProfiles(): Promise<{
    profiles: { id: string; label: string; description: string }[];
    default: string;
  }> {
    return { profiles: FALLBACK_RESEARCHER_PROFILES, default: "new-researcher" };
  }

}

/** Every call tries the real backend first and falls back to the in-memory
 * fake only on `OfflineError` (no server reachable)  -  never on a real
 * `ApiError`, so a genuine 401/403/404 still surfaces. Preserves offline
 * explorability (`npm run dev` with nothing on :8000, static previews) while
 * a deployed instance  -  same origin, per NFR-7  -  always talks to the real
 * server. Mirrors `studyApi.ts`'s per-call live-or-seed posture. */
function withOfflineFallback(live: Api, offline: Api): Api {
  const handler: ProxyHandler<Api> = {
    get(target, prop, receiver) {
      const value = Reflect.get(target, prop, receiver);
      if (typeof value !== "function") return value;
      return async (...args: unknown[]) => {
        try {
          return await (value as (...a: unknown[]) => unknown).apply(target, args);
        } catch (e) {
          if (e instanceof OfflineError) {
            const fallback = offline[prop as keyof Api] as (...a: unknown[]) => unknown;
            return fallback.apply(offline, args);
          }
          throw e;
        }
      };
    },
  };
  return new Proxy(live, handler);
}

/** Where the middleware answers. Same-origin by default  -  in production it
 * serves this SPA at `/` (NFR-7), so an empty base reaches the real API with
 * no build-time config. Set VITE_API_BASE only for a separate-origin
 * deployment (needs MIDDLEWARE_CORS_ORIGINS, FR-OPS-6, D30).
 *
 * Exported because `createApi` is not the only caller that has to reach the
 * middleware: the auth provider asks it which sign-in mode to present before
 * any `Api` exists, and it was asking with a bare relative path. On a
 * separate-origin deployment that path resolves against the SPA's own host,
 * which answers every unknown route with `index.html` and a 200  -  so the
 * config read parsed HTML as JSON, threw, hit the "no server reachable"
 * catch, and left the app in `mode: "none"`. The shell then renders as
 * though no sign-in exists, every call 401s, and the researcher is shown
 * "missing or invalid bearer token" on a page with no way to sign in. */
export function apiBase(): string {
  return (
    (typeof import.meta !== "undefined" ? import.meta.env?.VITE_API_BASE : undefined) ?? ""
  );
}

export function createApi(): Api {
  return withOfflineFallback(new HttpBackend(apiBase()), new InMemoryBackend());
}
