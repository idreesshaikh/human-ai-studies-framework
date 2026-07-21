import type { Role } from "./capabilities.ts";

/* The shell's data layer. One typed interface, two implementations:
 *
 *  - HttpBackend talks to the middleware (used when VITE_API_BASE is set);
 *  - InMemoryBackend is a self-contained fake that seeds a couple of
 *    projects and the demo, so the whole shell is explorable — and
 *    testable — with no server running. It also powers the hero's offline
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
 * stores keys it recognises (`theme`, `defaultAssistantModel`, `savedViews`);
 * the UI owns their semantics. */
export interface Preferences {
  theme?: "light" | "dark" | "system";
  defaultAssistantModel?: string;
  savedViews?: string[];
}

export interface ProjectSummary {
  id: string;
  slug: string;
  name: string;
  role: Role;
  createdAt: string;
}

export interface StudyRef {
  id: string;
  phase: string;
}

export interface Member {
  identitySub: string;
  role: Role;
  invitedBy?: string;
  joinedAt?: string;
}

export interface Invitation {
  id: string;
  email: string;
  role: Role;
  token?: string;
  url?: string;
  expiresAt: string;
  acceptedAt?: string | null;
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
  path: string[];
  label: string;
  description: string;
  grounding: { ref?: string; source?: string; unsourced?: boolean };
  currentValue: unknown;
}

export interface ToggleResult {
  applied: boolean;
  requiresReapproval?: boolean;
  amendmentId?: string;
  error?: string;
}

export interface EnrollmentTokenView {
  id: string;
  participantId: string;
  condition: string;
  grain: "participant" | "session";
  status: "unredeemed" | "paired" | "streaming" | "revoked";
  /** Present only right after minting — the participant's one-paste link. */
  connectionString?: string;
  /** The capture config the IDE will run under (FR-DASH-10 pre-flight
   * visibility); null for an agent-participant study with no overlay. */
  captureConfig?: EnrollmentTokenCaptureConfig | null;
}

export interface Api {
  me(): Promise<Me>;
  listProjects(): Promise<ProjectSummary[]>;
  createProject(name: string): Promise<ProjectSummary>;
  projectHome(slug: string): Promise<ProjectHome>;
  renameProject(slug: string, name: string): Promise<void>;
  deleteProject(slug: string, confirm: string): Promise<void>;
  members(slug: string): Promise<Member[]>;
  changeRole(slug: string, sub: string, role: Role): Promise<void>;
  removeMember(slug: string, sub: string): Promise<void>;
  createInvitation(slug: string, email: string, role: Role): Promise<Invitation>;
  revokeInvitation(slug: string, id: string): Promise<void>;
  acceptInvitation(token: string): Promise<{ projectSlug: string; role: Role }>;
  mintEnrollmentTokens(studyId: string, count: number, grain: "participant" | "session"): Promise<EnrollmentTokenView[]>;
  listEnrollmentTokens(studyId: string): Promise<EnrollmentTokenView[]>;
  revokeEnrollmentToken(studyId: string, tokenId: string): Promise<void>;
  toggleCatalog(studyId: string): Promise<ToggleCatalogEntry[]>;
  applyToggle(studyId: string, body: { instrument: string; path: string[]; value: unknown; rationale: string }): Promise<ToggleResult>;
  /** Persist this identity's profile preferences (FR-OPS-7) and return the
   * server's merged copy. */
  updatePreferences(prefs: Partial<Preferences>): Promise<Preferences>;
  /** The catalog of assistant model tiers the platform may pick
   * (FR-OPS-7 profile default). Unauthenticated catalog, never the key. */
  assistantModels(): Promise<{
    configured: boolean;
    models: string[];
    defaultModel: string;
  }>;
}

/** Raised by both backends so callers can show the server's plain-language
 * message. */
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** The middleware is unreachable (no server, network down) — distinct from
 * `ApiError`, which means the server answered but refused. `createApi()`
 * catches this to fall back to the offline fake; callers that want to tell
 * "no server" apart from "signed out" can catch it directly. */
export class OfflineError extends Error {
  constructor() {
    super("This needs the running middleware (port 8000).");
    this.name = "OfflineError";
  }
}

/** A bearer token to send with every request, refreshed on demand — Clerk
 * session JWTs are short-lived, so this is called per request rather than
 * cached. Set by the auth layer once a Clerk session exists; defaults to the
 * pasted-token fallback (`localStorage['middleware.token']`), matching
 * `studyApi.ts`'s auth header. */
let tokenProvider: () => Promise<string | null> = async () =>
  localStorage.getItem("middleware.token");

export function setTokenProvider(provider: () => Promise<string | null>): void {
  tokenProvider = provider;
}

/** Notified whenever the server answers 401 — the auth layer subscribes to
 * show the sign-in surface without every page needing to catch it itself. */
const unauthorizedListeners = new Set<() => void>();

export function onUnauthorized(listener: () => void): () => void {
  unauthorizedListeners.add(listener);
  return () => unauthorizedListeners.delete(listener);
}

/** The live bearer token (Clerk session JWT, or the pasted-token fallback)
 * — exported so `studyApi.ts`/`conversationApi.ts`/`evolutionApi.ts` share
 * the exact same token source as this module instead of each re-reading
 * `localStorage` directly, which never sees a Clerk-issued token at all. */
export async function getAuthToken(): Promise<string | null> {
  return tokenProvider();
}

/** Fires the same "show the sign-in surface" signal `HttpBackend` fires on
 * its own 401s — shared so every API client's 401 converges on one global
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
      let detail = res.statusText;
      try {
        detail = (await res.json()).detail ?? detail;
      } catch {
        /* non-JSON error body */
      }
      if (res.status === 401) unauthorizedListeners.forEach((l) => l());
      throw new ApiError(res.status, detail);
    }
    if (res.status === 204) return undefined as T;
    try {
      return (await res.json()) as T;
    } catch {
      // A 200 that isn't real JSON (e.g. a dev server's SPA-fallback
      // index.html, or a misconfigured proxy) means there's no real API
      // behind this origin — the same offline posture as an unreachable
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
  renameProject = (slug: string, name: string) =>
    this.call<void>("PATCH", `/projects/${slug}`, { name });
  deleteProject = (slug: string, confirm: string) =>
    this.call<void>("DELETE", `/projects/${slug}`, { confirm });
  members = (slug: string) => this.call<Member[]>("GET", `/projects/${slug}/members`);
  changeRole = (slug: string, sub: string, role: Role) =>
    this.call<void>("PATCH", `/projects/${slug}/members/${sub}`, { role });
  removeMember = (slug: string, sub: string) =>
    this.call<void>("DELETE", `/projects/${slug}/members/${sub}`);
  createInvitation = (slug: string, email: string, role: Role) =>
    this.call<Invitation>("POST", `/projects/${slug}/invitations`, { email, role });
  revokeInvitation = (slug: string, id: string) =>
    this.call<void>("DELETE", `/projects/${slug}/invitations/${id}`);
  acceptInvitation = (token: string) =>
    this.call<{ projectSlug: string; role: Role }>(
      "POST",
      `/invitations/${token}/accept`);
  mintEnrollmentTokens = (studyId: string, count: number, grain: "participant" | "session") =>
    this.call<EnrollmentTokenView[]>("POST", `/studies/${studyId}/enrollment/tokens`, { count, grain });
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
  assistantModels = () =>
    this.call<{ configured: boolean; models: string[]; defaultModel: string }>(
      "GET",
      "/assistant/models",
    );
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
        { id: "over-trust-2026", phase: "design" },
        // A demo study mid-evolution: its amendment banner + history
        // are seeded in evolutionStub.ts.
        { id: "sample-study-2026", phase: "data-collection" },
      ],
      members: [
        { identitySub: "you", role: "owner", joinedAt: "2026-07-10T09:00:00.000Z" },
        { identitySub: "dana@lab.test", role: "researcher", joinedAt: "2026-07-11T09:00:00.000Z" },
        { identitySub: "sam@lab.test", role: "viewer", joinedAt: "2026-07-12T09:00:00.000Z" },
      ],
      invitations: [],
    });
    // The shared, read-only demo project.
    this.projects.set("demo", {
      id: "p-demo",
      slug: "demo",
      name: "Demo — AI code trust study",
      createdAt: "2026-07-01T09:00:00.000Z",
      studies: [{ id: "demo-study", phase: "reporting" }],
      members: [{ identitySub: "you", role: "viewer" }],
      invitations: [],
    });

    // Seed protocol shapes so toggleCatalog/applyToggle work offline.
    const demoInstruments: Record<string, unknown> = {
      cognitiveOverlay: {
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
      if (role) out.push({ id: p.id, slug: p.slug, name: p.name, role, createdAt: p.createdAt });
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
    return { id: p.id, slug, name: p.name, role: "owner", createdAt: now };
  }

  async projectHome(slug: string): Promise<ProjectHome> {
    const p = this.get(slug);
    return {
      id: p.id,
      slug: p.slug,
      name: p.name,
      studies: p.studies,
      members: p.members,
      invitations: p.invitations.filter((i) => !i.acceptedAt),
    };
  }

  async renameProject(slug: string, name: string): Promise<void> {
    if (!name.trim()) throw new ApiError(400, "name is required");
    this.get(slug).name = name.trim();
  }

  async deleteProject(slug: string, confirm: string): Promise<void> {
    const p = this.get(slug);
    if (confirm !== p.slug) throw new ApiError(400, `type the project slug (${p.slug}) to confirm`);
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
      throw new ApiError(409, "can't remove the last owner — transfer ownership first");
    }
    p.members = p.members.filter((x) => x.identitySub !== sub);
  }

  async createInvitation(slug: string, email: string, role: Role): Promise<Invitation> {
    const p = this.get(slug);
    if (!email.trim()) throw new ApiError(400, "email is required");
    const token = this.id("tok");
    const inv: Invitation = {
      id: this.id("inv"),
      email: email.trim(),
      role,
      token,
      url: `/invitations/${token}`,
      expiresAt: new Date(Date.now() + 7 * 864e5).toISOString(),
      acceptedAt: null,
    };
    p.invitations.push(inv);
    return inv;
  }

  async revokeInvitation(slug: string, id: string): Promise<void> {
    const p = this.get(slug);
    const before = p.invitations.length;
    p.invitations = p.invitations.filter((i) => i.id !== id || i.acceptedAt);
    if (p.invitations.length === before) throw new ApiError(404, "invitation not found");
  }

  async acceptInvitation(token: string): Promise<{ projectSlug: string; role: Role }> {
    for (const p of this.projects.values()) {
      const inv = p.invitations.find((i) => i.token === token && !i.acceptedAt);
      if (inv) {
        inv.acceptedAt = new Date().toISOString();
        const existing = p.members.find((m) => m.identitySub === this.sub);
        if (existing) existing.role = inv.role;
        else p.members.push({ identitySub: this.sub, role: inv.role, invitedBy: inv.id });
        return { projectSlug: p.slug, role: inv.role };
      }
    }
    throw new ApiError(404, "invitation not found — it may have expired or already been used");
  }

  async mintEnrollmentTokens(studyId: string, count: number, grain: "participant" | "session"): Promise<EnrollmentTokenView[]> {
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
    addEntry("cognitiveOverlay", ["stuck", "enabled"], "Stuck detection", "Detects dwell/scroll-thrash", { ref: "FR-INST-2", source: "srs" });
    addEntry("cognitiveOverlay", ["ideHealth", "enabled"], "IDE health stream", "Captures diagnostic counts", { ref: "FR-INST-18", source: "srs" });
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
    const relevant = body.path.includes("enabled") || body.path[body.path.length - 1] === "enabled";
    return { applied: true, requiresReapproval: relevant, amendmentId: relevant ? "amend-demo" : undefined };
  }

  async updatePreferences(prefs: Partial<Preferences>): Promise<Preferences> {
    this.prefs = { ...this.prefs, ...prefs };
    return { ...this.prefs };
  }

  async assistantModels(): Promise<{
    configured: boolean;
    models: string[];
    defaultModel: string;
  }> {
    return {
      configured: true,
      models: ["mistral-small-latest", "mistral-medium-latest", "mistral-large-latest"],
      defaultModel: "mistral-small-latest",
    };
  }
}

/** Every call tries the real backend first and falls back to the in-memory
 * fake only on `OfflineError` (no server reachable) — never on a real
 * `ApiError`, so a genuine 401/403/404 still surfaces. Preserves offline
 * explorability (`npm run dev` with nothing on :8000, static previews) while
 * a deployed instance — same origin, per NFR-7 — always talks to the real
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

/** Same-origin by default — in production the middleware serves this SPA
 * at `/` (NFR-7), so a relative base reaches the real API with no build-time
 * config. Set VITE_API_BASE only for a separate-origin deployment (needs
 * MIDDLEWARE_CORS_ORIGINS, FR-OPS-6, D30). */
export function createApi(): Api {
  const base =
    (typeof import.meta !== "undefined" ? import.meta.env?.VITE_API_BASE : undefined) ?? "";
  return withOfflineFallback(new HttpBackend(base), new InMemoryBackend());
}
