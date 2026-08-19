import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronRight, Plus, Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/shell/EmptyState";
import { useApi, useSession } from "@/lib/session";
import { useAsync } from "@/lib/useAsync";
import { ROLE_LABELS } from "@/lib/capabilities.ts";
import { ApiError, type ProjectSummary } from "@/lib/api.ts";

/* The project list, and the one place a project is created.
 *
 * A row's job is to answer "which project?" in one glance, so it carries the
 * shape of what is inside — how many studies — rather than a name and a
 * folder icon. The count arrives on the list response itself
 * (`GET /projects`), so the answer costs no extra request.
 *
 * Rows used to carry a seven-segment lifecycle rail as well. It went with the
 * lifecycle board: with no phases to advance through, every project sat lit
 * in the same segment, which is a decoration pretending to be a status.
 *
 * The rows share one bordered sheet with hairline dividers instead of being
 * separate cards: a list of comparable things reads as a list.
 */

/** Above this many projects the list stops being scannable and earns a
 * filter; below it, the field is one more control for no gain. */
const FILTER_THRESHOLD = 6;

/** The one line under a project's name: how much is inside it. */
function studySummary(count: number): string {
  if (count === 0) return "No studies yet";
  return count === 1 ? "1 study" : `${count} studies`;
}

function ProjectRow({ project }: { project: ProjectSummary }) {
  const summary = studySummary(project.studyCount);
  return (
    <li>
      <Link
        to={`/p/${project.slug}`}
        className="group flex items-center gap-4 p-4 transition-colors duration-fast hover:bg-surface-raised"
      >
        <span className="flex min-w-0 flex-1 flex-wrap items-center gap-x-4 gap-y-3">
          <span className="min-w-0 grow basis-48">
            <span className="block truncate type-subhead text-text transition-colors duration-fast group-hover:text-accent">
              {project.name}
            </span>
            <span className="block truncate type-caption text-text-muted">
              /{project.slug}
            </span>
          </span>

          <span className="flex min-w-0 grow-[1.5] basis-72 flex-col gap-1.5">
            <span className="tabular type-caption text-text-muted sm:truncate" title={summary}>
              {summary}
            </span>
          </span>
        </span>

        <span className="flex shrink-0 items-center gap-3">
          <Badge variant="outline">{ROLE_LABELS[project.role]}</Badge>
          <ChevronRight
            className="hidden size-4 text-text-muted transition-all duration-fast group-hover:translate-x-0.5 group-hover:text-accent sm:block"
            aria-hidden
          />
        </span>
      </Link>
    </li>
  );
}

/* Loading shows the shape the answer will take, not the word "Loading".
 * Three rows because that is roughly what a real list looks like, and a
 * skeleton that lies about the count is worse than none. */
function RowSkeleton() {
  return (
    <li className="flex items-center gap-4 p-4">
      <span className="flex min-w-0 flex-1 flex-wrap items-center gap-x-4 gap-y-3">
        <span className="min-w-0 grow basis-48">
          <span className="block h-5 w-44 rounded-chip bg-zone-8" />
          <span className="mt-2 block h-3 w-24 rounded-chip bg-zone-9" />
        </span>
        <span className="flex min-w-0 grow-[1.5] basis-72 flex-col gap-1.5">
          <span className="block h-1.5 rounded-full bg-zone-8" />
          <span className="block h-3 w-36 rounded-chip bg-zone-9" />
        </span>
      </span>
    </li>
  );
}

export function Projects() {
  const api = useApi();
  const { refresh } = useSession();
  const { data, loading, error, reload } = useAsync(() => api.listProjects(), [api]);
  const [composing, setComposing] = useState(false);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [filter, setFilter] = useState("");
  const nameRef = useRef<HTMLInputElement>(null);

  // The composer opens focused: it is opened by an explicit click, so moving
  // the caret into it is finishing that action rather than stealing focus.
  useEffect(() => {
    if (composing) nameRef.current?.focus();
  }, [composing]);

  const openComposer = () => {
    setCreateError("");
    setComposing(true);
    nameRef.current?.focus();
  };

  const closeComposer = () => {
    setComposing(false);
    setName("");
    setCreateError("");
  };

  const create = async () => {
    if (!name.trim() || creating) return;
    setCreating(true);
    setCreateError("");
    try {
      await api.createProject(name);
      setName("");
      setComposing(false);
      // Refresh both the project list and `me` so the creator's owner
      // membership on the new project resolves right away (role-gated controls
      // depend on it).
      reload();
      await refresh();
    } catch (e) {
      // Only the API's own wording reaches the researcher; a bare HTTP status
      // ("Not Found") names no problem and suggests no recovery.
      setCreateError(
        e instanceof ApiError && e.fromServer
          ? e.message
          : "Could not create the project. The server didn't accept the request. Try again in a moment.",
      );
    } finally {
      setCreating(false);
    }
  };

  const needle = filter.trim().toLowerCase();
  const shown = useMemo(
    () =>
      !data
        ? []
        : needle
          ? data.filter(
              (p) =>
                p.name.toLowerCase().includes(needle) ||
                p.slug.toLowerCase().includes(needle),
            )
          : data,
    [data, needle],
  );

  return (
    <div className="mx-auto flex max-w-work flex-col gap-section p-gutter">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="type-title text-text">Projects</h1>
          <p className="type-body text-text-muted">The rooms your studies live in.</p>
        </div>
        {!composing && (
          <Button onClick={openComposer} data-agent="new-project">
            <Plus aria-hidden /> New project
          </Button>
        )}
      </header>

      {composing && (
        <div className="flex flex-col gap-3 rounded-card border border-border bg-surface p-4 shadow-mark">
          <label htmlFor="new-project-name" className="type-label text-text">
            Name the project
          </label>
          <div className="flex flex-wrap gap-2">
            <Input
              id="new-project-name"
              ref={nameRef}
              className="min-w-0 flex-1 basis-56"
              placeholder="Pair programming with agents"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") create();
                if (e.key === "Escape") closeComposer();
              }}
              aria-describedby="new-project-hint"
            />
            <Button onClick={create} disabled={!name.trim() || creating}>
              {creating ? "Creating…" : "Create"}
            </Button>
            <Button variant="outline" onClick={closeComposer} disabled={creating}>
              Cancel
            </Button>
          </div>
          <p id="new-project-hint" className="type-caption text-text-muted">
            A project owns its studies, the papers behind them, and the people you
            work with. You can rename it later.
          </p>
          {createError && (
            <p role="alert" className="type-caption text-critical">
              {createError}
            </p>
          )}
        </div>
      )}

      {data && data.length > FILTER_THRESHOLD && (
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-muted"
            aria-hidden
          />
          <Input
            className="pl-9"
            type="search"
            placeholder="Filter projects…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            onKeyDown={(e) => e.key === "Escape" && setFilter("")}
            aria-label="Filter projects by name or slug"
          />
        </div>
      )}

      {loading && !data && (
        <ul
          className="animate-pulse divide-y divide-border overflow-hidden rounded-card border border-border bg-surface shadow-sheet"
          aria-label="Loading projects"
          aria-busy="true"
        >
          <RowSkeleton />
          <RowSkeleton />
          <RowSkeleton />
        </ul>
      )}

      {error && (
        <Notice kind="problem">{error}</Notice>
      )}

      {data && data.length === 0 && (
        <EmptyState
          line="No projects yet. A project is the room a study lives in. It owns the studies, the papers behind them, and the people you work with."
          action={
            <div className="flex flex-wrap items-center justify-center gap-2">
              {!composing && (
                <Button onClick={openComposer}>
                  <Plus aria-hidden /> Create your first project
                </Button>
              )}
              {/* Templates-first: the repertoire needs no project, so a
               * researcher with no project yet can still start from a
               * proven design shape. */}
              <Button asChild variant="outline">
                <Link to="/repertoire">
                  Browse proven designs <ChevronRight aria-hidden />
                </Link>
              </Button>
            </div>
          }
        />
      )}

      {data && data.length > 0 && shown.length === 0 && (
        <EmptyState
          line={`No project matches “${filter.trim()}”.`}
          action={
            <Button variant="outline" onClick={() => setFilter("")}>
              <X aria-hidden /> Clear the filter
            </Button>
          }
        />
      )}

      {shown.length > 0 && (
        <ul
          className="divide-y divide-border overflow-hidden rounded-card border border-border bg-surface shadow-sheet"
          data-agent="project-list"
        >
          {shown.map((p) => (
            <ProjectRow key={p.slug} project={p} />
          ))}
        </ul>
      )}

      {/* Templates-first: the repertoire needs no project, so it sits below
       * the roster — the second way in for a researcher who already knows
       * the shape they want. */}
      <section className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-border bg-surface-raised p-4">
        <div className="min-w-0 basis-64 grow">
          <h2 className="type-subhead text-text">
            Start from a proven design
          </h2>
          <p className="type-caption mt-0.5 max-w-reading text-text-muted">
            The protocol repertoire: design shapes ranked by how widely the
            published corpus uses them. Pick two or more and merge them into
            one grounded protocol.
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link to="/repertoire">
            Browse the repertoire <ChevronRight aria-hidden />
          </Link>
        </Button>
      </section>
    </div>
  );
}
