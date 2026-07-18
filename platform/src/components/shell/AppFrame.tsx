import { useState } from "react";
import { Link, NavLink, useParams } from "react-router-dom";
import { Menu, Moon, Sun, Monitor, LogOut, FlaskConical, Users, Settings } from "lucide-react";
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
          "flex items-center gap-2 rounded-input px-2 py-1.5 text-sm transition-colors duration-fast",
          isActive ? "bg-accent-soft text-accent" : "text-text hover:bg-accent-soft",
        )
      }
    >
      {icon}
      {label}
    </NavLink>
  );

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-3 border-b border-border bg-surface px-4 py-2">
        <button
          type="button"
          className="rounded-input p-1 text-text-muted hover:bg-accent-soft lg:hidden"
          onClick={() => setNavOpen((v) => !v)}
          aria-label="Toggle navigation"
        >
          <Menu className="size-5" aria-hidden />
        </button>
        <Link to="/projects" className="font-display text-base text-text">
          Study Designer
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
            className={cn(
              "w-56 shrink-0 border-r border-border bg-surface p-3",
              navOpen ? "block" : "hidden lg:block",
            )}
          >
            <div className="flex flex-col gap-0.5">
              {navItem(`/p/${slug}`, "Studies", <FlaskConical className="size-4" aria-hidden />)}
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
