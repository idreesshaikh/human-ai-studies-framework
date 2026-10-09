import { lazy, Suspense } from "react";
import { Navigate, Outlet, Route, Routes, Link, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { PhoenixMark } from "@/components/brand/PhoenixMark";
import { useRouteTitle } from "@/lib/useDocumentTitle";
import { AppFrame } from "@/components/shell/AppFrame";
import { SignInScreen } from "@/components/shell/SignInScreen";
import { useAuth } from "@/lib/auth.tsx";
import { useSession } from "@/lib/session";

/* Route-level code splitting. The marketing hero and the study workspace (the
 * two heaviest subtrees  -  the workspace pulls the whole conversation, charts,
 * constellation, and enrollment stack) load only when the researcher actually
 * opens them, instead of riding in the first payload everyone pays for. The
 * chrome (AppFrame + auth) stays eager: it is on every signed-in screen and
 * must paint immediately. */

const Projects = lazy(() =>
  import("@/pages/Projects").then((m) => ({ default: m.Projects })),
);
const ProjectHome = lazy(() =>
  import("@/pages/ProjectHome").then((m) => ({ default: m.ProjectHome })),
);
const StudyHome = lazy(() =>
  import("@/pages/StudyHome").then((m) => ({ default: m.StudyHome })),
);
const Templates = lazy(() =>
  import("@/pages/Templates").then((m) => ({ default: m.Templates })),
);
const Members = lazy(() =>
  import("@/pages/Members").then((m) => ({ default: m.Members })),
);
const AccountSettings = lazy(() =>
  import("@/pages/AccountSettings").then((m) => ({ default: m.AccountSettings })),
);
const ProjectSettings = lazy(() =>
  import("@/pages/ProjectSettings").then((m) => ({ default: m.ProjectSettings })),
);
const InviteAccept = lazy(() =>
  import("@/pages/InviteAccept").then((m) => ({ default: m.InviteAccept })),
);

/* A route's fallback while its chunk loads. Chunks are small, so this rarely
 * paints for more than a frame; when it does, it is a single muted mark on the
 * page's own ground rather than a spinner. */
function PageFallback() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center" aria-hidden>
      <span className="size-2.5 animate-pulse rounded-dot bg-text-muted" />
    </div>
  );
}

function Home() {
  const { isSolo, me, loading } = useSession();
  if (isSolo && loading) return <PageFallback />;
  const slug = me?.memberships[0]?.projectSlug;
  return isSolo && slug ? <Navigate to={`/p/${slug}`} replace /> : <Projects />;
}

/* Templates are publicly readable; creating a study still requires an identity. */
const PUBLIC_PATHS = new Set(["/repertoire"]);

function Shell() {
  const { config, needed, hasCredential, resolving } = useAuth();
  const { pathname } = useLocation();
  // While the credential check is still in flight (clerk-js loading), show
  // neither the app nor the sign-in card  -  `hasCredential` reads false for
  // that whole window even for an already-signed-in session, and rendering
  // the sign-in screen on its say-so flashes it on every refresh.
  if (resolving) return null;
  if (
    config.mode !== "none" &&
    (needed || !hasCredential) &&
    !PUBLIC_PATHS.has(pathname)
  ) {
    return <SignInScreen />;
  }
  return (
    <AppFrame>
      <Outlet />
    </AppFrame>
  );
}

function NotFound() {
  const { hasCredential } = useAuth();
  useRouteTitle();
  return (
    <div className="flex min-h-screen flex-col bg-surface">
      <header className="flex items-center border-b border-border px-4 py-2">
        <Link
          to="/"
          className="-ml-2 flex items-center gap-2 rounded-control px-2 py-2 transition-colors duration-fast hover:bg-zone-9"
          aria-label="StudyLoop, home"
        >
          <PhoenixMark size={22} />
          <span className="hidden type-subhead tracking-tight text-text sm:inline">StudyLoop</span>
        </Link>
      </header>
      <main className="mx-auto flex w-full max-w-narrow flex-1 flex-col items-center justify-center gap-4 p-gutter text-center">
        {/* The one h1: a mistyped or dead URL is where a reader is most
          * likely to be lost, so the page names itself. */}
        <h1 className="type-title text-text">Page not found</h1>
        <p className="type-body text-pretty text-text-muted">
          That page does not exist, or you may not have access to it.
        </p>
        <Button asChild>
          <Link to={hasCredential ? "/home" : "/"}>
            {hasCredential ? "Go to Projects" : "Back to the start"}
          </Link>
        </Button>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route path="/" element={<Navigate to="/home" replace />} />
        {/* A real address for signing in, so a public page has somewhere to
            send someone that can carry them back afterwards (?next=). Outside
            `Shell`: the whole point is that it renders without a credential,
            and once there is one it forwards rather than framing an app the
            visitor has already left. */}
        <Route path="/signin" element={<SignInScreen />} />
        <Route path="/invitations/:token" element={<InviteAccept />} />
        <Route element={<Shell />}>
          {/* Not "/projects"  -  that's the backend's GET /projects API path
              (app.py); same-path SPA route + API route can't coexist on a
              hard navigation (refresh, bookmark, the sign-in/sign-out
              location.reload()), which bypasses the SPA shell entirely and
              shows the raw API response instead of this page. */}
          <Route path="/start" element={<Navigate to="/home" replace />} />
          <Route path="/home" element={<Home />} />
          <Route path="/settings" element={<AccountSettings />} />
          {/* Templates are project-agnostic (FR-TPL): one global browse,
              not one per project. Not "/templates"  -  that's the backend's
              GET /templates API path (app.py), and the same-path collision
              would show raw JSON on a hard navigation. The old project-scoped
              URL keeps working. */}
          <Route path="/repertoire" element={<Templates />} />
          <Route path="/p/:slug" element={<ProjectHome />} />
          <Route path="/p/:slug/studies/:id" element={<StudyHome />} />
          <Route
            path="/p/:slug/templates"
            element={<Navigate to="/repertoire" replace />}
          />
          <Route path="/p/:slug/members" element={<Members />} />
          <Route path="/p/:slug/settings" element={<ProjectSettings />} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
