import { useEffect, useMemo, useRef, useState } from "react";
import { Field } from "@/components/ui/field";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ChevronRight, Plus, Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { EmptyState } from "@/components/shell/EmptyState";
import { useApi, useSession } from "@/lib/session";
import { useAsync } from "@/lib/useAsync";
import { ROLE_LABELS } from "@/lib/capabilities.ts";
import { ApiError, type ProjectSummary } from "@/lib/api.ts";
import { NAME_MAX_LENGTH } from "@/lib/uiText";
import { rememberStudyName, browserNameStore } from "@/lib/studyNames";

/* Project list and creation form. Study counts come from the list response. */

/** Show a filter when the list has more than six projects. */
const FILTER_THRESHOLD = 6;

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
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex min-w-0 items-baseline gap-2">
            <span
              className="truncate type-subhead text-text transition-colors duration-fast group-hover:text-accent"
              title={project.name}
            >
              {project.name}
            </span>
            {/* The address is the part that tells two long names apart once
              * the name itself is cut, so it keeps its own room. */}
            <span className="max-w-[40%] shrink-0 truncate type-caption text-text-muted" title={`/${project.slug}`}>
              /{project.slug}
            </span>
          </div>
          <span className="tabular type-caption text-text-muted">
            {summary}
          </span>
        </span>

        <span className="flex shrink-0 items-center gap-3">
          <span className="type-caption text-text-muted">
            {ROLE_LABELS[project.role]}
          </span>
          <ChevronRight
            className="hidden size-4 text-text-muted transition-all duration-fast group-hover:translate-x-0.5 group-hover:text-accent sm:block"
            aria-hidden
          />
        </span>
      </Link>
    </li>
  );
}

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
  const navigate = useNavigate();
  const { data, loading, error, reload } = useAsync(() => api.listProjects(), [api]);
  const [composing, setComposing] = useState(false);
  const [name, setName] = useState("");
  // Optional opening question for the project's first study.
  const [question, setQuestion] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [savedProject, setSavedProject] = useState<ProjectSummary | null>(null);
  const createInFlight = useRef(false);
  const [filter, setFilter] = useState("");
  const nameRef = useRef<HTMLInputElement>(null);
  /* `?new=1` is how the command palette's "New project" arrives: the
   * composer opens, and the flag is consumed so a refresh does not reopen it. */
  const [searchParams, setSearchParams] = useSearchParams();
  const wantsComposer = searchParams.get("new") === "1";
  useEffect(() => {
    if (!wantsComposer) return;
    setComposing(true);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("new");
        return next;
      },
      { replace: true },
    );
  }, [wantsComposer, setSearchParams]);

  useEffect(() => {
    if (composing) nameRef.current?.focus();
  }, [composing]);

  const openComposer = () => {
    setCreateError("");
    setComposing(true);
    nameRef.current?.focus();
  };

  const closeComposer = () => {
    if (createInFlight.current) return;
    setComposing(false);
    setName("");
    setQuestion("");
    setCreateError("");
    setSavedProject(null);
  };

  const create = async () => {
    if (!name.trim() || createInFlight.current) return;
    createInFlight.current = true;
    setCreating(true);
    setCreateError("");
    try {
      const project = savedProject ?? await api.createProject(name);
      setSavedProject(project);
      // Refresh both the project list and `me` so the creator's owner
      // membership on the new project resolves right away (role-gated controls
      // depend on it).
      reload();
      await refresh();

      // Start with one study so a new project opens directly into setup.
      const opening = question.trim();
      const study = await api.createStudy(project.slug, name);
      rememberStudyName(browserNameStore(), study.id, name);
      setName("");
      setQuestion("");
      setComposing(false);
      setSavedProject(null);
      navigate(`/p/${project.slug}/studies/${study.id}`, { state: { opening } });
    } catch (e) {
      // Only the API's own wording reaches the researcher; a bare HTTP status
      // ("Not Found") names no problem and suggests no recovery.
      setCreateError(
        e instanceof ApiError && e.fromServer
          ? e.message
          : "Could not finish setup. Try again in a moment; your entries are still here.",
      );
    } finally {
      setCreating(false);
      createInFlight.current = false;
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
    <div className="mx-auto flex max-w-reading flex-col gap-section p-gutter">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="type-title text-text">Projects</h1>
          <p className="type-body text-pretty text-text-muted">Organize studies and collaborators.</p>
        </div>
        {/* The empty state has its own create button. */}
        {!composing && data && data.length > 0 && (
          <Button onClick={openComposer}>
            <Plus aria-hidden /> New project
          </Button>
        )}
      </header>

      {composing && (
        <div className="form-stack rounded-card border border-border bg-surface p-4">
          <Field
            id="new-project-name"
            label="Name the project"
            hint={`A project owns its studies, papers and people. Up to ${NAME_MAX_LENGTH} characters; rename it later.`}
          >
            <Input
              ref={nameRef}
              placeholder="e.g. Pair programming"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={NAME_MAX_LENGTH}
              readOnly={Boolean(savedProject)}
              disabled={creating}
              onKeyDown={(e) => {
                if (e.key === "Enter") create();
                if (e.key === "Escape") closeComposer();
              }}
            />
          </Field>

          <Field
            id="new-project-question"
            label="What do you want to run?"
            hint="Optional. Describe a coding task, the AI comparison, and the outcome you want to capture. You will land in the setup conversation for the project's first study."
          >
            <Textarea
              autoGrow
              rows={2}
              placeholder="Coding task, AI comparison, outcome"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={creating}
            />
          </Field>

          <div className="flex flex-wrap gap-2">
            <Button onClick={create} disabled={!name.trim() || creating}>
              {creating ? "Creating…" : savedProject ? "Retry study creation" : "Create and start"}
            </Button>
            <Button variant="outline" onClick={closeComposer} disabled={creating}>
              Cancel
            </Button>
          </div>
          {createError && (
            <p role="alert" className="type-note text-critical">
              {savedProject && "The project was saved, but its first study could not be created. Retry to finish setup in the same project. "}
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
          line="No projects yet. Create one to organize your studies, papers, and collaborators."
          action={
            <div className="flex flex-wrap items-center justify-center gap-2">
              {!composing && (
                <Button onClick={openComposer}>
                  <Plus aria-hidden /> Create your first project
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
        >
          {shown.map((p) => (
            <ProjectRow key={p.slug} project={p} />
          ))}
        </ul>
      )}

      <section className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-border bg-surface-raised p-4">
        <div className="min-w-0 basis-64 grow">
          <h2 className="type-subhead text-text">
            Start from a study template
          </h2>
          <p className="type-note mt-0.5 max-w-reading text-text-muted">
            Browse designs with supporting references, then review the
            protocol for your study.
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link to="/repertoire">
            Browse templates <ChevronRight aria-hidden />
          </Link>
        </Button>
      </section>
    </div>
  );
}
