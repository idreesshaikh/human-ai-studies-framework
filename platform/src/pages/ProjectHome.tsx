import { useNavigate, Link, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
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
  /* The naming field is revealed by "New study" rather than parked open, so
   * the page reads as a roster you return to instead of a form. */
  const [composing, setComposing] = useState(false);
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

  // Only the *first* load blanks the page; a post-delete `reload()` refetch
  // shouldn't unmount the whole tree while `studies` already reflects the
  // optimistic update — that remount was the delete-study flicker.
  if (loading && !data) return <p className="p-6 type-body text-text-muted">Loading…</p>;
  if (error) return <div className="p-gutter"><Notice kind="problem">{error}</Notice></div>;
  if (!data) return null;

  return (
    <div className="mx-auto flex max-w-work flex-col gap-section p-gutter">
      <div>
        <h1 className="type-title text-text">{data.name}</h1>
        <p className="type-body text-text-muted">/{data.slug}</p>
      </div>

      <section className="flex flex-col gap-3">
        {/* No icon beside the heading: a section title carries its own
          * weight, and a glyph next to every one of them is chrome the
          * reader has to skip past on the way to the content. */}
        <div className="flex items-end justify-between gap-3">
          <h2 className="type-section text-text">Studies</h2>
          {!composing && (
            <Button size="sm" onClick={() => setComposing(true)} data-agent="new-study-open">
              <Plus className="size-4" aria-hidden />
              New study
            </Button>
          )}
        </div>

        {/* The naming field is revealed by the action, not parked on the page.
          * A form sitting open above the roster made the page look like it
          * was for creating studies, when what a returning researcher comes
          * here to do is open one. */}
        {composing && (
          <div className="flex flex-col gap-2">
            <div className="flex gap-2">
              <Input
                autoFocus
                placeholder="Name a new study…"
                value={studyName}
                onChange={(e) => setStudyName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") newStudy();
                  if (e.key === "Escape") {
                    setComposing(false);
                    setStudyName("");
                  }
                }}
                aria-label="New study name"
              />
              <Button
                onClick={newStudy}
                disabled={!studyName.trim() || creating}
                data-agent="new-study"
              >
                {creating ? "Creating…" : "Create"}
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  setComposing(false);
                  setStudyName("");
                }}
              >
                Cancel
              </Button>
            </div>
            {createError && <Notice kind="problem">{createError}</Notice>}
          </div>
        )}

        {deleteError && <Notice kind="problem">{deleteError}</Notice>}

        {studies.length === 0 ? (
          <EmptyState line="Research goes better with a study. Start one above." />
        ) : (
          /* A roster, not a shelf. These are not alternatives to compare;
           * they are places to return to. */
          <ul className="divide-y divide-border overflow-hidden rounded-plate border border-border bg-surface">
            {studies.map((st) => (
              <li key={st.id} className="relative">
                <div className="group flex items-center gap-3 px-4 py-3 transition-colors duration-fast hover:bg-zone-9">
                  <Link
                    to={`/p/${slug}/studies/${st.id}`}
                    className="type-body min-w-0 flex-1 truncate font-semibold text-text after:absolute after:inset-0"
                  >
                    {st.id}
                  </Link>
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
                        "rounded-control text-text-muted opacity-0",
                        "transition-all duration-fast hover:bg-well",
                        "hover:text-critical group-hover:opacity-100",
                        "focus-visible:opacity-100",
                      )}
                    >
                      <Trash2 className="size-4" aria-hidden />
                    </button>
                  </RoleGate>
                </div>
                {confirmDelete === st.id && (
                  <div className="relative z-10 flex items-center gap-1 border-t border-border bg-well px-4 py-2">
                    <span className="type-caption flex-1 text-text-muted">
                      Delete this study? This cannot be undone.
                    </span>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-critical"
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
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="type-section text-text">Team</h2>
          {/* Not accent-coloured. The one accent on a screen belongs to the
            * action that screen is for; a secondary link tinted the same
            * blue makes the researcher check two things to find one. */}
          <Link
            to={`/p/${slug}/members`}
            className="type-caption text-text-muted underline decoration-border underline-offset-4 transition-colors duration-fast hover:text-text hover:decoration-control-edge"
          >
            Manage members
          </Link>
        </div>
        <div className="flex flex-wrap gap-2">
          {data.members.map((m) => (
            <span
              key={m.identitySub}
              className="type-caption flex items-center gap-2 rounded-chip border border-border bg-surface px-2 py-1 text-text"
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
