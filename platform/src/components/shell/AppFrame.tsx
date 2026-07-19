import { useState } from "react";
import { Link, NavLink, useParams } from "react-router-dom";
import { Menu, Moon, Sun, Monitor, LogOut, FlaskConical, Users, Settings, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ProjectSwitcher } from "./ProjectSwitcher";
import { useSession } from "@/lib/session";
import { applyTheme, getTheme, nextTheme, type Theme } from "@/lib/theme";
import { cn } from "@/lib/cn";

const THEME_ICON = { system: Monitor, light: Sun, dark: Moon };

/* The signed-in chrome: a project-scoped sidebar + a top bar (breadcrumb,
 * project switcher, theme, account). Collapses to a toggle on narrow
 * viewports. */
export function AppFrame({ children }: { children: React.ReactNode }) {
  const { me } = useSession();
  const { slug } = useParams();
  const [theme, setTheme] = useState<Theme>(() => getTheme());
  const [navOpen, setNavOpen] = useState(false);
  const Icon = THEME_ICON[theme];

  const cycleTheme = () => {
    const next = nextTheme(theme);
    applyTheme(next);
    setTheme(next);
  };

  const navItem = (to: string, label: string, icon: React.ReactNode) => (
    <NavLink
      to={to}
      end
      onClick={() => setNavOpen(false)}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-2 rounded-input border-2 px-2.5 py-1.5 font-display text-xs font-semibold uppercase tracking-wide transition-colors duration-fast",
          isActive
            ? "border-border-strong bg-accent text-accent-contrast shadow-brutal-sm"
            : "border-transparent text-text hover:border-border-strong hover:bg-accent-soft hover:text-accent",
        )
      }
    >
      {icon}
      {label}
    </NavLink>
  );

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-3 border-b-2 border-border-strong bg-surface px-4 py-2">
        <button
          type="button"
          className="rounded-input border-2 border-transparent p-1 text-text hover:border-border-strong hover:bg-accent-soft lg:hidden"
          onClick={() => setNavOpen((v) => !v)}
          aria-label="Toggle navigation"
        >
          <Menu className="size-5" aria-hidden />
        </button>
        <Link to="/projects" className="flex items-center gap-2" aria-label="Study Designer — home">
          <span
            aria-hidden
            className="inline-grid size-6 shrink-0 place-items-center rounded-input border-2 border-border-strong bg-accent font-display text-xs font-bold text-accent-contrast shadow-brutal-sm"
          >
            ◆
          </span>
          <span className="font-display text-sm font-bold uppercase tracking-widest text-text">
            Study<span className="text-accent">·</span>Designer
          </span>
        </Link>
        <div className="ml-auto flex items-center gap-2">
          <ProjectSwitcher memberships={me?.memberships ?? []} />
          <Button variant="ghost" size="icon" onClick={cycleTheme} aria-label={`Theme: ${theme}`}>
            <Icon aria-hidden />
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="rounded-chip" aria-label="Account">
                <Avatar name={me?.displayName ?? "You"} />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>
                {me?.displayName ?? "You"} · {me?.mode ?? "local"}
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link to="/projects">All projects</Link>
              </DropdownMenuItem>
              <DropdownMenuItem destructive>
                <LogOut className="size-4" aria-hidden /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        {slug && (
          <nav
            data-agent="project-nav"
            className={cn(
              "w-56 shrink-0 border-r-2 border-border-strong bg-surface p-3",
              navOpen ? "block" : "hidden lg:block",
            )}
          >
            <p className="mb-2 px-1 font-display text-[0.625rem] font-bold uppercase tracking-[0.2em] text-text-muted">
              ── Navigation ──
            </p>
            <div className="flex flex-col gap-1">
              {navItem(`/p/${slug}`, "Studies", <FlaskConical className="size-4" aria-hidden />)}
              {navItem(`/p/${slug}/platform`, "Platform findings", <Sparkles className="size-4" aria-hidden />)}
              {navItem(`/p/${slug}/members`, "Members", <Users className="size-4" aria-hidden />)}
              {navItem(`/p/${slug}/settings`, "Settings", <Settings className="size-4" aria-hidden />)}
            </div>
          </nav>
        )}
        <main className="min-h-0 flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
