import { useRef, useState, useSyncExternalStore } from "react";
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

export function AppFrame({ children }: { children: React.ReactNode }) {
  const { me, setThemePreference } = useSession();
  const { signOut, user: clerkUser, hasCredential } = useAuth();

  const signedOut = !hasCredential;
  const { pathname, search } = useLocation();
  const { slug: routeSlug } = useParams<{ slug?: string }>();
  const hasProjectNav = /^\/p\/[^/]+/.test(pathname);
  const isWorkspace = /^\/p\/[^/]+\/studies\/[^/]+/.test(pathname);
  const navSlug = routeSlug ?? me?.memberships?.[0]?.projectSlug ?? "";
  const theme = useSyncExternalStore(subscribeTheme, getTheme, getTheme);
  const navFolded = usePanel("nav");
  const [navOpen, setNavOpen] = useState(false);
  const navToggle = useRef<HTMLButtonElement>(null);

  const showFolded = navFolded && !navOpen;
  const Icon = THEME_ICON[theme];

  const accountName = clerkUser?.label ?? me?.displayName ?? "You";
  const accountImg = clerkUser?.imageUrl;

  const cycleTheme = () => {

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

      title={showFolded ? label : undefined}
      className={({ isActive }) =>
        cn(
          "type-control flex items-center gap-2 rounded-control border py-2 transition-all duration-standard",

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
    <div className="flex h-full flex-col" onKeyDown={(event) => {
      if (event.key === "Escape" && navOpen) {
        setNavOpen(false);
        navToggle.current?.focus();
      }
    }}>
      <header className="flex items-center gap-3 border-b border-border bg-surface px-4 py-2">

        {!signedOut && (
          <button
            ref={navToggle}
            type="button"
            className="rounded-input border border-transparent p-1 text-text hover:border-border hover:bg-zone-9 lg:hidden"
            onClick={() => setNavOpen((v) => !v)}
            aria-label="Toggle navigation"
            aria-expanded={navOpen}
            aria-controls="main-navigation"
          >
            <Menu className="size-5" aria-hidden />
          </button>
        )}

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

      <div className="flex min-h-0 flex-1">
        {navOpen && (
          <div
            className="fixed inset-x-0 bottom-0 top-[var(--header-h)] z-30 bg-ink/45 lg:hidden"
            onClick={() => setNavOpen(false)}
            aria-hidden
          />
        )}

        <nav
          id="main-navigation"
          aria-label="Main"
          hidden={signedOut}
          className={cn(
            "shrink-0 border-r border-border-strong bg-surface transition-all duration-fast",
            showFolded ? "w-[3.25rem]" : "w-56",
            signedOut
              ? "hidden"
              : navOpen
                ? "fixed bottom-0 left-0 top-[var(--header-h)] z-40 block pt-2 lg:static lg:pt-0"
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
