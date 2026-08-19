import { useState, useSyncExternalStore } from "react";
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
import { getTheme, nextTheme, subscribeTheme } from "@/lib/theme";
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
  // Read the applied theme live: the profile's saved theme lands after this
  // shell mounts, and a mount-time copy would leave the toggle a step behind
  // (its first click then re-applied what was already on screen).
  const theme = useSyncExternalStore(subscribeTheme, getTheme, getTheme);
  const [navOpen, setNavOpen] = useState(false);
  const Icon = THEME_ICON[theme];

  // In hosted (clerk) mode the Clerk session carries the real identity
  // (name, email, avatar); fall back to the server's /me otherwise.
  const accountName = clerkUser?.label ?? me?.displayName ?? "You";
  const accountImg = clerkUser?.imageUrl;

  const cycleTheme = () => {
    // Persist to the identity's profile (FR-OPS-7); the local apply inside
    // setThemePreference is what this button's own label re-reads.
    void setThemePreference(nextTheme(theme));
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
          "type-control flex items-center gap-2 rounded-control border px-2.5 py-1.5 transition-all duration-standard",
          isActive || forceActive
            ? "control-axis"
            : "border-transparent text-text-muted hover:bg-zone-9 hover:text-text",
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
          className="rounded-input border border-transparent p-1 text-text hover:border-border hover:bg-zone-9 lg:hidden"
          onClick={() => setNavOpen((v) => !v)}
          aria-label="Toggle navigation"
        >
          <Menu className="size-5" aria-hidden />
        </button>
        <Link to="/home" className="flex items-center gap-2" aria-label="Phoenix, home">
          <PhoenixMark size={22} />
          <span className="type-subhead tracking-tight text-text">Phoenix</span>
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
                  <span className="block truncate type-caption font-normal text-text-muted">
                    {clerkUser.email}
                  </span>
                )}
                <span className="mt-0.5 block type-caption font-normal text-text-muted">
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

      {/* Outside a project there is no sidebar; the two destinations that
       * exist there — the project list and the repertoire — get a bare
       * strip, so the repertoire is reachable from anywhere a project
       * isn't. */}
      {!hasProjectNav && (
        <nav
          className="flex items-center gap-1 border-b border-border bg-surface px-4 py-1.5"
          aria-label="Main"
        >
          {navItem("/home", "Projects", <FlaskConical className="size-4" aria-hidden />)}
          {navItem("/repertoire", "Templates", <Layers className="size-4" aria-hidden />)}
        </nav>
      )}

      <div className="flex min-h-0 flex-1">
        {hasProjectNav && navOpen && (
          <div
            className="fixed inset-0 z-30 bg-ink/45 lg:hidden"
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
              className="mb-3 flex items-center gap-1.5 px-1 type-caption font-medium text-text-muted transition-colors duration-fast hover:text-accent"
            >
              <ArrowLeft className="size-3.5" aria-hidden />
              All projects
            </NavLink>
            <p className="type-legend mb-2 px-1 text-text-muted">
              Project
            </p>
            <div className="flex flex-col gap-1">
              {navItem(`/p/${navSlug}`, "Studies", <FlaskConical className="size-4" aria-hidden />, {
                forceActive: pathname.includes("/studies/"),
              })}
              {/* The repertoire is global, so it leaves the project sidebar for the
               * one place every page shares — the header nav strip (it also
               * keeps working on the old project-scoped URL via redirect). */}
              {navItem("/repertoire", "Templates", <Layers className="size-4" aria-hidden />)}
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
