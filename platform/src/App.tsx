import { Outlet, Route, Routes, Link } from "react-router-dom";
import { AppFrame } from "@/components/shell/AppFrame";
import { SignInScreen } from "@/components/shell/SignInScreen";
import { useAuth } from "@/lib/auth.tsx";
import { Hero } from "@/pages/Hero";
import { Projects } from "@/pages/Projects";
import { ProjectHome } from "@/pages/ProjectHome";
import { StudyHome } from "@/pages/StudyHome";
import { PlatformFindings } from "@/pages/PlatformFindings";
import { Templates } from "@/pages/Templates";
import { Members } from "@/pages/Members";
import { Settings } from "@/pages/Settings";
import { InviteAccept } from "@/pages/InviteAccept";

function Shell() {
  const { config, needed, hasCredential } = useAuth();
  if (config.mode !== "none" && (needed || !hasCredential)) return <SignInScreen />;
  return (
    <AppFrame>
      <Outlet />
    </AppFrame>
  );
}

function NotFound() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-3 p-16 text-center">
      <p className="font-display text-xl text-text">Nothing here</p>
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
        <Route path="/p/:slug" element={<ProjectHome />} />
        <Route path="/p/:slug/studies/:id" element={<StudyHome />} />
        <Route path="/p/:slug/platform" element={<PlatformFindings />} />
        <Route path="/p/:slug/templates" element={<Templates />} />
        <Route path="/p/:slug/members" element={<Members />} />
        <Route path="/p/:slug/settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
