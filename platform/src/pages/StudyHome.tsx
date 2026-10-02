import { useRef, useState } from "react";
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
import { StudyTour, markTourSeen } from "@/components/shell/StudyTour";
import { ExportStudy } from "@/components/shell/ExportStudy";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { useApi, useSession } from "@/lib/session";
import { useAsync } from "@/lib/useAsync";
import { resolveRole, roleOrNull } from "@/lib/role";
import { cn } from "@/lib/cn";
import { humanSlug } from "@/lib/slug";

type Tab = "conversation" | "library" | "data" | "planning" | "enrollment";

const TABS: { id: Tab; label: string; icon: typeof Library }[] = [
  { id: "conversation", label: "Setup", icon: MessagesSquare },
  { id: "library", label: "Evidence", icon: Library },
  { id: "planning", label: "Plan", icon: Target },
  { id: "enrollment", label: "Run", icon: UserPlus },
  { id: "data", label: "Data", icon: BarChart3 },
];

export function StudyHome() {
  const { slug = "", id = "" } = useParams();
  const api = useApi();
  const { me, loading: meLoading } = useSession();

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

  const location = useLocation();
  const opening =
    typeof (location.state as { opening?: unknown } | null)?.opening === "string"
      ? ((location.state as { opening: string }).opening)
      : "";

  const [showTour, setShowTour] = useState(false);

  const tabBeforeTour = useRef<Tab>(tab);

  const openTour = () => {
    tabBeforeTour.current = tab;
    setShowTour(true);
  };

  const closeTour = () => {
    markTourSeen();
    setShowTour(false);
    setTab(tabBeforeTour.current);
  };

  const { data: project, loading: projectLoading } = useAsync(
    () => api.projectHome(slug),
    [api, slug],
  );

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

      <header className="border-b border-border bg-surface">
        <div className="flex items-center gap-3 px-4 pb-1.5 pt-2">
          <div className="flex min-w-0 items-baseline gap-2">
            <Link
              to={`/p/${slug}`}
              aria-label={`Back to ${project?.name ?? slug}`}
              className="type-label flex shrink-0 items-center gap-1 self-center rounded-control px-1.5 py-1 text-text-muted transition-colors duration-fast hover:bg-zone-9 hover:text-text"
            >
              <ChevronLeft className="size-4" aria-hidden />

              <span className="hidden max-w-40 truncate sm:inline">
                {project?.name ?? slug}
              </span>
            </Link>
            <span className="hidden shrink-0 text-border-strong sm:inline" aria-hidden>
              /
            </span>

            <h1 className="type-title truncate text-text" title={humanSlug(id)}>
              {humanSlug(id)}
            </h1>
          </div>

          <div className="ml-auto flex shrink-0 items-center gap-2">
            <ExportStudy key={id} studyId={id} />
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

              className={cn(
                "type-control relative flex min-h-11 sm:min-h-0 shrink-0 items-center gap-1.5 rounded-control rounded-b-none border border-b-0 px-2 py-2 transition-all duration-standard sm:px-2.5",
                tab === t.id
                  ? "control-axis axis-under"
                  : "border-transparent text-text-muted hover:bg-zone-9 hover:text-text")}
            >
              <t.icon className="hidden size-4 sm:block" aria-hidden />

              <span>
                {t.label}
              </span>
            </button>
          ))}
        </nav>
      </header>

      <div className="flex min-h-0 flex-1 overflow-hidden">
        {tab === "conversation" && (

          <div className="min-h-0 min-w-0 flex-1">
            <ConversationView key={id} studyId={id} opening={opening} />
          </div>
        )}
        {tab === "library" && (
          <div className="min-h-0 min-w-0 flex-1">
            <LibraryTab key={id} studyId={id} role={role} />
          </div>
        )}
        {tab === "data" && (
          <div className="min-h-0 min-w-0 flex-1">
            <DataTab key={id} studyId={id} />
          </div>
        )}
        {tab === "planning" && (
          <div className="min-h-0 min-w-0 flex-1">
            <PowerPanel key={id} studyId={id} />
          </div>
        )}
        {tab === "enrollment" && (
          <div className="min-h-0 min-w-0 flex-1">
            <EnrollmentPanel key={id} studyId={id} role={role} />
          </div>
        )}
      </div>

      {showTour && (
        <StudyTour onTab={(t) => setTab(t as Tab)} onClose={closeTour} />
      )}
    </div>
  );
}
