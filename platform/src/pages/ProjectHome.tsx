import { useNavigate, Link, useParams } from "react-router-dom";
import { useState } from "react";
import { FlaskConical, Users, Plus, Trash2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/shell/EmptyState";
import { RoleGate } from "@/components/shell/RoleGate";
import { useApi, useSession } from "@/lib/session";
import { useAuth } from "@/lib/auth.tsx";
import { useAsync } from "@/lib/useAsync";
import { memberLabel } from "@/lib/memberLabel";
import { ApiError } from "@/lib/api.ts";
import type { Role } from "@/lib/capabilities.ts";
import { cn } from "@/lib/cn";

/* Project home: its studies, and a preview of who's on the team. */
export function ProjectHome() {
  const api = useApi();
  const { me, refresh } = useSession();
  const { user } = useAuth();
  const navigate = useNavigate();
  const { slug = "" } = useParams();
  const { data, loading, error, reload } = useAsync(() => api.projectHome(slug), [api, slug]);
  const [studyName, setStudyName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  // Two-step confirm for study deletion: first click arms, second deletes.
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  // Studies mid-exit-animation — kept out of the render so the card fades out
  // before the reload removes it for real.
  const [removed, setRemoved] = useState<Set<string>>(new Set());

  // The caller's role. Prefer the freshly-loaded project payload (its members
  // carry the real role) over the session's `me`, which can be stale for a
  // project joined/created this session — a stale "viewer" would wrongly hide
  // the owner-only delete control (the "delete doesn't work" symptom).
  const mine: Role =
    data?.members.find((m) => m.identitySub === me?.sub)?.role ??
    me?.memberships.find((m) => m.projectSlug === slug)?.role ??
    "viewer";

  const removeStudy = async (studyId: string) => {
    setDeleting(studyId);
    try {
      await api.deleteStudy(studyId);
      setConfirmDelete(null);
      // Play the exit animation, then reload so the row is gone for real.
      setRemoved((prev) => new Set(prev).add(studyId));
      setTimeout(() => reload(), 200);
    } catch {
      // Leave the row; a retry reflects the real state.
    } finally {
      setDeleting(null);
    }
  };

  const newStudy = async () => {
    if (!studyName.trim()) return;
    setCreating(true);
    setCreateError("");
    try {
      const study = await api.createStudy(slug, studyName);
      // Refresh `me` so the new study's membership/role resolves immediately —
      // otherwise role-gated controls (e.g. Mint links) stay hidden until an
      // unrelated refresh fires.
      await refresh();
      navigate(`/p/${slug}/studies/${study.id}`);
    } catch (e) {
      setCreateError(e instanceof ApiError ? e.message : "Could not create the study.");
      setCreating(false);
    }
  };

  if (loading) return <p className="p-6 text-sm text-text-muted">Loading…</p>;
  if (error) return <p className="p-6 text-sm text-unsourced">{error}</p>;
  if (!data) return null;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 p-6">
      <div>
        <h1 className="font-serif text-3xl font-medium tracking-tight text-text">{data.name}</h1>
        <p className="text-sm text-text-muted">/{data.slug}</p>
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="flex items-center gap-2 text-sm font-medium text-text">
          <FlaskConical className="size-4 text-text-muted" aria-hidden /> Studies
        </h2>
        <Card>
          <CardContent className="flex flex-col gap-2 p-4">
            <div className="flex gap-2">
              <Input
                placeholder="Name a new study…"
                value={studyName}
                onChange={(e) => setStudyName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && newStudy()}
                aria-label="New study name"
              />
              <Button onClick={newStudy} disabled={!studyName.trim() || creating} data-agent="new-study">
                <Plus className="size-4" aria-hidden />
                {creating ? "Creating…" : "Create"}
              </Button>
            </div>
            {createError && <p className="text-sm text-unsourced">{createError}</p>}
          </CardContent>
        </Card>
        {data.studies.length === 0 ? (
          <EmptyState line="Research goes better with a study. Start one above." />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {data.studies.map((st) => (
              <Card
                key={st.id}
                className={cn(
                  "group relative transition-all duration-standard hover:border-accent",
                  removed.has(st.id) &&
                    "pointer-events-none scale-95 opacity-0",
                )}
              >
                <Link to={`/p/${slug}/studies/${st.id}`} className="block">
                  <CardContent className="flex items-center justify-between gap-2 p-4">
                    <span className="min-w-0 flex-1 truncate font-medium text-text">
                      {st.id}
                    </span>
                    <Badge variant="outline">{st.phase}</Badge>
                  </CardContent>
                </Link>
                <RoleGate role={mine} capability="delete">
                  {confirmDelete === st.id ? (
                    <div className="flex items-center gap-1 border-t border-border px-3 py-1.5 text-xs">
                      <span className="flex-1 text-text-muted">Delete this study?</span>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-status-critical"
                        disabled={deleting === st.id}
                        onClick={() => removeStudy(st.id)}
                      >
                        {deleting === st.id ? "Deleting…" : "Delete"}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(null)}>
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setConfirmDelete(st.id)}
                      aria-label={`Delete study ${st.id}`}
                      className={cn(
                        "absolute right-2 top-2 rounded-input p-1 text-text-muted",
                        "opacity-0 transition-opacity duration-fast hover:bg-accent-soft hover:text-status-critical",
                        "focus-visible:opacity-100 group-hover:opacity-100",
                      )}
                    >
                      <Trash2 className="size-4" aria-hidden />
                    </button>
                  )}
                </RoleGate>
              </Card>
            ))}
          </div>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-sm font-medium text-text">
            <Users className="size-4 text-text-muted" aria-hidden /> Team
          </h2>
          <Link to={`/p/${slug}/members`} className="text-xs text-accent hover:underline">
            Manage members
          </Link>
        </div>
        <div className="flex flex-wrap gap-2">
          {data.members.map((m) => (
            <span
              key={m.identitySub}
              className="flex items-center gap-2 rounded-chip border border-border px-2 py-1 text-xs text-text"
            >
              <Avatar name={memberLabel(m, user)} className="size-5" />
              {memberLabel(m, user)}
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}
