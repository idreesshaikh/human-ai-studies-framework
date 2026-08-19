import { useState } from "react";
import { useApi } from "@/lib/session";
import { hasRole, type Role } from "@/lib/capabilities";
import { cn } from "@/lib/cn";

interface CatalogEntry {
  instrument: string;
  path: string[];
  label: string;
  description: string;
  grounding: { ref?: string; source?: string; unsourced?: boolean };
  currentValue: unknown;
}

export function TogglePopover({
  studyId,
  entry,
  role,
  onToggle,
  onClose,
}: {
  studyId: string;
  entry: CatalogEntry;
  role: Role | null;
  onToggle: () => void;
  onClose: () => void;
}) {
  const api = useApi();
  const [applying, setApplying] = useState(false);
  const [result, setResult] = useState<{
    requiresReapproval?: boolean;
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
    <div className="absolute left-0 top-full z-50 mt-1 w-72 rounded-card border border-border bg-surface p-3 shadow-lifted"
      data-agent="toggle-popover">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-display type-body text-text">{entry.label}</span>
        <button onClick={onClose}
          className="rounded-sm px-1 text-text-muted hover:text-text"
          aria-label="Close">✕</button>
      </div>
      <p className="mb-2 type-caption text-text-muted">{entry.description}</p>
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
            <span className="rounded-sm bg-warning/10 px-1.5 py-0.5 type-caption text-warning"
              data-agent-status="unsourced">
              Uncited: researcher's judgment
            </span>
          ) : (
            <span className="rounded-sm bg-accent/10 px-1.5 py-0.5 type-quantity text-accent"
              title={`Source: ${entry.grounding.source}`}>
              {entry.grounding.ref}
            </span>
          )}
        </div>
      )}
      {result === null ? (
        <button onClick={handleToggle} disabled={applying || !canToggle}
          className={cn("w-full rounded-input border px-3 py-1.5 type-caption font-medium transition-colors",
            canToggle
              ? "border-accent text-accent hover:bg-accent hover:text-accent-contrast"
              : "border-border text-text-muted cursor-not-allowed")}>
          {applying ? "Applying..." : `Turn ${currentEnabled ? "off" : "on"}`}
        </button>
      ) : result.error ? (
        <p className="type-caption text-danger">{result.error}</p>
      ) : result.requiresReapproval ? (
        <div className="rounded-sm border border-warning bg-warning/5 p-2">
          <p className="type-caption font-medium text-warning">Amendment pending</p>
          <p className="mt-0.5 type-caption text-text-muted">
            This change affects what is captured. New sessions are paused until
            you re-upload ethics approval.
          </p>
        </div>
      ) : (
        <p className="type-caption text-accent">Applied. No re-approval needed.</p>
      )}
    </div>
  );
}
