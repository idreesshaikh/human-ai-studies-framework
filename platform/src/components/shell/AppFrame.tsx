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
import { signInHref } from "@/lib/returnTo";

const THEME_ICON = { light: Sun, dark: Moon };

/* The signed-in chrome: a project-scoped sidebar + a top bar (breadcrumb,
 * project switcher, theme, account). Collapses to a toggle on narrow
 * viewports. */
export function AppFrame({ children }: { children: React.ReactNode }) {
  const { me, setThemePreference } = useSession();
  const { signOut, user: clerkUser, hasCredential } = useAuth();
  /* No identity, and this deployment wants one. `hasCredential` already reads
   * true in `mode: "none"` (a local deployment has no accounts to be signed
   * out of), so this is only ever true on a public route reached by someone
   * who has not signed in. */
  const signedOut = !hasCredential;
  const { pathname, search } = useLocation();
  const { slug: routeSlug } = useParams<{ slug?: string }>();
  const hasProjectNav = /^\/p\/[^/]+/.test(pathname);
  const isWorkspace = /^\/p\/[^/]+\/studies\/[^/]+/.test(pathname);
  const navSlug = routeSlug ?? me?.memberships?.[0]?.projectSlug ?? "";
  const theme = useSyncExternalStore(subscribeTheme, getTheme, getTheme);
  const navFolded = usePanel("nav");
  const [navOpen, setNavOpen] = useState(false);
  /* What the rail actually renders as, which is NOT simply `navFolded`.
   *
   * `navFolded` is a per-device preference (panels.ts) with no notion of
   * viewport  -  it is set by folding the desktop rail and stays set the next
   * time this same browser opens a narrow window, because it has no reason
   * to know that window is a phone. The mobile drawer (`navOpen`) shares its
   * markup with the desktop rail, so honoring `navFolded` there collapsed
   * every label to a 52px column of bare glyphs  -  and did it inside an
   * overlay whose own fold button had just been removed as meaningless in
   * that context (see below), leaving no way back to full width short of
   * clearing localStorage.
   *
   * The mobile drawer already has its show/hide control, the hamburger, so
   * it never folds: full labels, full width, always, while `navOpen` is
   * true. */
  const showFolded = navFolded && !navOpen;
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
      // Folded, the rail is icon-only by design (w-[3.25rem])  -  but the
      // label itself never stopped rendering, so it just got clipped
      // mid-word ("Pro", "Ten") by the narrow container instead of
      // disappearing. `title` keeps the destination discoverable on hover
      // once the visible text is gone.
      title={showFolded ? label : undefined}
      className={({ isActive }) =>
        cn(
          "type-control flex items-center gap-2 rounded-control border py-2 transition-all duration-standard",
          // The folded rail is 3.25rem (52px) wide with 0.75rem of outer
          // padding on each side (12px), leaving 28px per row  -  px-2.5's
          // 20px of horizontal padding was sized for the expanded row and
          // left too little room for even the icon alone, which then
          // flex-shrank to a sliver instead of staying square. Folded gets
          // its own tight, centred padding sized to the icon.
          showFolded ? "justify-center px-1.5" : "px-2.5",
          isActive || forceActive
            ? "control-axis"
            : "border-transparent text-text-muted hover:bg-zone-9 hover:text-text",
        )
      }
    >
      <span className="shrink-0">{icon}</span>
      <span className={showFolded ? "sr-only" : undefined}>{label}</span>
    </NavLink>
  );

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-3 border-b border-border bg-surface px-4 py-2">
        {/* Nothing to open when the rail is not rendered. */}
        {!signedOut && (
          <button
            type="button"
            className="rounded-input border border-transparent p-1 text-text hover:border-border hover:bg-zone-9 lg:hidden"
            onClick={() => setNavOpen((v) => !v)}
            aria-label="Toggle navigation"
          >
            <Menu className="size-5" aria-hidden />
          </button>
        )}
        {/* Signed out, "home" is the public front, not the projects list the
          * visitor cannot see  -  the wordmark was the one control on a public
          * page guaranteed to dead-end at the sign-in gate. */}
        <Link
          to={signedOut ? "/" : "/home"}
          className="-ml-2 flex items-center gap-2 rounded-control px-2 py-2 transition-colors duration-fast hover:bg-zone-9"
          aria-label="Phoenix, home"
        >
          <PhoenixMark size={22} />
          <span className="type-subhead tracking-tight text-text">Phoenix</span>
        </Link>
        <div className="ml-auto flex items-center gap-2">
          {!signedOut && <ProjectSwitcher memberships={me?.memberships ?? []} />}
          <Button variant="ghost" size="icon" onClick={cycleTheme} aria-label={`Theme: ${theme}`}>
            <Icon aria-hidden />
          </Button>
          {/* Signed out, there is no account to open a menu about and no
            * project to switch between  -  an avatar reading "You" over a
            * "Sign out" item would be describing a session that does not
            * exist. The one thing a visitor on a public page can do with
            * their identity is acquire one. */}
          {signedOut ? (
            <Button asChild size="sm" variant="outline">
              <Link to={signInHref(pathname + search)}>Sign in</Link>
            </Button>
          ) : (
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
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link to="/settings">
                  <Settings className="size-4" aria-hidden /> Account settings
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem destructive onClick={signOut}>
                <LogOut className="size-4" aria-hidden /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          )}
        </div>
      </header>

      {/* One sidebar, always  -  a researcher switches between projects,
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
        {/* Signed out, the rail would hold one reachable destination and two
          * that bounce straight back to the sign-in gate. A nav whose items
          * mostly refuse is worse than no nav: the public page keeps the
          * header (mark, theme, Sign in) and gets its whole width. */}
        <nav
          data-agent="project-nav"
          aria-label="Main"
          hidden={signedOut}
          className={cn(
            "shrink-0 border-r border-border-strong bg-surface transition-all duration-fast",
            showFolded ? "w-[3.25rem]" : "w-56",
            signedOut
              ? "hidden"
              : navOpen
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
            {!hasProjectNav &&
              navItem("/settings", "Account settings", <Settings className="size-4" aria-hidden />)}

            {hasProjectNav && (
              <>
                {!showFolded && (
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
                  {navItem(
                    `/p/${navSlug}/settings`,
                    "Project settings",
                    <Settings className="size-4" aria-hidden />,
                  )}
                </div>
              </>
            )}
          </div>

          {/* The rail's footer, not a floating square in the corner. Expanded,
            * it says what it does; folded, the icon carries it and the name
            * moves to the accessible label. As a bare `size-icon` button it
            * painted as one unexplained 44px glyph pinned to the bottom-left
            * of the window, visually detached from the rail it belongs to.
            *
            * `hidden lg:flex`: this `<nav>` is shared between the desktop
            * static rail and the mobile slide-over (`navOpen`), and folding
            * is a desktop-only idea  -  the overlay already has a show/hide
            * control, the hamburger, so a second one that shrinks it to an
            * icon strip *while it stays open* has no coherent job to do.
            * Rendered anyway, tapping it inside the mobile drawer collapsed
            * every label to a 52px column of bare glyphs with no visible way
            * back  -  the button that had just done that was now unlabelled
            * too. Below `lg` the control simply is not there. */}
          <button
            type="button"
            onClick={() => togglePanel("nav")}
            aria-label={navFolded ? "Expand navigation" : "Collapse navigation"}
            aria-expanded={!navFolded}
            className={cn(
              "hidden shrink-0 items-center gap-2 border-t border-border py-3 type-control text-text-muted transition-colors duration-fast hover:bg-zone-9 hover:text-text lg:flex",
              navFolded ? "justify-center px-1.5" : "px-4",
            )}
          >
            {navFolded ? (
              <PanelLeft className="size-4" aria-hidden />
            ) : (
              <PanelLeftClose className="size-4" aria-hidden />
            )}
            {!navFolded && <span>Collapse</span>}
          </button>
        </nav>
        <main className={cn("min-h-0 flex-1", isWorkspace ? "overflow-hidden" : "overflow-auto")}>
          {children}
        </main>
      </div>
    </div>
  );
}
