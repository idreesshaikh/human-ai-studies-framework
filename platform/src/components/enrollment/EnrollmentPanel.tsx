import { useEffect, useState } from "react";
import { useApi } from "@/lib/session";
import { hasRole, type Role } from "@/lib/capabilities";
import type { EnrollmentTokenView } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { MintDialog } from "./MintDialog";
import { cn } from "@/lib/cn";

const STATUS_STYLE: Record<string, string> = {
  unredeemed: "text-text-muted",
  paired: "text-accent",
  streaming: "text-accent",
  revoked: "text-unsourced line-through",
};

/* The study's enrollment surface (FR-DASH-10): mint pairing links, see who has
 * paired / is streaming, revoke. Lives inside the study workspace — running a
 * study is part of the study, not a separate tool. */
export function EnrollmentPanel({ studyId, role }: { studyId: string; role: Role | null }) {
  const api = useApi();
  const [rows, setRows] = useState<EnrollmentTokenView[]>([]);
  const canMint = hasRole(role, "mint_token");

  const load = () => void api.listEnrollmentTokens(studyId).then(setRows);
  useEffect(load, [studyId]);

  return (
    <div className="flex flex-col gap-4 p-4" data-agent="enrollment-panel">
      <div className="flex items-center gap-3">
        <h2 className="font-display text-lg text-text">Participants</h2>
        {canMint && <MintDialog studyId={studyId} onMinted={load} />}
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-text-muted">
          Mint a link for each participant; they paste it once and their editor joins the study.
        </p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-text-muted">
              <th className="py-1 font-medium">Participant</th>
              <th className="py-1 font-medium">Condition</th>
              <th className="py-1 font-medium">Grain</th>
              <th className="py-1 font-medium">Status</th>
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
                <td className={cn("py-1.5", STATUS_STYLE[t.status])}>{t.status}</td>
                <td className="py-1.5">
                  {t.captureConfig ? (
                    <div className="flex flex-wrap gap-1" title={`captureConfigVersion ${t.captureConfig.captureConfigVersion}`}>
                      {t.captureConfig.enabledInstruments.map((i) => (
                        <span key={i.name}
                          className={cn("rounded-input border px-1.5 py-0.5 font-mono text-xs",
                            i.enabled ? "border-accent text-accent" : "border-border text-text-muted line-through")}>
                          {i.name}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-text-muted">—</span>
                  )}
                </td>
                <td className="py-1.5 text-right">
                  {canMint && t.status !== "revoked" && (
                    <Button size="sm" variant="ghost"
                      onClick={() => void api.revokeEnrollmentToken(studyId, t.id).then(load)}>
                      Revoke
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
