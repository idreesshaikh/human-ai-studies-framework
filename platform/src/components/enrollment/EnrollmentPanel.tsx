import { useCallback, useEffect, useRef, useState } from "react";
import { Copy, Check, ExternalLink } from "lucide-react";
import { useApi } from "@/lib/session";
import { hasRole, type Role } from "@/lib/capabilities";
import type { EnrollmentTokenView, ToggleCatalogEntry } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { MintDialog } from "./MintDialog";
import { TogglePopover } from "./TogglePopover";
import { cn } from "@/lib/cn";

const STATUS_STYLE: Record<string, string> = {
  unredeemed: "text-text-muted",
  paired: "text-accent",
  streaming: "text-accent",
  revoked: "text-unsourced line-through",
};

const EXTENSION_URI_AUTHORITY = "hpi-research.cognitive-overlay";

function vscodeDeepLink(connectionString: string): string {
  return `vscode://${EXTENSION_URI_AUTHORITY}/pair?c=${encodeURIComponent(connectionString)}`;
}

/* The study's enrollment surface (FR-DASH-10): mint pairing links, see who has
 * paired / is streaming with live polling, revoke, and toggle per-metric
 * capture (FR-DASH-11). Lives inside the study workspace — running a study is
 * part of the study. */
export function EnrollmentPanel({
  studyId,
  role,
}: {
  studyId: string;
  role: Role | null;
}) {
  const api = useApi();
  const [rows, setRows] = useState<EnrollmentTokenView[]>([]);
  const [catalog, setCatalog] = useState<ToggleCatalogEntry[]>([]);
  const [popoverEntry, setPopoverEntry] = useState<ToggleCatalogEntry | null>(
    null,
  );
  const [copied, setCopied] = useState<string | null>(null);
  const canMint = hasRole(role, "mint_token");
  const canToggle = hasRole(role, "toggle_capture");

  const load = useCallback(() => {
    void api.listEnrollmentTokens(studyId).then(setRows);
    void api.toggleCatalog(studyId).then(setCatalog);
  }, [studyId, api]);
  useEffect(load, [load]);

  // Live polling: refresh statuses every 15s while the panel is mounted.
  const pollRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  useEffect(() => {
    pollRef.current = setInterval(load, 15_000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [load]);

  const copy = (text: string, id: string) => {
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(id);
      setTimeout(() => setCopied(null), 2000);
    });
  };

  return (
    /* Composed like the Lifecycle tab: one centred column with a titled
     * section and its explanatory line, rather than a full-bleed table. The
     * column is wider than Lifecycle's because the enrollment table carries
     * seven columns, and it scrolls inside itself so the page never does. */
    <div
      className="mx-auto flex w-full max-w-5xl flex-col gap-4 overflow-auto p-6"
      data-agent="enrollment-panel"
    >
      <div className="flex flex-wrap items-start gap-3">
        <div className="flex-1">
          <h2 className="type-subhead text-text">
            Participants ·{" "}
            <span className="text-text-muted">
              {rows.length === 0 ? "none enrolled" : `${rows.length} enrolled`}
            </span>
          </h2>
          <p className="mt-1 text-xs text-text-muted">
            One link per participant. They paste it once, their editor joins the
            study, and what each instrument will capture is listed before
            anything is recorded.
          </p>
        </div>
        {canMint && <MintDialog studyId={studyId} onMinted={load} />}
      </div>
      {rows.length === 0 ? (
        <p className="rounded-input border border-dashed border-border px-3 py-6 text-center text-sm text-text-muted">
          No participants yet — mint a link to enroll the first one.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-3xl text-sm">
            <thead>
              <tr className="text-left text-text-muted">
                <th className="py-1 font-medium">Participant</th>
                <th className="py-1 font-medium">Condition</th>
                <th className="py-1 font-medium">Grain</th>
                <th className="py-1 font-medium">Status</th>
                <th className="py-1 font-medium">Link</th>
                <th className="py-1 font-medium">Will capture</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.id} className="border-t border-border">
                  <td className="py-1.5 font-mono">{t.participantId}</td>
                  <td className="py-1.5">{t.condition}</td>
                  <td className="py-1.5">{t.grain}</td>
                  <td className={cn("py-1.5", STATUS_STYLE[t.status])}>
                    {t.status}
                  </td>
                  <td className="py-1.5">
                    {t.status === "unredeemed" && t.connectionString ? (
                      <div className="flex items-center gap-1">
                        <Button
                          size="sm"
                          variant="subtle"
                          className="shrink-0 text-xs"
                          onClick={() => copy(t.connectionString ?? "", t.id)}
                          title="Copy connection string"
                        >
                          {copied === t.id ? (
                            <Check className="h-3.5 w-3.5" aria-hidden />
                          ) : (
                            <Copy className="h-3.5 w-3.5" aria-hidden />
                          )}
                          {copied === t.id ? "Copied" : "Copy link"}
                        </Button>
                        <Button
                          asChild
                          size="sm"
                          variant="ghost"
                          className="shrink-0"
                        >
                          <a
                            href={vscodeDeepLink(t.connectionString)}
                            data-agent="open-in-vscode"
                            title="Open in VS Code (requires extension)"
                          >
                            <ExternalLink className="h-3.5 w-3.5" aria-hidden />
                          </a>
                        </Button>
                      </div>
                    ) : t.status === "paired" || t.status === "streaming" ? (
                      <span className="text-xs text-text-muted">Paired</span>
                    ) : (
                      <span className="text-xs text-text-muted">—</span>
                    )}
                  </td>
                  <td className="py-1.5">
                    {t.captureConfig ? (
                      <div
                        className="flex flex-wrap gap-1"
                        title={`captureConfigVersion ${t.captureConfig.captureConfigVersion}`}
                      >
                        {t.captureConfig.enabledInstruments.map((i) => {
                          const cat = catalog.find(
                            (c) =>
                              c.instrument === "cognitiveOverlay" &&
                              c.path[0] === i.name &&
                              c.path[c.path.length - 1] === "enabled",
                          );
                          const chip = (
                            <span
                              key={i.name}
                              role={canToggle ? "button" : undefined}
                              tabIndex={canToggle ? 0 : undefined}
                              onClick={() => {
                                if (canToggle && cat) setPopoverEntry(cat);
                              }}
                              onKeyDown={(e) => {
                                if (
                                  canToggle &&
                                  cat &&
                                  (e.key === "Enter" || e.key === " ")
                                )
                                  setPopoverEntry(cat);
                              }}
                              className={cn(
                                "rounded-input border px-1.5 py-0.5 font-mono text-xs",
                                canToggle
                                  ? "cursor-pointer hover:ring-1 hover:ring-accent"
                                  : "",
                                i.enabled
                                  ? "border-accent text-accent"
                                  : "border-border text-text-muted line-through",
                              )}
                            >
                              {i.name}
                            </span>
                          );
                          return chip;
                        })}
                      </div>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </td>
                  <td className="py-1.5 text-right">
                    {canMint && t.status !== "revoked" && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() =>
                          void api
                            .revokeEnrollmentToken(studyId, t.id)
                            .then(load)
                        }
                      >
                        Revoke
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {popoverEntry && (
        <TogglePopover
          studyId={studyId}
          entry={popoverEntry}
          role={role}
          onToggle={() => {
            setPopoverEntry(null);
            load();
          }}
          onClose={() => setPopoverEntry(null)}
        />
      )}
    </div>
  );
}
