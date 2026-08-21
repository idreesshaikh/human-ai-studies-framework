import { useState, useSyncExternalStore } from "react";
import { Link, NavLink, useLocation, useParams } from "react-router-dom";
import {
  Menu,
  Moon,
  Sun,
  LogOut,
  FolderOpen,
  FlaskConical,
  Layers,
  Users,
  Settings,
  PanelLeft,
  PanelLeftClose,
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
import { usePanel, togglePanel } from "@/lib/panels";
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
  const isWorkspace = /^\/p\/[^/]+\/studies\/[^/]+/.test(pathname);
  const navSlug = routeSlug ?? me?.memberships?.[0]?.projectSlug ?? "";
  const theme = useSyncExternalStore(subscribeTheme, getTheme, getTheme);
  const navFolded = usePanel("nav");
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
      // Folded, the rail is icon-only by design (w-[3.25rem]) — but the
      // label itself never stopped rendering, so it just got clipped
      // mid-word ("Pro", "Ten") by the narrow container instead of
      // disappearing. `title` keeps the destination discoverable on hover
      // once the visible text is gone.
      title={navFolded ? label : undefined}
      className={({ isActive }) =>
        cn(
          "type-control flex items-center gap-2 rounded-control border py-2 transition-all duration-standard",
          // The folded rail is 3.25rem (52px) wide with 0.75rem of outer
          // padding on each side (12px), leaving 28px per row — px-2.5's
          // 20px of horizontal padding was sized for the expanded row and
          // left too little room for even the icon alone, which then
          // flex-shrank to a sliver instead of staying square. Folded gets
          // its own tight, centred padding sized to the icon.
          navFolded ? "justify-center px-1.5" : "px-2.5",
          isActive || forceActive
            ? "control-axis"
            : "border-transparent text-text-muted hover:bg-zone-9 hover:text-text",
        )
      }
    >
      <span className="shrink-0">{icon}</span>
      <span className={navFolded ? "sr-only" : undefined}>{label}</span>
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
        <Link
          to="/home"
          className="-ml-2 flex items-center gap-2 rounded-control px-2 py-2 transition-colors duration-fast hover:bg-zone-9"
          aria-label="Phoenix, home"
        >
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
              <button
                className="rounded-chip -m-1.5 p-1.5 transition-colors duration-fast hover:bg-zone-9"
                aria-label="Account"
              >
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
              <DropdownMenuItem asChild>
                <Link to="/settings">
                  <Settings className="size-4" aria-hidden /> Settings
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem destructive onClick={signOut}>
                <LogOut className="size-4" aria-hidden /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {/* One sidebar, always — a researcher switches between projects,
       * templates, members and settings from the same rail everywhere,
       * rather than a top strip outside a project and a side rail inside
       * one. The "Project" group only appears once a project is in scope,
       * since Studies, Members and Settings need a slug to resolve. */}
      <div className="flex min-h-0 flex-1">
        {navOpen && (
          <div
            className="fixed inset-0 z-30 bg-ink/45 lg:hidden"
            onClick={() => setNavOpen(false)}
            aria-hidden
          />
        )}
        <nav
          data-agent="project-nav"
          aria-label="Main"
          className={cn(
            "shrink-0 border-r border-border-strong bg-surface transition-all duration-fast",
            navFolded ? "w-[3.25rem]" : "w-56",
            navOpen
              ? "fixed inset-y-0 left-0 z-40 block pt-[calc(var(--header-h)+0.5rem)] lg:static lg:pt-0"
              : "hidden lg:flex lg:flex-col",
          )}
        >
          <div className="flex flex-1 flex-col gap-1 overflow-auto p-3">
            {navItem(
              "/home",
              "Projects",
              <FolderOpen className="size-4" aria-hidden />,
            )}
            {navItem("/repertoire", "Templates", <Layers className="size-4" aria-hidden />)}

            {hasProjectNav && (
              <>
                {!navFolded && (
                  <p className="type-legend mb-2 mt-4 border-t border-border px-1 pt-4 text-text-muted">
                    Project
                  </p>
                )}
                <div className="flex flex-col gap-1">
                  {navItem(
                    `/p/${navSlug}`,
                    "Studies",
                    <FlaskConical className="size-4" aria-hidden />,
                    {
                      forceActive: pathname.includes("/studies/"),
                    },
                  )}
                  {navItem(`/p/${navSlug}/members`, "Members", <Users className="size-4" aria-hidden />)}
                  {navItem(`/p/${navSlug}/settings`, "Settings", <Settings className="size-4" aria-hidden />)}
                </div>
              </>
            )}
          </div>

          <Button
            variant="ghost"
            size="icon"
            onClick={() => togglePanel("nav")}
            aria-label={navFolded ? "Expand nav" : "Collapse nav"}
            className="shrink-0 rounded-none border-t border-border"
          >
            {navFolded ? <PanelLeft className="size-4" /> : <PanelLeftClose className="size-4" />}
          </Button>
        </nav>
        <main className={cn("min-h-0 flex-1", isWorkspace ? "overflow-hidden" : "overflow-auto")}>
          {children}
        </main>
      </div>
    </div>
  );
}
