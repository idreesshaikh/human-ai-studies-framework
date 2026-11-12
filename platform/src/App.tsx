import { lazy, Suspense } from "react";
import { Navigate, Outlet, Route, Routes, Link, useLocation, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { PhoenixMark } from "@/components/brand/PhoenixMark";
import { useRouteTitle } from "@/lib/useDocumentTitle";
import { AppFrame } from "@/components/shell/AppFrame";
import { SignInScreen } from "@/components/shell/SignInScreen";
import { useAuth } from "@/lib/auth.tsx";

/* Route-level code splitting. The template collection and study workspace (the
 * two heaviest subtrees  -  the workspace pulls the whole conversation, charts,
 * constellation, and enrollment stack) load only when the researcher actually
 * opens them, instead of riding in the first payload everyone pays for. The
 * chrome (AppFrame + auth) stays eager: it is on every signed-in screen and
 * must paint immediately. */

const Studies = lazy(() =>
  import("@/pages/Studies").then((m) => ({ default: m.Studies })),
);
const StudyHome = lazy(() =>
  import("@/pages/StudyHome").then((m) => ({ default: m.StudyHome })),
);
const Templates = lazy(() =>
  import("@/pages/Templates").then((m) => ({ default: m.Templates })),
);
const AccountSettings = lazy(() =>
  import("@/pages/AccountSettings").then((m) => ({ default: m.AccountSettings })),
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

function LegacyStudyRedirect() {
  const { id = "" } = useParams();
  const { search } = useLocation();
  return <Navigate to={`/studies/${encodeURIComponent(id)}${search}`} replace />;
}

/* Templates are publicly readable; creating a study still requires an identity. */
const PUBLIC_PATHS = new Set(["/repertoire"]);

function Shell() {
  const { config, needed, hasCredential, resolving } = useAuth();
  const { pathname } = useLocation();
  // While the server's sign-in mode is still being fetched, show
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
            {hasCredential ? "Go to Studies" : "Back to the start"}
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
        <Route path="/invitations/:token" element={<Navigate to="/home" replace />} />
        <Route element={<Shell />}>
          <Route path="/start" element={<Navigate to="/home" replace />} />
          <Route path="/home" element={<Studies />} />
          <Route path="/settings" element={<AccountSettings />} />
          {/* The template collection is shared by every study. */}
          <Route path="/repertoire" element={<Templates />} />
          <Route path="/studies/:id" element={<StudyHome />} />
          {/* Old links keep opening their study, while containers stay out of
              the researcher-facing navigation. */}
          <Route path="/p/:slug" element={<Navigate to="/home" replace />} />
          <Route path="/p/:slug/studies/:id" element={<LegacyStudyRedirect />} />
          <Route
            path="/p/:slug/templates"
            element={<Navigate to="/repertoire" replace />}
          />
          <Route path="/p/:slug/members" element={<Navigate to="/home" replace />} />
          <Route path="/p/:slug/settings" element={<Navigate to="/settings" replace />} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
