import { lazy, Suspense } from "react";
import { Navigate, Outlet, Route, Routes, Link, useLocation } from "react-router-dom";
import { AppFrame } from "@/components/shell/AppFrame";
import { SignInScreen } from "@/components/shell/SignInScreen";
import { useAuth } from "@/lib/auth.tsx";

/* Route-level code splitting. The marketing hero and the study workspace (the
 * two heaviest subtrees — the workspace pulls the whole conversation, charts,
 * constellation, and enrollment stack) load only when the researcher actually
 * opens them, instead of riding in the first payload everyone pays for. The
 * chrome (AppFrame + auth) stays eager: it is on every signed-in screen and
 * must paint immediately. */

const Hero = lazy(() => import("@/pages/Hero").then((m) => ({ default: m.Hero })));
const QuickStart = lazy(() =>
  import("@/pages/QuickStart").then((m) => ({ default: m.QuickStart })),
);
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

/* Routes the shell renders to anyone, credential or not.
 *
 * The repertoire is a public browse and the middleware already treats it as
 * one: `/templates/repertoire`, `/templates/merge`, `/templates/from-paper`
 * and `/corpus/search` all carry no auth dependency and answer 200 to an
 * unauthenticated request. The gate was the SPA's own invention, and it made
 * the page contradict its own first line — "No project needed to browse" —
 * by demanding an account before a visitor saw a single design shape.
 *
 * Public means readable, not writable. Every action that creates something
 * still needs an identity, and each one says so where it is (CreateStudyFrom,
 * the describe-a-study panel). */
const PUBLIC_PATHS = new Set(["/repertoire"]);

function Shell() {
  const { config, needed, hasCredential, resolving } = useAuth();
  const { pathname } = useLocation();
  // While the credential check is still in flight (clerk-js loading), show
  // neither the app nor the sign-in card — `hasCredential` reads false for
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
  return (
    <div className="mx-auto flex max-w-narrow flex-col items-center gap-3 p-16 text-center">
      {/* An `h1`, not a styled paragraph. This was the one page in the app
        * with no heading at all, so the one place a reader is most likely to
        * be lost — a mistyped or dead URL — announced nothing to a screen
        * reader and gave a document-outline reader an empty page. */}
      <h1 className="type-subhead text-text">Nothing here</h1>
      <Link to="/" className="text-accent hover:underline">
        Back to the start
      </Link>
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route path="/" element={<Hero />} />
        {/* A real address for signing in, so a public page has somewhere to
            send someone that can carry them back afterwards (?next=). Outside
            `Shell`: the whole point is that it renders without a credential,
            and once there is one it forwards rather than framing an app the
            visitor has already left. */}
        <Route path="/signin" element={<SignInScreen />} />
        <Route path="/invitations/:token" element={<InviteAccept />} />
        <Route element={<Shell />}>
          {/* Not "/projects" — that's the backend's GET /projects API path
              (app.py); same-path SPA route + API route can't coexist on a
              hard navigation (refresh, bookmark, the sign-in/sign-out
              location.reload()), which bypasses the SPA shell entirely and
              shows the raw API response instead of this page. */}
          <Route path="/start" element={<QuickStart />} />
          <Route path="/home" element={<Projects />} />
          <Route path="/settings" element={<AccountSettings />} />
          {/* The repertoire is project-agnostic (FR-TPL): one global browse,
              not one per project. Not "/templates" — that's the backend's
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
