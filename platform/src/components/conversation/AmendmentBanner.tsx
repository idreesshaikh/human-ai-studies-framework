import { Lock, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import type { AmendmentState } from "@/lib/types";

/* The amendment banner.
 *
 * Precise register, deliberately unanimated — this is a consent surface, on the
 * never-animate list (§7). It states the study's revision plainly, and when a
 * consent-relevant amendment awaits ethics re-approval it says so in plain
 * language ("new sessions paused until re-approval") with a lock glyph. No
 * drama: evolution is normal. */
export function AmendmentBanner({
  state,
  onRecordReapproval,
}: {
  state: AmendmentState;
  onRecordReapproval?: () => void;
}) {
  // Pre-ethics there is nothing to say — amendments are ordinary compiles.
  if (!state.ethicsApprovedAt) return null;

  const paused = Boolean(state.pendingReapproval);

  return (
    <div
      data-agent="amendment-banner"
      data-agent-paused={paused}
      role="status"
      className={cn(
        "flex items-start gap-3 border-b px-4 py-3 type-body",
        paused
          ? "border-unsourced bg-unsourced-soft text-text"
          : "border-border bg-surface text-text-muted")}
    >
      {paused ? (
        <Lock className="mt-0.5 size-4 shrink-0 text-unsourced" aria-hidden />
      ) : (
        <ShieldCheck className="mt-0.5 size-4 shrink-0 text-grounded" aria-hidden />
      )}
      <div className="flex-1">
        {paused ? (
          <>
            <p className="font-medium text-text">
              New sessions are paused until ethics re-approval.
            </p>
            <p className="mt-0.5">
              A consent-relevant amendment took this study to revision{" "}
              {state.currentVersion}. Already-collected data and any session in
              progress are unaffected; only new data-collection sessions wait
              for the updated approval.
            </p>
          </>
        ) : (
          <p>
            Under ethics approval since{" "}
            {state.ethicsApprovedAt.slice(0, 10)}; now on revision{" "}
            {state.currentVersion}. Changes are version-visible amendments.
          </p>
        )}
      </div>
      {paused && onRecordReapproval && (
        <Button
          size="sm"
          variant="subtle"
          data-agent="amendment-reapprove"
          onClick={onRecordReapproval}
        >
          I've uploaded the re-approval
        </Button>
      )}
    </div>
  );
}
