import { useState } from "react";
import { Link, NavLink, useLocation, useParams } from "react-router-dom";
import {
  Menu,
  Moon,
  Sun,
  LogOut,
  FlaskConical,
  Layers,
  Users,
  Settings,
  ArrowLeft,
} from "lucide-react";
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
import { PhoenixMark } from "@/components/brand/PhoenixMark";
import { ProjectSwitcher } from "./ProjectSwitcher";
import { useSession } from "@/lib/session";
import { useAuth } from "@/lib/auth.tsx";
import { getTheme, nextTheme, type Theme } from "@/lib/theme";
import { cn } from "@/lib/cn";

const THEME_ICON = { light: Sun, dark: Moon };

/* The signed-in chrome: a project-scoped sidebar + a top bar (breadcrumb,
 * project switcher, theme, account). Collapses to a toggle on narrow
 * viewports. */
export function AppFrame({ children }: { children: React.ReactNode }) {
  const { me, setThemePreference } = useSession();
  const { signOut, user: clerkUser, config } = useAuth();
  const { pathname } = useLocation();
  const { slug: routeSlug } = useParams<{ slug?: string }>();
  const hasProjectNav = /^\/p\/[^/]+/.test(pathname);
  // A study workspace clips here and lets its own tab own the one scroller
  // (StudyHome + its Surfaces); every other route still scrolls in the
  // shell. Never both, or a tall page grows two scrollbars.
  const isWorkspace = /^\/p\/[^/]+\/studies\/[^/]+/.test(pathname);
  // Use the slug from the current route; fall back to the first membership
  // only on pages that have no slug param (shouldn't happen when hasProjectNav
  // is true, but keeps the type-system happy).
  const navSlug = routeSlug ?? me?.memberships?.[0]?.projectSlug ?? "";
  const [theme, setTheme] = useState<Theme>(() => getTheme());
  const [navOpen, setNavOpen] = useState(false);
  const Icon = THEME_ICON[theme];

  // In hosted (clerk) mode the Clerk session carries the real identity
  // (name, email, avatar); fall back to the server's /me otherwise.
  const accountName = clerkUser?.label ?? me?.displayName ?? "You";
  const accountImg = clerkUser?.imageUrl;

  const cycleTheme = () => {
    const next = nextTheme(theme);
    setTheme(next);
    // Persist to the identity's profile (FR-OPS-7); local apply is internal.
    void setThemePreference(next);
  };

  const navItem = (
    to: string,
    label: string,
    icon: React.ReactNode,
    { end = true, forceActive = false }: { end?: boolean; forceActive?: boolean } = {},
  ) => (
    <NavLink
      to={to}
      end={end}
      onClick={() => setNavOpen(false)}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-2 rounded-input border px-2.5 py-1.5 font-mono text-sm font-medium tracking-tight transition-colors duration-fast",
          isActive || forceActive
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
      <header className="flex items-center gap-3 border-b border-border-strong bg-surface px-4 py-2">
        <button
          type="button"
          className="rounded-input border border-transparent p-1 text-text hover:border-border-strong hover:bg-accent-soft lg:hidden"
          onClick={() => setNavOpen((v) => !v)}
          aria-label="Toggle navigation"
        >
          <Menu className="size-5" aria-hidden />
        </button>
        <Link to="/home" className="flex items-center gap-2" aria-label="Phoenix, home">
          <PhoenixMark size={22} />
          <span className="type-subhead text-text">Phoenix</span>
        </Link>
        <div className="ml-auto flex items-center gap-2">
          <ProjectSwitcher memberships={me?.memberships ?? []} />
          <Button variant="ghost" size="icon" onClick={cycleTheme} aria-label={`Theme: ${theme}`}>
            <Icon aria-hidden />
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="rounded-chip" aria-label="Account">
                <Avatar name={accountName} src={accountImg} />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>
                <span className="block truncate">{accountName}</span>
                {clerkUser?.email && (
                  <span className="block truncate text-xs font-normal text-text-muted">
                    {clerkUser.email}
                  </span>
                )}
                <span className="mt-0.5 block text-xs font-normal text-text-muted">
                  {me?.mode ?? config.mode ?? "local"}
                </span>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link to="/home">All projects</Link>
              </DropdownMenuItem>
              <DropdownMenuItem destructive onClick={signOut}>
                <LogOut className="size-4" aria-hidden /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        {hasProjectNav && navOpen && (
          <div
            className="fixed inset-0 z-30 bg-black/40 lg:hidden"
            onClick={() => setNavOpen(false)}
            aria-hidden
          />
        )}
        {hasProjectNav && (
          <nav
            data-agent="project-nav"
            className={cn(
              "w-56 shrink-0 border-r border-border-strong bg-surface p-3",
              navOpen
                ? "fixed inset-y-0 left-0 z-40 block pt-[calc(var(--header-h)+0.5rem)] lg:static lg:pt-0"
                : "hidden lg:block",
            )}
          >
            <NavLink
              to="/home"
              onClick={() => setNavOpen(false)}
              className="mb-3 flex items-center gap-1.5 px-1 text-xs font-medium text-text-muted transition-colors duration-fast hover:text-accent"
            >
              <ArrowLeft className="size-3.5" aria-hidden />
              All projects
            </NavLink>
            <p className="type-eyebrow mb-2 px-1 text-text-muted">
              Project
            </p>
            <div className="flex flex-col gap-1">
              {navItem(`/p/${navSlug}`, "Studies", <FlaskConical className="size-4" aria-hidden />, {
                forceActive: pathname.includes("/studies/"),
              })}
              {navItem(`/p/${navSlug}/templates`, "Templates", <Layers className="size-4" aria-hidden />)}
              {navItem(`/p/${navSlug}/members`, "Members", <Users className="size-4" aria-hidden />)}
              {navItem(`/p/${navSlug}/settings`, "Settings", <Settings className="size-4" aria-hidden />)}
            </div>
          </nav>
        )}
        <main className={cn("min-h-0 flex-1", isWorkspace ? "overflow-hidden" : "overflow-auto")}>
          {children}
        </main>
      </div>
    </div>
  );
}
