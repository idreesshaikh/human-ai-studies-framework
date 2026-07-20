import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ChevronLeft,
  History,
  MessagesSquare,
  Library,
  BarChart3,
  GitBranch,
  UserPlus,
} from "lucide-react";
import { ConversationView } from "@/components/conversation/ConversationView";
import { AmendmentBanner } from "@/components/conversation/AmendmentBanner";
import { AmendmentHistory } from "@/components/conversation/AmendmentHistory";
import { LibraryTab } from "@/components/library/LibraryTab";
import { DataTab } from "@/components/charts/DataTab";
import { LifecycleTab } from "@/components/charts/LifecycleTab";
import { EnrollmentPanel } from "@/components/enrollment/EnrollmentPanel";
import { Button } from "@/components/ui/button";
import { evolutionStore, useEvolution } from "@/lib/evolutionStub";
import { useSession } from "@/lib/session";
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
  const { me } = useSession();
  const [tab, setTab] = useState<Tab>("conversation");
  const [showHistory, setShowHistory] = useState(false);

  const role = me?.memberships.find((m,) => m.projectSlug === slug)?.role ?? null;

  // The seeded evolution state stands in for its study only when the ids line
  // up; a different study is pre-ethics and shows no amendment chrome.
  const evolved = amendmentState.studyId === id ? amendmentState : null;

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border bg-surface px-4 py-2 text-sm">
        <Link
          to={`/p/${slug}`}
          className="flex items-center gap-1 text-text-muted hover:text-text"
        >
          <ChevronLeft className="size-4" aria-hidden /> {slug}
        </Link>
        <span className="text-text-muted">/</span>
        <span className="font-medium text-text">{id}</span>

        <nav
          className="flex items-center gap-1 sm:ml-4"
          aria-label="Study sections"
          data-agent="study-tabs"
        >
          {TABS.map((t,) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              aria-current={tab === t.id ? "page" : undefined}
              className={cn(
                "flex items-center gap-1.5 rounded-input px-2.5 py-1 text-sm transition-colors duration-fast",
                tab === t.id
                  ? "bg-accent-soft text-accent"
                  : "text-text-muted hover:bg-accent-soft hover:text-text")}
            >
              <t.icon className="size-4" aria-hidden />
              {t.label}
            </button>
          ))}
        </nav>

        {evolved?.ethicsApprovedAt && tab === "conversation" && (
          <Button
            size="sm"
            variant="ghost"
            data-agent="amendment-history-toggle"
            className="ml-auto text-xs text-text-muted"
            onClick={() => setShowHistory((v,) => !v)}
            aria-expanded={showHistory}
          >
            <History className="size-3" aria-hidden />
            {showHistory ? "Hide history" : `History · v${evolved.currentVersion}`}
          </Button>
        )}
      </div>

      {evolved && (
        <AmendmentBanner
          state={evolved}
          onRecordReapproval={() => evolutionStore.recordReapproval()}
        />
      )}

      <div className="flex min-h-0 flex-1">
        {tab === "conversation" && (
          <>
            <div className={cn("min-h-0 flex-1", showHistory && "hidden lg:block")}>
              <ConversationView studyId={id} />
            </div>
            {showHistory && evolved && (
              <aside className="w-full overflow-auto border-l border-border bg-bg p-4 lg:w-96">
                <h2 className="mb-3 font-display text-lg text-text">
                  Amendment history
                </h2>
                <AmendmentHistory amendments={evolved.amendments} />
              </aside>
            )}
          </>
        )}
        {tab === "library" && <LibraryTab studyId={id} />}
        {tab === "data" && <DataTab studyId={id} />}
        {tab === "lifecycle" && <LifecycleTab studyId={id} />}
        {tab === "enrollment" && <EnrollmentPanel studyId={id} role={role} />}
      </div>
    </div>
  );
}
