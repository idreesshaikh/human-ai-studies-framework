import { useEffect, useState } from "react";
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
import type { Membership } from "@/lib/api.ts";

/* ⌘K project switcher: fuzzy over project names; the empty state's action
 * is "create a project". Opening is global (⌘K / Ctrl-K). */
export function ProjectSwitcher({ memberships }: { memberships: Membership[] }) {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

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

  const go = (path: string) => {
    setOpen(false);
    navigate(path);
  };

  return (
    <>
      <button
        type="button"
        data-agent="project-switcher"
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 rounded-input border border-border px-2 py-1 text-xs text-text-muted transition-colors duration-fast hover:bg-accent-soft"
      >
        <FolderOpen className="size-3.5" aria-hidden />
        Switch project
        <kbd className="rounded border border-border px-1 text-[0.65rem]">⌘K</kbd>
      </button>
      <CommandDialog open={open} onOpenChange={setOpen} label="Switch project">
        <CommandInput placeholder="Find a project…" />
        <CommandList>
          <CommandEmpty>No project by that name.</CommandEmpty>
          <CommandGroup>
            {memberships.map((m) => (
              <CommandItem
                key={m.projectSlug}
                value={m.projectName}
                onSelect={() => go(`/p/${m.projectSlug}`)}
              >
                <FolderOpen className="size-4 text-text-muted" aria-hidden />
                {m.projectName}
                <span className="ml-auto text-xs text-text-muted">{m.role}</span>
              </CommandItem>
            ))}
            <CommandItem value="__new project" onSelect={() => go("/projects")}>
              <Plus className="size-4 text-accent" aria-hidden />
              New project…
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </>
  );
}
