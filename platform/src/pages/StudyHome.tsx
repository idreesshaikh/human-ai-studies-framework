import { useEffect, useState } from "react";
import { Link, useLocation, useParams, useSearchParams } from "react-router-dom";
import {
  ChevronLeft,
  History,
  HelpCircle,
  MessagesSquare,
  Library,
  BarChart3,
  Target,
  UserPlus,
} from "lucide-react";
import { ConversationView } from "@/components/conversation/ConversationView";
import { LibraryTab } from "@/components/library/LibraryTab";
import { DataTab } from "@/components/charts/DataTab";
import { PowerPanel } from "@/components/charts/PowerPanel";
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

/* A study's workspace, and the whole arc the platform supports: design the
 * study in conversation, then set it up. The design conversation is the
 * primary surface; the Library (live paper ingest, citation constellation,
 * grounded assistant), Data (honest metric shapes) and Participants ride
 * alongside it as tabs.
 *
 * There is deliberately no lifecycle board. Tracking a study across seven
 * phases was ceremony no researcher worked through, and its ethics gate
 * blocked the one thing this workspace exists to do - it made a designed,
 * compiled study impossible to actually set up. Approval is the
 * university's to grant; what the platform owes a participant is an
 * unmissable account of what will be captured, which the consent statement
 * at pairing gives them. */

type Tab = "conversation" | "library" | "data" | "planning" | "enrollment";

const TABS: { id: Tab; label: string; icon: typeof Library }[] = [
  { id: "conversation", label: "Conversation", icon: MessagesSquare },
  { id: "library", label: "Library", icon: Library },
  { id: "data", label: "Data", icon: BarChart3 },
  { id: "planning", label: "Planning", icon: Target },
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
  /* A study reached straight from project creation carries the researcher's
   * answer to "what do you want to find out?" — their first turn, typed
   * before this workspace existed. Router state, not a query param: it is a
   * one-time hand-off, not part of the study's address. */
  const location = useLocation();
  const opening =
    typeof (location.state as { opening?: unknown } | null)?.opening === "string"
      ? ((location.state as { opening: string }).opening)
      : "";

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
      {/* ONE header row: project link + study name + tabs + actions */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface px-4 py-2">
        <Link
          to={`/p/${slug}`}
          className="type-label flex items-center gap-1 text-text-muted hover:text-text"
        >
          <ChevronLeft className="size-4" aria-hidden /> {slug}
        </Link>

        <h1 className="type-title text-text">{id}</h1>

        <nav
          className="ml-auto flex items-center gap-0.5 sm:gap-1"
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
              /* The active section carries the axis mark — a rule on the
               * edge the strip is ruled against, plus a cleared ground. It is
               * the same "you are here" form the project sidebar uses, and it
               * is deliberately not a fill: a fill in this app means "an
               * action you can take", and a tab you are already on is a
               * position, not an action. */
              className={cn(
                "type-control relative flex items-center gap-1.5 rounded-control border px-2 sm:px-2.5 py-1.5 transition-all duration-standard",
                tab === t.id
                  ? "control-axis axis-under"
                  : "border-transparent text-text-muted hover:bg-zone-9 hover:text-text")}
            >
              <t.icon className="size-4" aria-hidden />
              {/* Narrow screens can't carry five labels, but five bare glyphs
                * tell a stranger nothing and a phone has no hover to fall back
                * on. The section you are in says its name; the rest are marks
                * you can reach — which is also what the struck mark means. */}
              <span className={cn(tab === t.id ? "inline" : "hidden sm:inline")}>
                {t.label}
              </span>
            </button>
          ))}
        </nav>

        <div className="flex items-center gap-2">
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
          /* min-w-0: without it this flex item takes its width from its widest
           * unshrinkable descendant, so one long citation title pushed the
           * whole workspace column off the side of a phone. A definite width
           * here is also what lets the citation wrap instead of clamp. */
          <div className="min-h-0 min-w-0 flex-1">
            <ConversationView studyId={id} remoteChange={change} opening={opening} />
          </div>
        )}
        {tab === "library" && <LibraryTab studyId={id} />}
        {tab === "data" && <DataTab studyId={id} />}
        {tab === "planning" && <PowerPanel studyId={id} />}
        {tab === "enrollment" && <EnrollmentPanel studyId={id} role={role} />}
      </div>

      {showTour && (
        <StudyTour onTab={(t) => setTab(t as Tab)} onClose={closeTour} />
      )}
    </div>
  );
}
