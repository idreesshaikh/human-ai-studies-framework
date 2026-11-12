import { useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ChevronRight, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Notice } from "@/components/ui/notice";
import { EmptyState } from "@/components/shell/EmptyState";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from "@/components/ui/dialog";
import { useApi, useSession } from "@/lib/session";
import { useAsync } from "@/lib/useAsync";
import { hasRole } from "@/lib/capabilities";
import { ApiError, type StudySummary } from "@/lib/api";
import { NAME_MAX_LENGTH } from "@/lib/uiText";
import { browserNameStore, rememberStudyName, studyDisplayName } from "@/lib/studyNames";
import { studyContainer } from "@/lib/studyContainer";

export function Studies() {
  const api = useApi();
  const { me, loading: meLoading, refresh } = useSession();
  const navigate = useNavigate();
  const { data, loading, error, reload } = useAsync(() => api.listStudies(), [api]);
  const [composing, setComposing] = useState(false);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<StudySummary | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  const names = browserNameStore();

  const studies = useMemo(
    () =>
      [...(data ?? [])].sort((a, b) =>
        studyDisplayName(names, a.id).localeCompare(studyDisplayName(names, b.id)),
      ),
    [data, names],
  );

  const startCreating = () => {
    setCreateError("");
    setComposing(true);
    requestAnimationFrame(() => nameRef.current?.focus());
  };

  const create = async () => {
    const title = name.trim();
    if (!title || creating || meLoading) return;
    setCreating(true);
    setCreateError("");
    try {
      const slug = await studyContainer(api, me, refresh);
      const study = await api.createStudy(slug, title);
      rememberStudyName(names, study.id, title);
      await refresh();
      navigate(`/studies/${encodeURIComponent(study.id)}`);
    } catch (e) {
      setCreateError(
        e instanceof ApiError && e.fromServer
          ? e.message
          : "Could not create the study. Try again in a moment.",
      );
    } finally {
      setCreating(false);
    }
  };

  const remove = async () => {
    if (!deleteTarget || deleting) return;
    setDeleting(true);
    setDeleteError("");
    try {
      await api.deleteStudy(deleteTarget.id);
      setDeleteTarget(null);
      reload();
    } catch (e) {
      setDeleteError(e instanceof ApiError ? e.message : "Could not delete this study.");
    } finally {
      setDeleting(false);
    }
  };

  const changeDeleteOpen = (open: boolean) => {
    if (deleting) return;
    if (!open) {
      setDeleteTarget(null);
      setDeleteError("");
    }
  };

  const deleteName = deleteTarget
    ? studyDisplayName(names, deleteTarget.id)
    : "";

  return (
    <div className="mx-auto flex max-w-reading flex-col gap-section p-gutter">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="type-title text-text">Studies</h1>
          <p className="type-body mt-1 max-w-[68ch] text-pretty text-text-muted">
            Your study designs and research data.
          </p>
        </div>
        {studies.length > 0 && !composing && (
          <Button onClick={startCreating}>
            <Plus aria-hidden /> New study
          </Button>
        )}
      </header>

      {composing && (
        <form
          className="flex flex-col gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            void create();
          }}
        >
          <label className="type-label font-medium text-text" htmlFor="new-study-name">
            Study name
          </label>
          <div className="flex flex-wrap gap-2">
            <Input
              ref={nameRef}
              id="new-study-name"
              autoFocus
              placeholder="e.g. AI assistance and debugging"
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={NAME_MAX_LENGTH}
              disabled={creating || meLoading}
            />
            <Button type="submit" disabled={!name.trim() || creating || meLoading}>
              {creating ? "Creating…" : "Create study"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              disabled={creating}
              onClick={() => {
                setComposing(false);
                setName("");
                setCreateError("");
              }}
            >
              Cancel
            </Button>
          </div>
          {createError && <Notice kind="problem">{createError}</Notice>}
        </form>
      )}

      {error && <Notice kind="problem">{error}</Notice>}

      {loading && !data && (
        <p role="status" className="type-body text-text-muted">
          Loading studies…
        </p>
      )}

      {data && data.length === 0 && (
        <EmptyState
          line="No studies yet. Start one here or choose a template."
          action={
            <div className="flex flex-wrap justify-center gap-2">
              {!composing && (
                <Button onClick={startCreating}>
                  <Plus aria-hidden /> New study
                </Button>
              )}
              <Button asChild variant="outline">
                <Link to="/repertoire">
                  Browse templates <ChevronRight aria-hidden />
                </Link>
              </Button>
            </div>
          }
        />
      )}

      {studies.length > 0 && (
        <ul className="divide-y divide-border border-y border-border bg-surface">
          {studies.map((study) => {
            const title = studyDisplayName(names, study.id);
            return (
              <li key={study.id} className="flex items-center gap-2 px-2 sm:px-3">
                <Link
                  to={`/studies/${encodeURIComponent(study.id)}`}
                  className="flex min-h-14 min-w-0 flex-1 items-center justify-between gap-3 rounded-control px-2 py-2 transition-colors duration-fast hover:bg-zone-9 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
                  title={title}
                >
                  <span className="truncate type-body font-medium text-text">{title}</span>
                  <span className="shrink-0 type-caption text-text-muted">
                    {study.hasProtocol ? "Protocol ready" : "Setup in progress"}
                  </span>
                </Link>
                {hasRole(study.role, "delete") && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={`Delete ${title}`}
                    onClick={() => {
                      setDeleteError("");
                      setDeleteTarget(study);
                    }}
                  >
                    <Trash2 aria-hidden />
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <Dialog
        open={Boolean(deleteTarget)}
        onOpenChange={changeDeleteOpen}
      >
        <DialogContent>
          <DialogTitle>Delete this study?</DialogTitle>
          <DialogDescription className="mt-2">
            “{deleteName}” and its collected data will be permanently deleted. This can’t be undone.
          </DialogDescription>
          {deleteError && <Notice kind="problem" className="mt-3">{deleteError}</Notice>}
          <DialogFooter>
            <Button variant="outline" disabled={deleting} onClick={() => changeDeleteOpen(false)}>
              Cancel
            </Button>
            <Button variant="danger" disabled={deleting} onClick={() => void remove()}>
              {deleting ? "Deleting…" : "Delete study"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
