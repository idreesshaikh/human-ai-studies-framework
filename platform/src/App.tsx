import { lazy, Suspense } from "react";
import { Navigate, Outlet, Route, Routes, Link } from "react-router-dom";
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
const TemplateSubmissions = lazy(() =>
  import("@/pages/TemplateSubmissions").then((m) => ({ default: m.TemplateSubmissions })),
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
      <span className="mag mag-3 animate-pulse" />
    </div>
  );
}

function Shell() {
  const { config, needed, hasCredential, resolving } = useAuth();
  // While the credential check is still in flight (clerk-js loading), show
  // neither the app nor the sign-in card — `hasCredential` reads false for
  // that whole window even for an already-signed-in session, and rendering
  // the sign-in screen on its say-so flashes it on every refresh.
  if (resolving) return null;
  if (config.mode !== "none" && (needed || !hasCredential)) return <SignInScreen />;
  return (
    <AppFrame>
      <Outlet />
    </AppFrame>
  );
}

function NotFound() {
  return (
    <div className="mx-auto flex max-w-narrow flex-col items-center gap-3 p-16 text-center">
      <p className="type-subhead text-text">Nothing here</p>
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
          <Route path="/submissions" element={<TemplateSubmissions />} />
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
