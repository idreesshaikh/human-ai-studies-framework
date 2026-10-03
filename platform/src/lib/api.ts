import type { Role } from "./capabilities.ts";

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

  preferences: Preferences;
}

export type ResearcherProfile =
  | "student"
  | "new-researcher"
  | "experienced"
  | "industry";

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
  enabledInstruments: { name: string; enabled: boolean; }[];
  producerStates?: Record<string, string>;
  privacyPolicy?: Record<string, unknown>;
}

export interface ToggleCatalogEntry {
  instrument: string;
  leg?: string;
  path: string[];
  label: string;
  description: string;
  grounding: { ref?: string; source?: string; unsourced?: boolean; };
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

  connectionString?: string;

  captureConfig?: EnrollmentTokenCaptureConfig | null;

  captureOverrides?: CaptureOverrides | null;
}

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
  ): Promise<{ id: string; }>;
  deleteStudy(studyId: string): Promise<void>;
  renameProject(slug: string, name: string): Promise<void>;
  deleteProject(slug: string, confirm: string): Promise<void>;
  members(slug: string): Promise<Member[]>;
  changeRole(slug: string, sub: string, role: Role): Promise<void>;
  removeMember(slug: string, sub: string): Promise<void>;
  createInvitation(slug: string, role: Role): Promise<Invitation>;
  revokeInvitation(slug: string, id: string): Promise<void>;
  acceptInvitation(token: string): Promise<{ projectSlug: string; role: Role; }>;
  mintEnrollmentTokens(
    studyId: string,
    count: number,
    grain: "participant" | "session",
    overrides?: CaptureOverrides | null,
  ): Promise<EnrollmentTokenView[]>;
  listEnrollmentTokens(studyId: string): Promise<EnrollmentTokenView[]>;
  revokeEnrollmentToken(studyId: string, tokenId: string): Promise<void>;
  toggleCatalog(studyId: string): Promise<ToggleCatalogEntry[]>;
  applyToggle(studyId: string, body: { instrument: string; path: string[]; value: unknown; rationale: string; }): Promise<ToggleResult>;

  updatePreferences(prefs: Partial<Preferences>): Promise<Preferences>;

  researcherProfiles(): Promise<{
    profiles: { id: string; label: string; description: string; }[];
    default: string;
  }>;
}

export class ApiError extends Error {
  status: number;

  fromServer: boolean;
  constructor(status: number, message: string, fromServer = true) {
    super(message);
    this.status = status;
    this.fromServer = fromServer;
  }
}

export class OfflineError extends Error {
  constructor() {
    super("Could not reach the study server. Check your connection and try again.");
    this.name = "OfflineError";
  }
}

let tokenProvider: () => Promise<string | null> = async () =>
  localStorage.getItem("middleware.token");

export function setTokenProvider(provider: () => Promise<string | null>): void {
  tokenProvider = provider;
}

const unauthorizedListeners = new Set<() => void>();

export function onUnauthorized(listener: () => void): () => void {
  unauthorizedListeners.add(listener);
  return () => unauthorizedListeners.delete(listener);
}

export async function getAuthToken(): Promise<string | null> {
  return tokenProvider();
}

export function notifyUnauthorized(): void {
  unauthorizedListeners.forEach((l) => l());
}

export async function request<T>(path: string, init: RequestInit = {}, base = apiBase()): Promise<T> {
  const token = await tokenProvider();
  let res: Response;
  try {
    res = await fetch(base + path, {
      ...init,
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init.headers ?? {}),
      },
      credentials: "include",
    });
  } catch {
    throw new OfflineError();
  }
  if (!res.ok) {
    const contentType = (res.headers.get("content-type") ?? "").toLowerCase();
    if (res.status === 404 && !contentType.includes("application/json")) {
      throw new OfflineError();
    }
    let detail = res.statusText || `Request failed (${res.status})`;
    let fromServer = false;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string" && body.detail.trim()) {
        detail = body.detail;
        fromServer = true;
      }
    } catch {
      fromServer = false;
    }
    if (res.status === 401) unauthorizedListeners.forEach((l) => l());
    throw new ApiError(res.status, detail, fromServer);
  }
  if (res.status === 204) return undefined as T;
  try {
    return (await res.json()) as T;
  } catch {
    throw new OfflineError();
  }
}

class HttpBackend implements Api {
  private base: string;
  constructor(base: string) {
    this.base = base;
  }

  private call<T>(method: string, path: string, body?: unknown): Promise<T> {
    return request<T>(path, {
      method,
      headers: body ? { "content-type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    }, this.base);
  }

  me = () => this.call<Me>("GET", "/me");
  listProjects = () => this.call<ProjectSummary[]>("GET", "/projects");
  createProject = (name: string) =>
    this.call<ProjectSummary>("POST", "/projects", { name });
  projectHome = (slug: string) => this.call<ProjectHome>("GET", `/projects/${slug}`);
  createStudy = (slug: string, name: string, protocol?: Record<string, unknown>) =>
    this.call<{ id: string; }>("POST", `/projects/${slug}/studies`, {
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
    this.call<{ projectSlug: string; role: Role; }>(
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
  applyToggle = (studyId: string, body: { instrument: string; path: string[]; value: unknown; rationale: string; }) =>
    this.call<ToggleResult>("POST", `/studies/${studyId}/enrollment/toggles`, body);
  updatePreferences = (prefs: Partial<Preferences>) =>
    this.call<{ sub: string; preferences: Preferences; }>(
      "PUT",
      "/me/preferences",
      { preferences: prefs },
    ).then((r) => r.preferences);
  researcherProfiles = () =>
    this.call<{
      profiles: { id: string; label: string; description: string; }[];
      default: string;
    }>("GET", "/conversation/profiles");
}

export function apiBase(): string {
  return (
    (typeof import.meta !== "undefined" ? import.meta.env?.VITE_API_BASE : undefined) ?? ""
  ).replace(/\/+$/, "");
}

export function createApi(): Api {
  return new HttpBackend(apiBase());
}
