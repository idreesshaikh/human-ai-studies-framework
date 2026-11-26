import { useState, type ReactNode } from "react";
import { X } from "lucide-react";
import { Popover, PopoverClose, PopoverContent, PopoverTitle, PopoverTrigger } from "@ui-sdk/react/popover";
import { useApi } from "@/lib/session";
import { hasRole, type Role } from "@/lib/capabilities";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { cn } from "@/lib/cn";
import { publicPaperReference } from "@/lib/paperReference";

interface CatalogEntry {
  instrument: string;
  path: string[];
  label: string;
  description: string;
  grounding: { ref?: string; source?: string; unsourced?: boolean };
  currentValue: unknown;
}

/* A capture instrument chip that opens its toggle beside itself: ui-sdk
 * anchors the popover to the chip, moves focus in, and Escape or an outside
 * press closes it and returns focus to the chip. */
export function TogglePopover({
  studyId,
  entry,
  role,
  onToggle,
  className,
  title,
  children,
}: {
  studyId: string;
  entry: CatalogEntry;
  role: Role | null;
  onToggle: () => void;
  className?: string;
  title?: string;
  children: ReactNode;
}) {
  const api = useApi();
  const [applying, setApplying] = useState(false);
  const [result, setResult] = useState<{
    error?: string;
  } | null>(null);
  const canToggle = hasRole(role, "toggle_capture");

  const currentEnabled =
    typeof entry.currentValue === "boolean"
      ? entry.currentValue
      : entry.currentValue !== null && entry.currentValue !== undefined;

  const handleToggle = async () => {
    if (!canToggle) return;
    setApplying(true);
    setResult(null);
    try {
      const res = await api.applyToggle(studyId, {
        instrument: entry.instrument,
        path: entry.path,
        value: !currentEnabled,
        rationale: `Toggled ${entry.label} from console`,
      });
      setResult(res);
      onToggle();
    } catch (err: unknown) {
      setResult({ error: err instanceof Error ? err.message : "Toggle failed" });
    } finally {
      setApplying(false);
    }
  };

  return (
    <Popover onOpenChange={(open) => { if (open) setResult(null); }}>
      <PopoverTrigger title={title} className={className}>
        {children}
      </PopoverTrigger>
      <PopoverContent side="bottom" align="start" sideOffset={6} collisionPadding={8} className="popup-panel w-72 p-3">
        <div className="mb-2 flex items-center justify-between">
          <PopoverTitle className="type-body text-text">{entry.label}</PopoverTitle>
          <PopoverClose render={<Button type="button" variant="ghost" size="icon-sm" aria-label="Close" />}>
            <X aria-hidden />
          </PopoverClose>
        </div>
        <p className="mb-2 type-note text-text-muted">{entry.description}</p>
        <div className="mb-3 flex items-center gap-2">
          <span className="type-caption text-text-muted">Current:</span>
          <span className={cn("type-quantity",
            currentEnabled ? "text-accent" : "text-text-muted")}>
            {JSON.stringify(currentEnabled)}
          </span>
        </div>
        {entry.grounding && (
          <div className="mb-3">
            {"unsourced" in entry.grounding && entry.grounding.unsourced ? (
              <Badge variant="unsourced">
                Uncited: researcher's judgment
              </Badge>
            ) : (
              (() => {
                const citation = publicPaperReference(entry.grounding?.ref ?? "");
                return citation ? (
                  <Badge variant="grounded" title={`Source: ${entry.grounding.source}`}>
                    {citation}
                  </Badge>
                ) : null;
              })()
            )}
          </div>
        )}
        {result === null ? (
          <Button
            className="w-full"
            size="sm"
            onClick={handleToggle}
            disabled={applying || !canToggle}
          >
            {applying ? "Applying…" : `Turn ${currentEnabled ? "off" : "on"}`}
          </Button>
        ) : result.error ? (
          <Notice kind="problem">{result.error}</Notice>
        ) : (
          <p className="type-caption text-accent">Applied.</p>
        )}
      </PopoverContent>
    </Popover>
  );
}
