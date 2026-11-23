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

/* Export the replication kit, decision record, or starter notebook from the same study. */
export function ExportStudy({ studyId }: { studyId: string }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(
    kind: "kit" | "record" | "notebook" | "data" | "card",
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
          <Button variant="ghost" size="sm" aria-label="Export study">
            {busy ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : done ? (
              <Check className="size-4 text-grounded" aria-hidden />
            ) : (
              <Download className="size-4" aria-hidden />
            )}
            <span className="hidden sm:inline">Export</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="max-w-72">
          <DropdownMenuItem
            onSelect={() => void run("data", () => studyApi.downloadDataBundle(studyId))}
          >
            <div className="flex flex-col gap-0.5">
              <span>Data (.zip)</span>
              <span className="type-caption text-text-muted">
                Event CSVs, joined timeline and data dictionary. Synthetic rows excluded.
              </span>
            </div>
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() =>
              void run("card", () => studyApi.downloadDesignCard(studyId))
            }
          >
            <div className="flex flex-col gap-0.5">
              <span>Design card (.md)</span>
              <span className="type-caption text-text-muted">
                The recorded study design in Markdown.
              </span>
            </div>
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() =>
              void run("kit", () => studyApi.downloadReplicationKit(studyId))
            }
          >
            <div className="flex flex-col gap-0.5">
              <span>Replication kit</span>
              <span className="type-caption text-text-muted">
                Protocol, data, report and pinned versions. Reproducible on every export.
              </span>
            </div>
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() =>
              void run("record", () => studyApi.downloadElicitationRecord(studyId))
            }
          >
            <div className="flex flex-col gap-0.5">
              <span>Elicitation record</span>
              <span className="type-caption text-text-muted">
                Conversation, decisions, sources, compilations and approvals.
              </span>
            </div>
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() =>
              void run("notebook", () => studyApi.downloadNotebook(studyId))
            }
          >
            <div className="flex flex-col gap-0.5">
              <span>Starter notebook</span>
              <span className="type-caption text-text-muted">
                Dataset and planned recipes ready for your analysis. Nothing run yet.
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
