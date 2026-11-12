import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams, useSearchParams } from "react-router-dom";
import {
  ChevronLeft,
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
import { StudyTour } from "@/components/shell/StudyTour";
import { ExportStudy } from "@/components/shell/ExportStudy";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { useApi } from "@/lib/session";
import { useAsync } from "@/lib/useAsync";
import { roleOrNull } from "@/lib/role";
import { cn } from "@/lib/cn";
import { browserNameStore, studyDisplayName } from "@/lib/studyNames";
import { resolveStudyTab } from "@/lib/studyTabs";

/* Study workflow: Setup → Evidence → Plan → Run → Data. Route IDs stay stable for deep links. */

type Tab = "conversation" | "library" | "data" | "planning" | "enrollment";

const TABS: { id: Tab; label: string; icon: typeof Library }[] = [
  { id: "conversation", label: "Setup", icon: MessagesSquare },
  { id: "library", label: "Evidence", icon: Library },
  { id: "planning", label: "Plan", icon: Target },
  { id: "enrollment", label: "Run", icon: UserPlus },
  { id: "data", label: "Data", icon: BarChart3 },
];

export function StudyHome() {
  const { id = "" } = useParams();
  const [planVisited, setPlanVisited] = useState<string | null>(null);
  const api = useApi();
  // Store the active tab in the URL for refresh and shared links.
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const tab: Tab = resolveStudyTab(tabParam);
  useEffect(() => { if (tab === "planning") setPlanVisited(id); }, [tab, id]);
  const setTab = (next: Tab) =>
    setSearchParams(
      (prev) => {
        const params = new URLSearchParams(prev);
        params.set("tab", next);
        return params;
      },
      { replace: true },
    );
  /* A study reached straight from creation carries the researcher's
   * answer to "what do you want to find out?"  -  their first turn, typed
   * before this workspace existed. Router state, not a query param: it is a
   * one-time hand-off, not part of the study's address. */
  const location = useLocation();
  const opening =
    typeof (location.state as { opening?: unknown } | null)?.opening === "string"
      ? ((location.state as { opening: string }).opening)
      : "";

  const [showTour, setShowTour] = useState(false);
  /* Return to the researcher’s selected tab when the walkthrough closes. */
  const tabBeforeTour = useRef<Tab>(tab);

  const openTour = () => {
    tabBeforeTour.current = tab;
    setShowTour(true);
  };

  // The workspace is self-explanatory enough to start without a blocking tour.
  // Keep the walkthrough available from the help button for researchers who ask
  // for it, but never put a first-time modal in front of their study.

  const closeTour = () => {
    setShowTour(false);
    setTab(tabBeforeTour.current);
  };

  const { data: study, loading: studyLoading, error: studyError, reload: reloadStudy } = useAsync(
    () => api.studySummary(id),
    [api, id],
  );
  const currentStudy = study?.id === id ? study : null;
  const roleState = studyLoading || !currentStudy
    ? { status: "loading" as const }
    : { status: "known" as const, role: currentStudy.role };
  const role = roleOrNull(roleState);
  const hasProtocol = currentStudy?.hasProtocol ?? false;

  if (studyError && !currentStudy) {
    return (
      <div className="mx-auto flex max-w-reading flex-col gap-section p-gutter">
        <Notice kind="problem">
          This study isn’t available. <Link to="/home" className="underline">Return to studies</Link>.
        </Notice>
      </div>
    );
  }
  if (!currentStudy) {
    return (
      <div className="mx-auto flex max-w-reading flex-col gap-section p-gutter">
        <p role="status" className="type-body text-text-muted">Loading study…</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Keep study identity and workspace navigation in separate rows. */}
      <header className="border-b border-border bg-surface">
        <div className="flex items-center gap-3 px-4 py-1">
          <div className="flex min-w-0 items-center gap-2 sm:items-baseline">
            <Link
              to="/home"
              aria-label="Back to studies"
              className="touch-link type-label flex shrink-0 items-center gap-1 self-center rounded-control px-1.5 py-1 text-text-muted transition-colors duration-fast hover:bg-zone-9 hover:text-text"
            >
              <ChevronLeft className="size-4" aria-hidden />
              <span className="hidden sm:inline">Studies</span>
            </Link>
            <span className="hidden shrink-0 text-border-strong sm:inline" aria-hidden>
              /
            </span>
            <h1 className="type-control truncate text-text" title={studyDisplayName(browserNameStore(), id)}>
              {studyDisplayName(browserNameStore(), id)}
            </h1>
          </div>

          <div className="ml-auto flex shrink-0 items-center gap-2">
            <ExportStudy studyId={id} />
            <Button
              variant="ghost"
              size="icon"
              aria-label="How this workspace works"
              onClick={openTour}
            >
              <HelpCircle className="size-4" aria-hidden />
            </Button>
          </div>
        </div>

        <nav
          className="flex items-center gap-0.5 overflow-x-auto px-3 sm:gap-1"
          aria-label="Study sections"
        >
          {TABS.map((t) => (
            <button
              type="button"
              key={t.id}
              onClick={() => setTab(t.id)}
              aria-label={t.label}
              aria-current={tab === t.id ? "page" : undefined}
              /* The active section carries the axis mark  -  a rule on the
               * edge the strip is ruled against, plus a cleared ground. It is
               * deliberately not a fill: a fill in this app means "an
               * action you can take", and a tab you are already on is a
               * position, not an action. */
              className={cn(
                "type-control relative flex shrink-0 items-center gap-1.5 rounded-control rounded-b-none border border-b-0 px-2 py-2 transition-all duration-standard sm:px-2.5",
                tab === t.id
                  ? "control-axis axis-under"
                  : "border-transparent text-text-muted hover:bg-zone-9 hover:text-text")}
            >
              <t.icon className="hidden size-4 sm:block" aria-hidden />
              {/* Keep every section named on phones; omit icons to make room. */}
              <span>
                {t.label}
              </span>
            </button>
          ))}
        </nav>
      </header>

      {/* This row clips; it never scrolls itself. Each tab owns its one
       * scroller (a Surface body, or  -  for Library  -  its own split-rail
       * columns), so the workspace never ends up with two scrollbars. */}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {tab === "conversation" && (
          /* min-w-0: without it this flex item takes its width from its widest
           * unshrinkable descendant, so one long citation title pushed the
           * whole workspace column off the side of a phone. A definite width
           * here is also what lets the citation wrap instead of clamp. */
          <div className="min-h-0 min-w-0 flex-1">
            <ConversationView studyId={id} opening={opening} roleState={roleState} onProtocolChanged={reloadStudy} />
          </div>
        )}
        {tab === "library" && (
          <div className="min-h-0 min-w-0 flex-1">
            <LibraryTab key={id} studyId={id} roleState={roleState} />
          </div>
        )}
        {tab === "data" && (
          <div className="min-h-0 min-w-0 flex-1">
            <DataTab studyId={id} role={role} hasProtocol={hasProtocol} />
          </div>
        )}
        <div hidden={tab !== "planning"} className={cn("min-h-0 min-w-0 flex-1", tab !== "planning" && "hidden")}>
          {tab === "planning" || planVisited === id ? (
            <PowerPanel key={id} studyId={id} active={tab === "planning"} role={role} hasProtocol={hasProtocol} />
          ) : null}
        </div>
        {tab === "enrollment" && (
          <div className="min-h-0 min-w-0 flex-1">
            <EnrollmentPanel key={id} studyId={id} role={role} hasProtocol={hasProtocol} />
          </div>
        )}
      </div>

      {showTour && (
        <StudyTour onTab={(t) => setTab(t as Tab)} onClose={closeTour} />
      )}
    </div>
  );
}
