import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, FolderOpen } from "lucide-react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import type { Membership, ProjectSummary } from "@/lib/api.ts";
import { ROLE_LABELS } from "@/lib/capabilities.ts";
import { useApi } from "@/lib/session";
import {
  NEW_PROJECT_PATH,
  isMacPlatform,
  paletteProjects,
  shortcutLabel,
} from "@/lib/uiText";

/* ⌘K / Ctrl K project switcher: fuzzy over project names. The list comes from
 * the same call /home makes, re-read each time the palette opens, so a viewer
 * project (the demo) is listed and a project created a minute ago is not
 * missing until reload. The session's memberships only seed the list for the
 * moment before that call answers. */
export function ProjectSwitcher({ memberships }: { memberships: Membership[] }) {
  const [open, setOpen] = useState(false);
  const [listed, setListed] = useState<ProjectSummary[] | null>(null);
  const navigate = useNavigate();
  const api = useApi();
  const mac = useMemo(
    () => isMacPlatform(typeof navigator === "undefined" ? undefined : navigator),
    [],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!open) return;
    let live = true;
    api
      .listProjects()
      .then((list) => live && setListed(paletteProjects(list)))
      .catch(() => {
        /* keep whatever is already listed; the seed below still works */
      });
    return () => {
      live = false;
    };
  }, [open, api]);

  const projects: { slug: string; name: string; role: ProjectSummary["role"] }[] =
    listed ??
    memberships.map((m) => ({
      slug: m.projectSlug,
      name: m.projectName,
      role: m.role,
    }));

  const go = (path: string) => {
    setOpen(false);
    navigate(path);
  };

  return (
    <>
      <button
        type="button"
        aria-label="Switch project"
        onClick={() => setOpen(true)}
        className="header-control"
      >
        <FolderOpen aria-hidden />
        <span className="hidden sm:inline">Switch project</span>
        <kbd className="type-legend hidden rounded-chip border border-border px-1.5 text-text-muted sm:inline">
          {shortcutLabel(mac)}
        </kbd>
      </button>
      <CommandDialog open={open} onOpenChange={setOpen} label="Switch project">
        <CommandInput placeholder="Find a project…" />
        <CommandList>
          <CommandEmpty>No project by that name.</CommandEmpty>
          <CommandGroup>
            {projects.map((p) => (
              <CommandItem
                key={p.slug}
                value={`${p.name} ${p.slug}`}
                onSelect={() => go(`/p/${p.slug}`)}
              >
                <FolderOpen className="size-4 shrink-0 text-text-muted" aria-hidden />
                <span className="min-w-0 flex-1 truncate" title={p.name}>
                  {p.name}
                </span>
                <span className="ml-2 shrink-0 type-caption text-text-muted">
                  {ROLE_LABELS[p.role]}
                </span>
              </CommandItem>
            ))}
          </CommandGroup>
          {/* Says where it goes: the Projects page, composer open. Always
            * mounted (`forceMount`), so a filter that matches nothing still
            * leaves the way to make the project being looked for. */}
          <CommandGroup forceMount>
            <CommandItem
              forceMount
              value="__new project"
              onSelect={() => go(NEW_PROJECT_PATH)}
            >
              <Plus className="size-4 shrink-0 text-text-muted" aria-hidden />
              New project…
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </>
  );
}
