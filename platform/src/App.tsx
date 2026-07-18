import { Outlet, Route, Routes, Link } from "react-router-dom";
import { AppFrame } from "@/components/shell/AppFrame";
import { Hero } from "@/pages/Hero";
import { DemoProject } from "@/pages/DemoProject";
import { Projects } from "@/pages/Projects";
import { ProjectHome } from "@/pages/ProjectHome";
import { StudyHome } from "@/pages/StudyHome";
import { Members } from "@/pages/Members";
import { Settings } from "@/pages/Settings";
import { InviteAccept } from "@/pages/InviteAccept";

/* Layout for the signed-in routes: the app chrome around a routed page. */
function Shell() {
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
      {/* Public / standalone */}
      <Route path="/" element={<Hero />} />
      <Route path="/demo" element={<DemoProject />} />
      <Route path="/invitations/:token" element={<InviteAccept />} />
      {/* Signed-in shell */}
      <Route element={<Shell />}>
        <Route path="/projects" element={<Projects />} />
        <Route path="/p/:slug" element={<ProjectHome />} />
        <Route path="/p/:slug/studies/:id" element={<StudyHome />} />
        <Route path="/p/:slug/members" element={<Members />} />
        <Route path="/p/:slug/settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
