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

/* The study's enrollment surface (FR-DASH-10): mint pairing links, see who has
 * paired / is streaming with live polling, revoke, and toggle per-metric
 * capture (FR-DASH-11). Lives inside the study workspace  -  running a study is
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
  const [revokeError, setRevokeError] = useState("");
  const [loadError, setLoadError] = useState("");
  /* Participants this study already holds data for. Enrollment tokens and
   * collected sessions are different facts: a study can carry sessions that
   * never came through a minted link (a curated import, a replayed capture,
   * the bundled demo). Saying "No participants yet" on the strength of an
   * empty token list made this tab contradict the Data tab, which was listing
   * those same participants and their completed sessions. */
  const [dataParticipants, setDataParticipants] = useState<string[]>([]);
  const canMint = hasRole(role, "mint_token");
  const canToggle = hasRole(role, "toggle_capture");

  const load = useCallback(() => {
    // A study with no compiled protocol has nothing to enroll  -  surface it
    // calmly instead of letting a rejected read blank the tab.
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

  // Live polling: refresh statuses every 15s while the panel is mounted.
  const pollRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  useEffect(() => {
    pollRef.current = setInterval(load, 15_000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [load]);

  /* Revoking used to be `void api.revoke(...).then(load)`  -  a rejection
   * became an unhandled promise and the row simply stayed, which reads as
   * the button doing nothing. Optimistic, with a rollback and a stated
   * reason. */
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

  /* Same precondition as the Data tab, and the same treatment: a study whose
   * protocol has never compiled cannot enroll anyone, so that is one fact
   * with one move that resolves it  -  not a caution stacked above a live
   * "Mint links" button, a "no sessions running" readout and a dashed box,
   * each describing a consequence of it. */
  const noProtocol =
    !!loadError &&
    (loadError.toLowerCase().includes("no protocol") ||
      loadError.toLowerCase().includes("not found"));

  if (noProtocol) {
    return (
      <Surface measure="work" label="Participants" data-agent="enrollment-panel">
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
    /* `work`, the same measure Data and Planning use  -  the four tabs of one
     * workspace must not move the content column as you switch between them.
     * This panel was the odd one out at `wide`, so Participants sat 192px
     * wider than Data and Planning and the page visibly jumped between tabs.
     *
     * The old justification  -  seven columns needing the contract's escape
     * hatch  -  does not hold: the table is `min-w-3xl` (768px) inside
     * `overflow-x-auto`, and `work` leaves 896px of column, so it fits with
     * room to spare and still scrolls on its own if a window gets tighter. */
    <Surface measure="work" label="Participants" data-agent="enrollment-panel">
      <div className="flex flex-wrap items-start gap-3">
        <div className="flex-1">
          {/* Counts enrollment links, so it says "enrolled" only about
            * enrolment  -  a study holding imported or replayed sessions has
            * participants without ever having minted one. */}
          <h2 className="type-section text-text">
            {rows.length === 0
              ? dataParticipants.length > 0
                ? "None enrolled through a link"
                : "None enrolled"
              : `${rows.length} enrolled`}
          </h2>
          {/* Prose is held to the reading measure even inside a wider column  -
            * the layout contract has a measure for running text precisely so
            * a panel does not set its prose to the width its table needs. */}
          <p className="mt-1 max-w-work type-body text-text-muted">
            One link per participant. They paste it once, their editor joins the
            study, and what each instrument will capture is listed before
            anything is recorded.
          </p>
          {/* The deep link can only reach an editor that already has the
            * extension: {EXTENSION_NAME} ships as a GitHub release artifact,
            * not on the Marketplace, so VS Code cannot fetch it on demand the
            * way a Marketplace link would. Say so once, here, rather than
            * letting a participant click a link that does nothing. */}
          {/* Same measure, and it matters more here: this sentence ends in a
            * mono command chip, so at full width the chip was stranded out at
            * the right edge on its own. VS Code's command really is named
            * "Extensions: Install from VSIX…"  -  that ellipsis is part of the
            * name, not a truncation  -  but marooned at the end of a very long
            * line it read as a string that had been cut off. */}
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
              data-agent="extension-install-link"
            >
              Download the .vsix
            </a>
            <span>and install it with</span>
            {/* Verbatim, and in the measurement voice. `type-legend`
              * uppercases and tracks its contents, which is right for a
              * column head and wrong for a string the participant has to
              * find in a menu: this rendered as "EXTENSIONS: INSTALL FROM
              * VSIX…", a command that matches nothing they can search for. */}
            <kbd className="type-quantity whitespace-nowrap rounded-chip border border-border px-1.5 py-0.5 font-mono text-text">
              Extensions: Install from VSIX…
            </kbd>
          </div>
        </div>
        {/* Only while there is a roster to add to. With none, the same control
          * moves into the empty state below, next to the sentence telling you
          * to press it  -  it used to sit a thousand pixels away at the far
          * right of a `wide` surface, so the instruction and its button were
          * never in one glance. */}
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

      {/* What is happening right now, above the roster of who *could* be
        * running. A facilitator mid-study is asking "is data arriving?", and
        * the answer belongs before the enrollment table, not after it. */}
      <LiveSessions studyId={studyId} />
      {rows.length === 0 ? (
        /* The one place this absence is stated, and it carries the control
          * that ends it. The heading above already says "None enrolled"; this
          * used to repeat it as a sentence in a dashed box with the button
          * that would fix it parked off at the other end of the row. */
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
                            data-agent="open-in-vscode"
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
