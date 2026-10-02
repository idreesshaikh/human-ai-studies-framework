import { lazy, Suspense } from "react";
import { Navigate, Outlet, Route, Routes, Link, useLocation } from "react-router-dom";
import { AppFrame } from "@/components/shell/AppFrame";
import { SignInScreen } from "@/components/shell/SignInScreen";
import { useAuth } from "@/lib/auth.tsx";

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

function PageFallback() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center" aria-hidden>
      <span className="size-2.5 animate-pulse rounded-dot bg-text-muted" />
    </div>
  );
}

const PUBLIC_PATHS = new Set(["/repertoire"]);

function Shell() {
  const { config, needed, hasCredential, resolving } = useAuth();
  const { pathname } = useLocation();

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
    <main className="mx-auto flex max-w-narrow flex-col items-center gap-3 p-16 text-center">

      <h1 className="type-subhead text-text">Nothing here</h1>
      <Link to="/" className="text-accent hover:underline">
        Back to the start
      </Link>
    </main>
  );
}

export default function App() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route path="/" element={<Hero />} />

        <Route path="/signin" element={<SignInScreen />} />
        <Route path="/invitations/:token" element={<InviteAccept />} />
        <Route element={<Shell />}>

          <Route path="/start" element={<QuickStart />} />
          <Route path="/home" element={<Projects />} />
          <Route path="/settings" element={<AccountSettings />} />

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
