import { useState } from "react";
import { Download, Loader2, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { studyApi, OfflineError } from "@/lib/studyApi";

/* Getting the study *out* (FR-PROT-7, FR-CONV-6, FR-AGENT-5, FR-ANA-6). Four
 * things a researcher actually needs to hand to someone else, or to
 * themselves at the platform's own boundary:
 *
 * - the replication kit  -  protocol, joined dataset, regenerated report and
 *   pinned versions, byte-reproducible, the thing a reviewer reruns;
 * - the elicitation record  -  the decision chain from idea to specification;
 * - the starter notebook  -  a loaded, documented dataframe with every
 *   planned recipe imported and never run: where the platform's own scope
 *   ends and the researcher's analysis begins. */
export function ExportStudy({ studyId }: { studyId: string }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(
    kind: "kit" | "record" | "notebook",
    download: () => Promise<void>,
  ) {
    setBusy(kind);
    setError(null);
    try {
      await download();
      setDone(kind);
      setTimeout(() => setDone(null), 2000);
    } catch (e) {
      setError(
        e instanceof OfflineError
          ? "Start the middleware to export this study."
          : e instanceof Error
            ? e.message
            : "Couldn't export this study.",
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" aria-label="Share and export" data-agent="study-export">
            {busy ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : done ? (
              <Check className="size-4 text-grounded" aria-hidden />
            ) : (
              <Download className="size-4" aria-hidden />
            )}
            <span className="hidden sm:inline">Share</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="max-w-72">
          <DropdownMenuItem
            data-agent="export-replication-kit"
            onSelect={() =>
              void run("kit", () => studyApi.downloadReplicationKit(studyId))
            }
          >
            <div className="flex flex-col gap-0.5">
              <span>Replication kit</span>
              <span className="type-caption text-text-muted">
                Protocol, dataset, report and pinned versions: byte-identical
                on every export.
              </span>
            </div>
          </DropdownMenuItem>
          <DropdownMenuItem
            data-agent="export-elicitation-record"
            onSelect={() =>
              void run("record", () => studyApi.downloadElicitationRecord(studyId))
            }
          >
            <div className="flex flex-col gap-0.5">
              <span>Elicitation record</span>
              <span className="type-caption text-text-muted">
                The decision chain: turns, moves and their grounding,
                compilations, approvals.
              </span>
            </div>
          </DropdownMenuItem>
          <DropdownMenuItem
            data-agent="export-notebook"
            onSelect={() =>
              void run("notebook", () => studyApi.downloadNotebook(studyId))
            }
          >
            <div className="flex flex-col gap-0.5">
              <span>Starter notebook</span>
              <span className="type-caption text-text-muted">
                Loaded, documented dataset and every planned recipe imported,
                nothing run yet. Your analysis starts at the last cell.
              </span>
            </div>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      {error && (
        <span className="max-w-64 truncate type-caption text-critical" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
