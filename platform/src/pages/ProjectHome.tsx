import { useNavigate, Link, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
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
import { resolveRole, roleOrNull } from "@/lib/role";
import { cn } from "@/lib/cn";

/* Project home: its studies, and a preview of who's on the team. */
export function ProjectHome() {
  const api = useApi();
  const { me, loading: meLoading, refresh } = useSession();
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
  const [deleteError, setDeleteError] = useState("");
  // The list the page renders. Held locally so a delete can be applied
  // optimistically and *rolled back* if the server refuses — the same shape
  // MembersTable uses. The previous version swallowed every error, so a 403,
  // a 404, or being offline all looked identical to nothing happening.
  type Study = NonNullable<typeof data>["studies"][number];
  const [studies, setStudies] = useState<Study[]>([]);
  useEffect(() => {
    if (data) setStudies(data.studies);
  }, [data]);

  // My role here — and whether that is known yet. Treating "still loading" as
  // "viewer" is what made the delete control appear a beat late, or seem to
  // be missing altogether.
  const roleState = resolveRole({
    projectMembers: data?.members,
    meSub: me?.sub,
    memberships: me?.memberships,
    meLoading,
    slug,
  });
  const mine = roleOrNull(roleState);
  const rolePending = roleState.status === "loading";

  const removeStudy = async (studyId: string) => {
    const before = studies;
    setDeleting(studyId);
    setDeleteError("");
    // Optimistic: the row goes now, and comes back if the server disagrees.
    setStudies((list) => list.filter((s) => s.id !== studyId));
    setConfirmDelete(null);
    try {
      await api.deleteStudy(studyId);
      reload();
    } catch (e) {
      setStudies(before);
      setDeleteError(
        e instanceof ApiError ? e.message : "Could not delete that study.",
      );
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
    <div className="mx-auto flex max-w-work flex-col gap-section p-gutter">
      <div>
        <h1 className="type-title text-text">{data.name}</h1>
        <p className="text-sm text-text-muted">/{data.slug}</p>
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="type-subhead flex items-center gap-2 text-text">
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
        {deleteError && (
          <p role="alert" className="text-sm text-status-critical">
            {deleteError}
          </p>
        )}
        {studies.length === 0 ? (
          <EmptyState line="Research goes better with a study. Start one above." />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {studies.map((st) => (
              <Card
                key={st.id}
                className="group relative transition-colors duration-standard hover:border-accent"
              >
                {/* The delete control is a real cell in this row, not an
                  * overlay. It used to be positioned absolutely on top of the
                  * card, which put it over the phase badge and over long study
                  * ids. The link stretches to fill the card instead
                  * (after:inset-0), so the whole card still navigates while
                  * the button keeps its own space. */}
                <CardContent className="flex items-center gap-2 p-4">
                  <Link
                    to={`/p/${slug}/studies/${st.id}`}
                    className="min-w-0 flex-1 truncate font-medium text-text after:absolute after:inset-0"
                  >
                    {st.id}
                  </Link>
                  <Badge variant="outline" className="relative shrink-0">
                    {st.phase}
                  </Badge>
                  <RoleGate
                    role={mine}
                    capability="delete"
                    pending={rolePending}
                    /* Hold the space while the role loads, so the row doesn't
                     * reflow when the answer arrives. */
                    pendingFallback={<span aria-hidden className="min-h-11 min-w-11 shrink-0" />}
                  >
                    <button
                      type="button"
                      onClick={() => setConfirmDelete(st.id)}
                      aria-label={`Delete study ${st.id}`}
                      className={cn(
                        "relative z-10 flex min-h-11 min-w-11 shrink-0 items-center justify-center",
                        "rounded-input text-text-muted opacity-60",
                        "transition-colors duration-fast hover:bg-accent-soft",
                        "hover:text-status-critical hover:opacity-100",
                        "focus-visible:opacity-100",
                      )}
                    >
                      <Trash2 className="size-4" aria-hidden />
                    </button>
                  </RoleGate>
                </CardContent>
                {confirmDelete === st.id && (
                  <div className="relative z-10 flex items-center gap-1 border-t border-border px-3 py-1.5 text-xs">
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
                )}
              </Card>
            ))}
          </div>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="type-subhead flex items-center gap-2 text-text">
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
