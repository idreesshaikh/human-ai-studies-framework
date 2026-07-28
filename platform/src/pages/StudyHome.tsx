import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  ChevronLeft,
  History,
  HelpCircle,
  MessagesSquare,
  Library,
  BarChart3,
  GitBranch,
  UserPlus,
} from "lucide-react";
import { ConversationView } from "@/components/conversation/ConversationView";
import { LibraryTab } from "@/components/library/LibraryTab";
import { DataTab } from "@/components/charts/DataTab";
import { LifecycleTab } from "@/components/charts/LifecycleTab";
import { EnrollmentPanel } from "@/components/enrollment/EnrollmentPanel";
import { AmendmentBanner } from "@/components/conversation/AmendmentBanner";
import { AmendmentHistory } from "@/components/conversation/AmendmentHistory";
import { StudyTour, tourSeen, markTourSeen } from "@/components/shell/StudyTour";
import { ExportStudy } from "@/components/shell/ExportStudy";
import { PresenceChips } from "@/components/shell/PresenceChips";
import { Button } from "@/components/ui/button";
import { evolutionStore, useEvolution } from "@/lib/evolutionStub";
import { useApi, useSession } from "@/lib/session";
import { useAsync } from "@/lib/useAsync";
import { resolveRole, roleOrNull } from "@/lib/role";
import { usePresence } from "@/lib/presence";
import { cn } from "@/lib/cn";

/* A study's workspace. The design conversation is the primary surface; the
 * Library (live paper ingest, citation constellation, grounded assistant),
 * Data (honest metric shapes), and Lifecycle — ride alongside as tabs. Above
 * them all, once the
 * study has ethics approval, its evolution is visible: the amendment banner
 * (paused-until-re-approval when consent-relevant) and the quiet history
 *. */

type Tab = "conversation" | "library" | "data" | "lifecycle" | "enrollment";

const TABS: { id: Tab; label: string; icon: typeof Library }[] = [
  { id: "conversation", label: "Conversation", icon: MessagesSquare },
  { id: "library", label: "Library", icon: Library },
  { id: "data", label: "Data", icon: BarChart3 },
  { id: "lifecycle", label: "Lifecycle", icon: GitBranch },
  { id: "enrollment", label: "Participants", icon: UserPlus },
];

export function StudyHome() {
  const { slug = "", id = "" } = useParams();
  const { amendmentState } = useEvolution();
  const api = useApi();
  const { me, loading: meLoading } = useSession();
  // The active tab lives in the URL (not local state) so a refresh, a
  // shared link, or the browser's back button lands on the same tab
  // instead of always bouncing back to the conversation.
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const tab: Tab = TABS.some((t) => t.id === tabParam) ? (tabParam as Tab) : "conversation";
  const setTab = (next: Tab) =>
    setSearchParams(
      (prev) => {
        const params = new URLSearchParams(prev);
        params.set("tab", next);
        return params;
      },
      { replace: true },
    );
  const [showHistory, setShowHistory] = useState(false);
  const [showTour, setShowTour] = useState(false);

  // First study: run the walkthrough once (persisted). Re-openable via "?".
  useEffect(() => {
    if (!tourSeen()) setShowTour(true);
  }, []);

  const closeTour = () => {
    markTourSeen();
    setShowTour(false);
  };

  // My role in this study's project. The project payload is the fresh source
  // (the session's memberships can be a session old, which is what made the
  // Revoke control on Participants come and go); "still loading" stays
  // distinct from "viewer" — see lib/role.ts.
  const { data: project } = useAsync(() => api.projectHome(slug), [api, slug]);
  const roleState = resolveRole({
    projectMembers: project?.members,
    meSub: me?.sub,
    memberships: me?.memberships,
    meLoading,
    slug,
  });
  const role = roleOrNull(roleState);

  /* Live collaboration: who else is here, and a push when the study changes
   * (consumed by the conversation below). Degrades to nothing when the
   * stream is unavailable. */
  const { viewers, change } = usePresence(id);

  // The seeded evolution state stands in for its study only when the ids line
  // up; a different study is pre-ethics and shows no amendment chrome.
  const evolved = amendmentState.studyId === id ? amendmentState : null;
  const shownState = evolved ?? {
    studyId: id,
    currentVersion: 1,
    ethicsApprovedAt: "",
    pendingReapproval: "",
    amendments: [],
  };

  return (
    <div className="flex h-full flex-col">
      {/* Row 1: where am I, and the actions that apply to the whole study —
       * not to any one tab. Row 2 carries the study's own name, so this row
       * never needs to repeat it. */}
      <div className="flex items-center gap-3 border-b border-border bg-surface px-4 py-1.5 text-sm">
        <Link
          to={`/p/${slug}`}
          className="flex items-center gap-1 text-text-muted hover:text-text"
        >
          <ChevronLeft className="size-4" aria-hidden /> {slug}
        </Link>
        <div className="ml-auto flex items-center gap-2">
          <PresenceChips viewers={viewers} meSub={me?.sub} />
          <ExportStudy studyId={id} />
          {shownState.ethicsApprovedAt && (
            <Button
              variant="ghost"
              size="sm"
              data-agent="amendment-history-toggle"
              onClick={() => setShowHistory((v) => !v)}
            >
              <History className="size-4" aria-hidden />
              {showHistory ? "Hide history" : "History"}
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            aria-label="How this workspace works"
            data-agent="tour-open"
            onClick={() => setShowTour(true)}
          >
            <HelpCircle className="size-4" aria-hidden />
          </Button>
        </div>
      </div>

      {/* Row 2: the study's name, once — and the tabs beside it, since a tab
       * switch stays within this one study. */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-border-strong bg-surface px-4 py-2">
        <h1 className="type-title text-text">{id}</h1>
        <nav
          className="flex items-center gap-0.5 sm:gap-1"
          aria-label="Study sections"
          data-agent="study-tabs"
        >
          {TABS.map((t) => (
            <button
              type="button"
              key={t.id}
              onClick={() => setTab(t.id)}
              aria-label={t.label}
              aria-current={tab === t.id ? "page" : undefined}
              className={cn(
                "flex items-center gap-1.5 rounded-input px-2 sm:px-2.5 py-1 text-sm transition-colors duration-fast",
                tab === t.id
                  ? "bg-accent-soft text-accent"
                  : "text-text-muted hover:bg-accent-soft hover:text-text")}
            >
              <t.icon className="size-4" aria-hidden />
              <span className="hidden sm:inline">{t.label}</span>
            </button>
          ))}
        </nav>
      </div>

      <AmendmentBanner
        state={shownState}
        onRecordReapproval={() => evolutionStore.recordReapproval()}
      />

      {showHistory && (
        <div className="border-b border-border bg-surface-raised p-4">
          <AmendmentHistory amendments={shownState.amendments} />
        </div>
      )}

      {/* This row clips; it never scrolls itself. Each tab owns its one
       * scroller (a Surface body, or — for Library — its own split-rail
       * columns), so the workspace never ends up with two scrollbars. */}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {tab === "conversation" && (
          <div className="min-h-0 flex-1">
            <ConversationView studyId={id} remoteChange={change} />
          </div>
        )}
        {tab === "library" && <LibraryTab studyId={id} />}
        {tab === "data" && <DataTab studyId={id} />}
        {tab === "lifecycle" && (
          <LifecycleTab studyId={id} onGoToConversation={() => setTab("conversation")} />
        )}
        {tab === "enrollment" && <EnrollmentPanel studyId={id} role={role} />}
      </div>

      {showTour && (
        <StudyTour onTab={(t) => setTab(t as Tab)} onClose={closeTour} />
      )}
    </div>
  );
}
