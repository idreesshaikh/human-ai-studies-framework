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

export interface DemoPointer {
  projectSlug: string;
  projectName: string;
  studyId: string;
}

export interface EnrollmentTokenView {
  id: string;
  participantId: string;
  condition: string;
  grain: "participant" | "session";
  status: "unredeemed" | "paired" | "streaming" | "revoked";
  /** Present only right after minting — the participant's one-paste link. */
  connectionString?: string;
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
  demo(): Promise<DemoPointer>;
  mintEnrollmentTokens(studyId: string, count: number, grain: "participant" | "session"): Promise<EnrollmentTokenView[]>;
  listEnrollmentTokens(studyId: string): Promise<EnrollmentTokenView[]>;
  revokeEnrollmentToken(studyId: string, tokenId: string): Promise<void>;
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

// --------------------------------------------------------------- HTTP backend

class HttpBackend implements Api {
  private base: string;
  constructor(base: string) {
    this.base = base;
  }

  private async call<T>(method: string, path: string, body?: unknown): Promise<T> {
    const res = await fetch(this.base + path, {
      method,
      headers: body ? { "content-type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      credentials: "include",
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        detail = (await res.json()).detail ?? detail;
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(res.status, detail);
    }
    return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
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
  demo = () => this.call<DemoPointer>("GET", "/demo");
  mintEnrollmentTokens = (studyId: string, count: number, grain: "participant" | "session") =>
    this.call<EnrollmentTokenView[]>("POST", `/studies/${studyId}/enrollment/tokens`, { count, grain });
  listEnrollmentTokens = (studyId: string) =>
    this.call<EnrollmentTokenView[]>("GET", `/studies/${studyId}/enrollment/tokens`);
  revokeEnrollmentToken = (studyId: string, tokenId: string) =>
    this.call<void>("DELETE", `/studies/${studyId}/enrollment/tokens/${tokenId}`);
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
  private sub = "you";
  private seq = 0;

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
  }

  private roleOn(slug: string): Role | null {
    const p = this.projects.get(slug);
    return p?.members.find((m,) => m.identitySub === this.sub)?.role ?? null;
  }

  private get(slug: string): FakeProject {
    const p = this.projects.get(slug);
    if (!p) throw new ApiError(404, "project not found");
    return p;
  }

  async me(): Promise<Me> {
    const memberships: Membership[] = [];
    for (const p of this.projects.values()) {
      const m = p.members.find((x,) => x.identitySub === this.sub);
      if (m) memberships.push({ projectSlug: p.slug, projectName: p.name, role: m.role });
    }
    return { sub: this.sub, displayName: "You", mode: "none", memberships };
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
      invitations: p.invitations.filter((i,) => !i.acceptedAt),
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
    const m = this.get(slug).members.find((x,) => x.identitySub === sub);
    if (!m) throw new ApiError(404, "member not found");
    m.role = role;
  }

  async removeMember(slug: string, sub: string): Promise<void> {
    const p = this.get(slug);
    const m = p.members.find((x,) => x.identitySub === sub);
    if (!m) throw new ApiError(404, "member not found");
    if (m.role === "owner" && p.members.filter((x,) => x.role === "owner").length <= 1) {
      throw new ApiError(409, "can't remove the last owner — transfer ownership first");
    }
    p.members = p.members.filter((x,) => x.identitySub !== sub);
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
    p.invitations = p.invitations.filter((i,) => i.id !== id || i.acceptedAt);
    if (p.invitations.length === before) throw new ApiError(404, "invitation not found");
  }

  async acceptInvitation(token: string): Promise<{ projectSlug: string; role: Role }> {
    for (const p of this.projects.values()) {
      const inv = p.invitations.find((i,) => i.token === token && !i.acceptedAt);
      if (inv) {
        inv.acceptedAt = new Date().toISOString();
        const existing = p.members.find((m,) => m.identitySub === this.sub);
        if (existing) existing.role = inv.role;
        else p.members.push({ identitySub: this.sub, role: inv.role, invitedBy: inv.id });
        return { projectSlug: p.slug, role: inv.role };
      }
    }
    throw new ApiError(404, "invitation not found — it may have expired or already been used");
  }

  async demo(): Promise<DemoPointer> {
    const p = this.get("demo");
    return { projectSlug: p.slug, projectName: p.name, studyId: p.studies[0]?.id ?? "" };
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
}

/** Pick the backend: the real API when VITE_API_BASE is set, else the
 * in-memory fake (offline dev, the hero demo, and tests). */
export function createApi(): Api {
  const base =
    typeof import.meta !== "undefined" ? import.meta.env?.VITE_API_BASE : undefined;
  return base ? new HttpBackend(base) : new InMemoryBackend();
}
