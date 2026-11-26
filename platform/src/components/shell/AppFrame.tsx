import { useEffect, useState, useSyncExternalStore } from "react";
import { Link, NavLink, useLocation, useMatch } from "react-router-dom";
import {
  Menu,
  Moon,
  Sun,
  LogOut,
  FlaskConical,
  Layers,
  Settings,
  PanelLeft,
  PanelLeftClose,
} from "lucide-react";
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
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
import { useSession } from "@/lib/session";
import { useAuth } from "@/lib/auth.tsx";
import { getTheme, nextTheme, subscribeTheme, themeToggleLabel } from "@/lib/theme";
import { usePanel, togglePanel } from "@/lib/panels";
import { cn } from "@/lib/cn";
import { signInHref } from "@/lib/returnTo";
import { useRouteTitle } from "@/lib/useDocumentTitle";
import { browserNameStore, studyDisplayName, studyNamesVersion, subscribeStudyNames } from "@/lib/studyNames";

const THEME_ICON = { light: Sun, dark: Moon };

/* One row spec for every control in the rail: the nav links and the fold
 * button share height, radius, type and hover so none reads as a different
 * kind of thing. */
const NAV_ITEM =
  "type-control flex items-center gap-2 rounded-control border py-2 transition-colors duration-standard";
const NAV_ITEM_IDLE = "border-transparent text-text-muted hover:bg-zone-9 hover:text-text";

/* The signed-in shell keeps the study list and shared settings in one rail. */
export function AppFrame({ children }: { children: React.ReactNode }) {
  const { me, setThemePreference } = useSession();
  const { signOut, hasCredential } = useAuth();
  // No-auth mode already reports a credential.
  const signedOut = !hasCredential;
  const { pathname, search } = useLocation();
  const studyId = useMatch("/studies/:id")?.params.id;
  const theme = useSyncExternalStore(subscribeTheme, getTheme, getTheme);
  /* Re-read the study's name once its summary has remembered it. */
  useSyncExternalStore(subscribeStudyNames, studyNamesVersion, studyNamesVersion);
  const navFolded = usePanel("nav");
  const [navOpen, setNavOpen] = useState(false);
  useEffect(() => {
    const desktop = window.matchMedia("(min-width: 64rem)");
    const closeOnDesktop = () => {
      if (desktop.matches) setNavOpen(false);
    };
    desktop.addEventListener("change", closeOnDesktop);
    return () => desktop.removeEventListener("change", closeOnDesktop);
  }, []);
  useRouteTitle({
    studyName: studyId
      ? studyDisplayName(browserNameStore(), studyId)
      : undefined,
  });
  const Icon = THEME_ICON[theme];

  const accountName = me?.displayName ?? "You";

  const cycleTheme = () => {
    // Persist to the identity's profile (FR-OPS-7); the local apply inside
    // setThemePreference is what this button's own label re-reads.
    void setThemePreference(nextTheme(theme));
  };

  const navItem = (
    to: string,
    label: string,
    icon: React.ReactNode,
    folded: boolean,
    forceActive = false,
  ) => (
    <NavLink
      to={to}
      end
      onClick={() => setNavOpen(false)}
      title={folded ? label : undefined}
      className={({ isActive }) =>
        cn(
          NAV_ITEM,
          folded ? "justify-center gap-0 px-1.5" : "gap-2 px-2.5",
          isActive || forceActive
            ? "control-axis"
            : NAV_ITEM_IDLE,
        )
      }
    >
      <span className="shrink-0">{icon}</span>
      <span
        className={cn(
          "min-w-0 truncate transition-opacity duration-fast",
          folded ? "w-0 overflow-hidden opacity-0" : "opacity-100",
        )}
      >
        {label}
      </span>
    </NavLink>
  );

  const navigationItems = (folded: boolean) => (
    <>
      {navItem("/home", "Studies", <FlaskConical className="size-4" aria-hidden />, folded, !!studyId)}
      {navItem("/repertoire", "Templates", <Layers className="size-4" aria-hidden />, folded)}
      {navItem("/settings", "Account settings", <Settings className="size-4" aria-hidden />, folded)}
    </>
  );

  return (
    <div className="flex h-full flex-col">
      <a href="#workspace-content" className="sr-only rounded-control bg-surface p-3 type-control text-accent focus:not-sr-only focus:fixed focus:z-50">
        Skip to main content
      </a>
      <header className="flex items-center gap-2 border-b border-border bg-surface px-3 py-2 sm:gap-3 sm:px-4">
        {!signedOut && (
          <Dialog open={navOpen} onOpenChange={setNavOpen}>
            <DialogTrigger className="header-control lg:hidden" aria-label="Toggle navigation" aria-expanded={navOpen}>
              <Menu className="size-5" aria-hidden />
            </DialogTrigger>
            <DialogContent variant="drawer" className="p-3">
              <DialogTitle className="px-2 py-3 type-subhead text-text">Navigation</DialogTitle>
              <nav aria-label="Main" className="mt-2 flex flex-col gap-1 p-1">
                {navigationItems(false)}
              </nav>
            </DialogContent>
          </Dialog>
        )}
        {/* Signed out, "home" is the public front, not the studies list the
          * visitor cannot see  -  the wordmark was the one control on a public
          * page guaranteed to dead-end at the sign-in gate. */}
        <Link
          to={signedOut ? "/" : "/home"}
          className="-ml-2 flex items-center gap-2 rounded-control px-2 py-2 transition-colors duration-fast hover:bg-zone-9"
          aria-label="StudyLoop, home"
        >
          <PhoenixMark size={22} />
          <span className="hidden type-subhead tracking-tight text-text sm:inline">StudyLoop</span>
        </Link>
        <div className="ml-auto flex items-center gap-2">
          <button type="button" className="header-control" onClick={cycleTheme} aria-label={themeToggleLabel(theme)}>
            <Icon aria-hidden />
          </button>
          {/* Signed out, there is no account menu to open. The one thing a
            * visitor on a public page can do with their identity is acquire
            * one. */}
          {signedOut ? (
            <Link to={signInHref(pathname + search)} className="header-control px-3 text-text">
              Sign in
            </Link>
          ) : (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="header-control px-0"
                aria-label="Account"
              >
                <Avatar name={accountName} />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>
                <span className="block truncate">{accountName}</span>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link to="/settings">
                  <Settings className="size-4" aria-hidden /> Account settings
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem destructive onSelect={signOut}>
                <LogOut className="size-4" aria-hidden /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          )}
        </div>
      </header>

      {/* Studies, templates and account preferences are the three destinations. */}
      <div className="flex min-h-0 flex-1">
        <nav
          aria-label="Main"
          hidden={signedOut}
          className={cn(
            "hidden shrink-0 border-r border-border-strong bg-surface transition-[width] duration-standard ease-out",
            !signedOut && "lg:flex lg:flex-col",
            navFolded ? "w-[3.25rem]" : "w-56",
          )}
        >
          <div className="flex flex-1 flex-col gap-1 overflow-auto p-3">
            {navigationItems(navFolded)}
          </div>

          {/* Folding applies to the desktop rail; the mobile drawer has its own toggle. */}
          <div className="hidden shrink-0 border-t border-border p-3 lg:block">
          <button
            type="button"
            onClick={() => togglePanel("nav")}
            aria-label={navFolded ? "Expand navigation" : "Collapse navigation"}
            aria-expanded={!navFolded}
            className={cn(
              NAV_ITEM,
              NAV_ITEM_IDLE,
              "w-full",
              navFolded ? "justify-center px-1.5" : "px-2.5",
            )}
          >
            {navFolded ? (
              <PanelLeft className="size-4" aria-hidden />
            ) : (
              <PanelLeftClose className="size-4" aria-hidden />
            )}
            {!navFolded && <span>Collapse</span>}
          </button>
          </div>
        </nav>
        <main id="workspace-content" tabIndex={-1} className={cn("min-h-0 flex-1", studyId ? "overflow-hidden" : "overflow-auto")}>
          {children}
        </main>
      </div>
    </div>
  );
}
