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
import { StudyTour, tourSeen, markTourSeen } from "@/components/shell/StudyTour";
import { ExportStudy } from "@/components/shell/ExportStudy";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { useApi, useSession } from "@/lib/session";
import { useAsync } from "@/lib/useAsync";
import { resolveRole, roleOrNull } from "@/lib/role";
import { cn } from "@/lib/cn";
import { humanSlug } from "@/lib/slug";

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
   * answer to "what do you want to find out?"  -  their first turn, typed
   * before this workspace existed. Router state, not a query param: it is a
   * one-time hand-off, not part of the study's address. */
  const location = useLocation();
  const opening =
    typeof (location.state as { opening?: unknown } | null)?.opening === "string"
      ? ((location.state as { opening: string }).opening)
      : "";

  const [showTour, setShowTour] = useState(false);
  /* The tab the researcher was on when the tour opened.
   *
   * The tour BORROWS the workspace to demonstrate it  -  each step switches the
   * tab to whatever it is describing  -  and it has to give it back. It did
   * not: the last step is about Participants, so every first-run walkthrough
   * ended by abandoning the researcher on the Participants tab of a study
   * with no protocol, looking at "Nobody can be enrolled yet". The one screen
   * whose whole job is to get someone started left them on the only tab where
   * nothing can be done yet, and the first tab it had just spent two steps
   * explaining was two clicks away again.
   *
   * Restoring the remembered tab is right in both directions: a first run
   * opens on Conversation and returns there, and a researcher who reopens the
   * tour with "?" from Planning is put back on Planning rather than being
   * dumped somewhere they never chose. */
  const tabBeforeTour = useRef<Tab>(tab);

  const openTour = () => {
    tabBeforeTour.current = tab;
    setShowTour(true);
  };

  // First study: run the walkthrough once (persisted). Re-openable via "?".
  useEffect(() => {
    if (!tourSeen()) {
      tabBeforeTour.current = tab;
      setShowTour(true);
    }
    // Deliberately mount-only: this is the "first study ever" trigger, not a
    // reaction to the tab changing (which the tour itself does, six times).
  }, []);

  const closeTour = () => {
    markTourSeen();
    setShowTour(false);
    setTab(tabBeforeTour.current);
  };

  // My role in this study's project. The project payload is the fresh source
  // (the session's memberships can be a session old, which is what made the
  // Revoke control on Participants come and go); "still loading" stays
  // distinct from "member"  -  see lib/role.ts.
  const { data: project, loading: projectLoading } = useAsync(
    () => api.projectHome(slug),
    [api, slug],
  );
  /* In local (non-Clerk) dev mode, the server's per-study authorization
   * check waves through any unknown study id  -  deliberately, since local
   * mode has no real accounts to check against  -  so a stale bookmark, a
   * typo'd id, or a deleted study all render a fully interactive, empty
   * workspace with no sign anything is wrong (verified live: every
   * conversation/compile call the page fires returns 200 for a study that
   * was never created). `project.studies` is the same list the sidebar
   * and Studies tab already read from, so cross-checking against it here
   * is a real "does this study exist in THIS project" answer, not a guess. */
  const studyExists =
    projectLoading || !project ? null : project.studies.some((st) => st.id === id);
  const roleState = resolveRole({
    projectMembers: project?.members,
    meSub: me?.sub,
    memberships: me?.memberships,
    meLoading,
    slug,
  });
  const role = roleOrNull(roleState);

  if (studyExists === false) {
    return (
      <div className="mx-auto flex max-w-reading flex-col gap-section p-gutter">
        <Notice kind="problem">
          Study &quot;{id}&quot; doesn&apos;t exist in {slug}.{" "}
          <Link to={`/p/${slug}`} className="underline">
            Back to studies
          </Link>
          .
        </Notice>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* TWO ruled tiers, not one row that wraps. The identity of the study
       * (where it lives, what it is called, what you can do to the whole of
       * it) is one kind of thing; which part of it you are looking at is
       * another. Packed into a single row these four groups could not fit a
       * 1440px window, so `flex-wrap` silently dropped the actions onto a
       * second line under the title  -  a two-tier header by accident, aligned
       * to nothing.
       *
       * Tiering it deliberately also puts the tab strip on the workspace's
       * real spine: the axis mark under the active section now lands on the
       * rule that divides chrome from work, instead of floating 20px above
       * an unrelated border. */}
      <header className="border-b border-border bg-surface">
        <div className="flex items-center gap-3 px-4 pb-1.5 pt-2">
          <div className="flex min-w-0 items-baseline gap-2">
            <Link
              to={`/p/${slug}`}
              aria-label={`Back to ${project?.name ?? slug}`}
              className="type-label flex shrink-0 items-center gap-1 self-center rounded-control px-1.5 py-1 text-text-muted transition-colors duration-fast hover:bg-zone-9 hover:text-text"
            >
              <ChevronLeft className="size-4" aria-hidden />
              {/* A project's slug is its address, not its name. The name is
               * already on the payload this page loads for the role check.
               *
               * Below `sm` the name gives its width back to the study's own
               * title, which is the thing this screen is about  -  carrying
               * both truncated a 390px header to "Trust cali…". The chevron
               * still goes back, and the link keeps its name above. */}
              <span className="hidden max-w-40 truncate sm:inline">
                {project?.name ?? slug}
              </span>
            </Link>
            <span className="hidden shrink-0 text-border-strong sm:inline" aria-hidden>
              /
            </span>
            {/* A study id IS its slug in the schema, so the header was
             * printing `trust-calibration-in-ai-code-review` at 28px as the
             * study's name. Same string, read as words. */}
            <h1 className="type-title truncate text-text" title={humanSlug(id)}>
              {humanSlug(id)}
            </h1>
          </div>

          <div className="ml-auto flex shrink-0 items-center gap-2">
            <ExportStudy studyId={id} />
            <Button
              variant="ghost"
              size="icon"
              aria-label="How this workspace works"
              data-agent="tour-open"
              onClick={openTour}
            >
              <HelpCircle className="size-4" aria-hidden />
            </Button>
          </div>
        </div>

        <nav
          className="flex items-center gap-0.5 overflow-x-auto px-3 sm:gap-1"
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
              /* The active section carries the axis mark  -  a rule on the
               * edge the strip is ruled against, plus a cleared ground. It is
               * the same "you are here" form the project sidebar uses, and it
               * is deliberately not a fill: a fill in this app means "an
               * action you can take", and a tab you are already on is a
               * position, not an action. */
              className={cn(
                "type-control relative flex shrink-0 items-center gap-1.5 rounded-control rounded-b-none border border-b-0 px-2 py-2 transition-all duration-standard sm:px-2.5",
                tab === t.id
                  ? "control-axis axis-under"
                  : "border-transparent text-text-muted hover:bg-zone-9 hover:text-text")}
            >
              <t.icon className="size-4" aria-hidden />
              {/* Narrow screens can't carry five labels, but five bare glyphs
                * tell a stranger nothing and a phone has no hover to fall back
                * on. The section you are in says its name; the rest are marks
                * you can reach  -  which is also what the struck mark means. */}
              <span className={cn(tab === t.id ? "inline" : "hidden sm:inline")}>
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
            <ConversationView studyId={id} opening={opening} />
          </div>
        )}
        {tab === "library" && (
          <div className="min-h-0 min-w-0 flex-1">
            <LibraryTab studyId={id} />
          </div>
        )}
        {tab === "data" && (
          <div className="min-h-0 min-w-0 flex-1">
            <DataTab studyId={id} />
          </div>
        )}
        {tab === "planning" && (
          <div className="min-h-0 min-w-0 flex-1">
            <PowerPanel studyId={id} />
          </div>
        )}
        {tab === "enrollment" && (
          <div className="min-h-0 min-w-0 flex-1">
            <EnrollmentPanel studyId={id} role={role} />
          </div>
        )}
      </div>

      {showTour && (
        <StudyTour onTab={(t) => setTab(t as Tab)} onClose={closeTour} />
      )}
    </div>
  );
}
