import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Copy, Check, ExternalLink } from "lucide-react";
import { useApi } from "@/lib/session";
import { studyApi } from "@/lib/studyApi";
import { hasRole, type Role } from "@/lib/capabilities";
import type { EnrollmentTokenView, ToggleCatalogEntry } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/shell/Surface";
import { EmptyState } from "@/components/shell/EmptyState";
import { Notice } from "@/components/ui/notice";
import { LiveSessions } from "./LiveSessions";
import { MintDialog } from "./MintDialog";
import { TogglePopover } from "./TogglePopover";
import {
  EXTENSION_NAME,
  EXTENSION_RELEASES_URL,
  vscodeDeepLink,
} from "@/lib/extension";
import { cn } from "@/lib/cn";

const STATUS_STYLE: Record<string, string> = {
  unredeemed: "text-text-muted",
  paired: "text-accent",
  streaming: "text-accent",
  revoked: "superseded",
};

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
  const [revokeError, setRevokeError] = useState("");
  const [loadError, setLoadError] = useState("");

  const [dataParticipants, setDataParticipants] = useState<string[]>([]);
  const canMint = hasRole(role, "mint_token");
  const canToggle = hasRole(role, "toggle_capture");

  const load = useCallback(() => {

    void api
      .listEnrollmentTokens(studyId)
      .then(setRows)
      .catch((e: unknown) =>
        setLoadError(
          e instanceof Error ? e.message : "Could not load enrollment.",
        ),
      );
    void api.toggleCatalog(studyId).then(setCatalog).catch(() => {});
    void studyApi
      .status(studyId)
      .then((s) =>
        setDataParticipants([
          ...new Set(
            s.sessions.map((row) => row.participantId).filter(Boolean),
          ),
        ]),
      )
      .catch(() => setDataParticipants([]));
  }, [studyId, api]);
  useEffect(load, [load]);

  const pollRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  useEffect(() => {
    pollRef.current = setInterval(load, 15_000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [load]);

  const revoke = async (tokenId: string) => {
    const before = rows;
    setRevokeError("");
    setRows((list) =>
      list.map((r) => (r.id === tokenId ? { ...r, status: "revoked" } : r)),
    );
    try {
      await api.revokeEnrollmentToken(studyId, tokenId);
      load();
    } catch (e) {
      setRows(before);
      setRevokeError(
        e instanceof Error ? e.message : "Could not revoke that link.",
      );
    }
  };

  const copy = (text: string, id: string) => {
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(id);
      setTimeout(() => setCopied(null), 2000);
    });
  };

  const noProtocol =
    !!loadError &&
    (loadError.toLowerCase().includes("no protocol") ||
      loadError.toLowerCase().includes("not found"));

  if (noProtocol) {
    return (
      <Surface measure="work" label="Participants">
        <EmptyState
          line="Nobody can be enrolled yet: this study has no compiled protocol. Participants join by pasting a link that carries the protocol, so it has to exist before a link can be minted."
          action={
            <Button asChild size="sm">
              <Link to={{ search: "?tab=conversation" }}>
                Open the design conversation
              </Link>
            </Button>
          }
        />
      </Surface>
    );
  }

  return (

    <Surface measure="work" label="Participants">
      <div className="flex flex-wrap items-start gap-3">
        <div className="flex-1">

          <h2 className="type-section text-text">
            {rows.length === 0
              ? dataParticipants.length > 0
                ? "None enrolled through a link"
                : "None enrolled"
              : `${rows.length} enrolled`}
          </h2>

          <p className="mt-1 max-w-work type-body text-text-muted">
            One link per participant. They paste it once, their editor joins the
            study, and what each instrument will capture is listed before
            anything is recorded.
          </p>

          <p className="mt-2 max-w-work type-body text-text-muted">
            Participants need the {EXTENSION_NAME} extension first. It is not
            on the Marketplace.
          </p>
          <div className="mt-1 flex max-w-work flex-wrap items-center gap-x-1.5 gap-y-1 type-caption text-text-muted">
            <span>Download the extension:</span>{" "}
            <a
              href={EXTENSION_RELEASES_URL}
              target="_blank"
              rel="noreferrer"
              className="inline-block py-1 -my-1 underline underline-offset-2 hover:text-text"
            >
              Download the .vsix
            </a>
            <span>and install it with</span>

            <kbd className="type-quantity whitespace-nowrap rounded-chip border border-border px-1.5 py-0.5 font-mono text-text">
              Extensions: Install from VSIX…
            </kbd>
          </div>
        </div>

        {canMint && !loadError && rows.length > 0 && (
          <MintDialog studyId={studyId} onMinted={load} />
        )}
      </div>
      {loadError && (
        <Notice kind="problem">
          Couldn&apos;t load enrollment. {loadError}
        </Notice>
      )}
      {revokeError && (
        <p role="alert" className="type-body text-status-critical">
          {revokeError}
        </p>
      )}

      <LiveSessions studyId={studyId} />
      {rows.length === 0 ? (

        <EmptyState
          line={
            dataParticipants.length > 0 ? (
              <>
                No enrollment links minted yet. This study already holds data
                for {dataParticipants.length} participant
                {dataParticipants.length === 1 ? "" : "s"} (
                {dataParticipants.join(", ")}) collected outside the enrollment
                flow  -  see the Data tab. Mint a link to enroll anyone new.
              </>
            ) : (
              "Each participant gets one link. Mint the first one and it appears here with its condition, its capture list, and whether it has been claimed."
            )
          }
          action={
            canMint ? <MintDialog studyId={studyId} onMinted={load} /> : undefined
          }
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[var(--enrollment-table-min-width)] table-fixed type-body">
            <colgroup>
              <col className="w-28" />
              <col className="w-36" />
              <col className="w-32" />
              <col className="w-36" />
              <col className="w-44" />
              <col className="w-96" />
              <col className="w-20" />
            </colgroup>
            <thead>
              <tr className="text-left text-text-muted">
                <th className="whitespace-nowrap px-3 py-2 font-medium">Participant</th>
                <th className="whitespace-nowrap px-3 py-2 font-medium">Condition</th>
                <th className="whitespace-nowrap px-3 py-2 font-medium">Grain</th>
                <th className="whitespace-nowrap px-3 py-2 font-medium">Status</th>
                <th className="whitespace-nowrap px-3 py-2 font-medium">Link</th>
                <th className="whitespace-nowrap px-3 py-2 font-medium">Will capture</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.id} className="border-t border-border">
                  <td className="whitespace-nowrap px-3 py-2 align-top type-quantity">{t.participantId}</td>
                  <td className="whitespace-nowrap px-3 py-2 align-top">{t.condition}</td>
                  <td className="whitespace-nowrap px-3 py-2 align-top">{t.grain}</td>
                  <td className={cn("whitespace-nowrap px-3 py-2 align-top", STATUS_STYLE[t.status])}>
                    {t.status}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 align-top">
                    {t.status === "unredeemed" && t.connectionString ? (
                      <div className="flex items-center gap-1">
                        <Button
                          size="sm"
                          variant="subtle"
                          className="shrink-0 type-caption"
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
                            title={`Open in VS Code (requires the ${EXTENSION_NAME} extension)`}
                          >
                            <ExternalLink className="h-3.5 w-3.5" aria-hidden />
                          </a>
                        </Button>
                      </div>
                    ) : t.status === "paired" || t.status === "streaming" ? (
                      <span className="type-caption text-text-muted">Paired</span>
                    ) : (
                      <span className="type-caption text-text-muted">-</span>
                    )}
                  </td>
                  <td className="px-3 py-2 align-top">
                    {t.captureConfig ? (
                      <div
                        className="flex min-w-0 flex-wrap gap-1 break-words"
                        title={`captureConfigVersion ${t.captureConfig.captureConfigVersion}`}
                      >
                        {t.captureConfig.enabledInstruments.map((i) => {
                          const cat = catalog.find(
                            (c) =>
                              c.instrument === "tern" &&
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
                                "rounded-input border px-1.5 py-0.5 type-quantity",
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
                        {t.captureConfig.producerStates && (
                            <span className="basis-full break-words type-caption text-text-muted">
                            {Object.entries(t.captureConfig.producerStates)
                              .filter(([id]) => id !== "tern")
                              .map(([id, state]) => `${id}: ${state}`)
                              .join("; ")}
                          </span>
                        )}
                      </div>
                    ) : (
                      <span className="text-text-muted">-</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-right align-top">
                    {canMint && t.status !== "revoked" && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => void revoke(t.id)}
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
    </Surface>
  );
}
