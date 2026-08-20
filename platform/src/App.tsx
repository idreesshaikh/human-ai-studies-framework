import { Navigate, Outlet, Route, Routes, Link } from "react-router-dom";
import { AppFrame } from "@/components/shell/AppFrame";
import { SignInScreen } from "@/components/shell/SignInScreen";
import { useAuth } from "@/lib/auth.tsx";
import { Hero } from "@/pages/Hero";
import { Projects } from "@/pages/Projects";
import { ProjectHome } from "@/pages/ProjectHome";
import { StudyHome } from "@/pages/StudyHome";
import { Templates } from "@/pages/Templates";
import { Members } from "@/pages/Members";
import { AccountSettings } from "@/pages/AccountSettings";
import { ProjectSettings } from "@/pages/ProjectSettings";
import { InviteAccept } from "@/pages/InviteAccept";

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
    <Routes>
      <Route path="/" element={<Hero />} />
      <Route path="/invitations/:token" element={<InviteAccept />} />
      <Route element={<Shell />}>
        {/* Not "/projects" — that's the backend's GET /projects API path
            (app.py); same-path SPA route + API route can't coexist on a
            hard navigation (refresh, bookmark, the sign-in/sign-out
            location.reload()), which bypasses the SPA shell entirely and
            shows the raw API response instead of this page. */}
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
  );
}
