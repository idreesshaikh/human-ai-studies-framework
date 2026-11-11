import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Copy, Check, ExternalLink } from "lucide-react";
import { useApi } from "@/lib/session";
import { studyApi } from "@/lib/studyApi";
import { SYNTHETIC_EXAMPLE_LABEL } from "@/lib/syntheticExample";
import { hasRole, type Role } from "@/lib/capabilities";
import type { EnrollmentTokenView, ToggleCatalogEntry } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/field";
import { Pagination, paginate } from "@/components/ui/pagination";
import { Surface } from "@/components/shell/Surface";
import { EmptyState } from "@/components/shell/EmptyState";
import { Notice } from "@/components/ui/notice";
import { LiveSessions } from "./LiveSessions";
import { MintDialog } from "./MintDialog";
import { TogglePopover } from "./TogglePopover";
import { summarizeProducerStates } from "./captureSummary";
import {
  EXTENSION_NAME,
  EXTENSION_RELEASES_URL,
  vscodeDeepLink,
} from "@/lib/extension";
import { cn } from "@/lib/cn";
import {
  APPLY_PROTOCOL_FIRST,
  captureTokenLabel,
  enrollmentHeading,
  isMissingProtocolError,
  plainErrorMessage,
  conditionLabel,
} from "@/lib/uiText";

/* What the roster says for each link state. The ids stay as recorded. */
const STATUS_LABEL: Record<string, string> = {
  unredeemed: "Not used yet",
  paired: "Paired",
  streaming: "Sending data",
  revoked: "Revoked",
};

const GRAIN_LABEL: Record<string, string> = {
  participant: "Per participant",
  session: "Per session",
};

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
  hasProtocol,
}: {
  studyId: string;
  role: Role | null;
  hasProtocol: boolean;
}) {
  const api = useApi();
  const [rows, setRows] = useState<EnrollmentTokenView[]>([]);
  const [catalog, setCatalog] = useState<ToggleCatalogEntry[]>([]);
  const [popoverEntry, setPopoverEntry] = useState<ToggleCatalogEntry | null>(
    null,
  );
  const [copied, setCopied] = useState<string | null>(null);
  const [revokeError, setRevokeError] = useState("");
  /* Revoking cuts a participant off and cannot be undone, so it takes a
   * second, explicit confirmation on the same row. */
  const [confirmingRevoke, setConfirmingRevoke] = useState<string | null>(null);
  const [loadError, setLoadError] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  /* The protocol-dependent reads answer 404 until a protocol is applied. Once
   * one has, stop asking: polling a study that cannot answer only fills the
   * console (and the server log) with the same refusal every few seconds. */
  const [noProtocol, setNoProtocol] = useState(false);
  const [ready, setReady] = useState(false);
  // Imported sessions can contain participants without enrollment tokens.
  const [dataParticipants, setDataParticipants] = useState<string[]>([]);
  const synthetic = rows.some((row) => row.illustrative);
  const canMint = ready && !synthetic && hasRole(role, "mint_token");
  const canToggle = ready && !synthetic && hasRole(role, "toggle_capture");
  const roster = paginate(rows.filter((row) =>
    `${row.participantId} ${row.condition} ${conditionLabel(row.condition)} ${row.status} ${STATUS_LABEL[row.status] ?? ""}`.toLowerCase().includes(query.trim().toLowerCase()),
  ), page);

  const load = useCallback(() => {
    if (!hasProtocol) return;
    // Tokens first: a study with no applied protocol refuses them, and that
    // one answer is enough to know the other two reads would be refused too.
    void api
      .listEnrollmentTokens(studyId)
      .then((list) => {
        setRows(list);
        setLoadError("");
        setNoProtocol(false);
        setReady(true);
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
      })
      .catch((e: unknown) => {
        if (isMissingProtocolError(e)) {
          setReady(false);
          setNoProtocol(true);
          setLoadError(APPLY_PROTOCOL_FIRST);
          return;
        }
        setLoadError(plainErrorMessage(e, "Could not load enrollment."));
      });
  }, [studyId, api, hasProtocol]);
  useEffect(load, [load]);
  useEffect(() => { setQuery(""); setPage(0); }, [studyId]);

  // Live polling: refresh statuses every 15s, but only once a protocol exists.
  const pollRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  useEffect(() => {
    if (!ready || !hasProtocol) return;
    pollRef.current = setInterval(load, 15_000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [load, ready, hasProtocol]);

  /* Revoking used to be `void api.revoke(...).then(load)`  -  a rejection
   * became an unhandled promise and the row simply stayed, which reads as
   * the button doing nothing. Optimistic, with a rollback and a stated
   * reason. */
  const revoke = async (tokenId: string) => {
    const before = rows;
    setConfirmingRevoke(null);
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
    setRevokeError("");
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(id);
      setTimeout(() => setCopied(null), 2000);
    }).catch(() => setRevokeError("Could not copy the link. Select and copy it manually."));
  };

  if (!hasProtocol || noProtocol) {
    return (
      <Surface measure="work" label="Participants">
        <EmptyState
          line="Set up and apply a protocol before creating participant links. Each link carries the assigned tasks and capture configuration."
          action={
            <Button asChild size="sm">
              <Link to={{ search: "?tab=conversation" }}>
                Open Setup
              </Link>
            </Button>
          }
        />
      </Surface>
    );
  }

  const redeemed = rows.filter(
    (r) => r.status === "paired" || r.status === "streaming",
  ).length;
  const revokedCount = rows.filter((r) => r.status === "revoked").length;
  const heading = enrollmentHeading(rows.length, redeemed, revokedCount);

  return (
    /* Keep the workspace measure stable; let the roster scroll within it. */
    <Surface measure="work" label="Participants">
      {synthetic && (
        <Notice>
          <strong>{SYNTHETIC_EXAMPLE_LABEL}</strong> These example links are
          illustrative and cannot connect an editor. Create a separate study
          for live capture.
        </Notice>
      )}
      <div className="flex flex-wrap items-start gap-3">
        <div className="flex-1">
          {/* Counts enrollment links, so it says "enrolled" only about
            * enrolment  -  a study holding imported or replayed sessions has
            * participants without ever having minted one. */}
          <h2 className="type-section text-text">{heading.title}</h2>
          {heading.detail && (
            <p className="type-note text-text-muted">{heading.detail}</p>
          )}
          {/* Prose is held to the reading measure even inside a wider column  -
            * the layout contract has a measure for running text precisely so
            * a panel does not set its prose to the width its table needs. */}
          {!synthetic && (
            <>
              <p className="mt-1 max-w-work type-body text-text-muted">
                Share one link per participant. They review the study and capture
                settings before recording.
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
                Install the {EXTENSION_NAME} extension for VS Code first.
              </p>
              <div className="mt-1 flex max-w-work flex-wrap items-center gap-x-1.5 gap-y-1 type-caption text-text-muted">
                <span>Download the extension:</span>{" "}
                <a
                  href={EXTENSION_RELEASES_URL}
                  target="_blank"
                  rel="noreferrer"
                  className="touch-link inline-block py-1 -my-1 underline underline-offset-2 hover:text-text"
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
            </>
          )}
        </div>
        {/* Only while there is a roster to add to. With none, the same control
          * moves into the empty state below, next to the sentence telling you
          * to press it  -  it used to sit a thousand pixels away at the far
          * right of a `wide` surface, so the instruction and its button were
          * never in one glance. */}
        {canMint && !loadError && (
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
      {ready && <LiveSessions studyId={studyId} />}
      {rows.length === 0 ? (
        /* The one place this absence is stated, and it carries the control
          * that ends it. The heading above already says "None enrolled"; this
          * used to repeat it as a sentence in a dashed box with the button
          * that would fix it parked off at the other end of the row. */
        <EmptyState
          line={
            dataParticipants.length > 0 ? (
              <>
                No enrollment links created yet. This study already holds data
                for {dataParticipants.length} participant
                {dataParticipants.length === 1 ? "" : "s"} (
                {dataParticipants.join(", ")}) collected outside the enrollment
                flow. See the Data tab, or create a link for someone new.
              </>
            ) : (
              "Create one link per participant. Each row shows its assignment, capture scope, and whether it has been claimed."
            )
          }
        />
      ) : (
        <div className="flex min-w-0 flex-col gap-3">
          <Field label="Search participants">
            <Input type="search" value={query} placeholder="Participant, condition or link status" onChange={(e) => { setQuery(e.target.value); setPage(0); }} />
          </Field>
          <p className="type-caption text-text-muted sm:hidden">Scroll sideways to see link and capture settings.</p>
        <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Participant links">
          <table className="w-full min-w-[var(--enrollment-table-min-width)] table-fixed type-body">
            <colgroup>
              <col className="w-24" />
              <col className="w-32" />
              <col className="w-28" />
              <col className="w-44" />
              <col />
              {canMint && <col className="w-20" />}
            </colgroup>
            <thead>
              <tr className="text-left text-text-muted">
                <th className="sticky left-0 z-10 whitespace-nowrap bg-bg px-3 py-2 font-medium">Participant</th>
                <th className="whitespace-nowrap px-3 py-2 font-medium">Condition</th>
                <th className="whitespace-nowrap px-3 py-2 font-medium">Status</th>
                <th className="whitespace-nowrap px-3 py-2 font-medium">Link</th>
                <th className="whitespace-nowrap px-3 py-2 font-medium">Will capture</th>
                {canMint && <th className="sticky right-0 bg-bg"><span className="sr-only">Actions</span></th>}
              </tr>
            </thead>
            <tbody>
              {roster.rows.map((t) => (
                <tr key={t.id} className="border-t border-border">
                  <td className="sticky left-0 z-10 whitespace-nowrap bg-bg px-3 py-2 align-top type-quantity">
                    {t.participantId}
                    {t.grain !== "participant" && <span className="block type-caption text-text-muted">{GRAIN_LABEL[t.grain] ?? t.grain}</span>}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 align-top">{conditionLabel(t.condition)}</td>
                  <td className={cn("whitespace-nowrap px-3 py-2 align-top", STATUS_STYLE[t.status])}>
                    {STATUS_LABEL[t.status] ?? t.status}
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
                      <details>
                      <summary className="cursor-pointer rounded-control py-1 type-note text-text">Capture settings</summary>
                      <div
                        className="mt-2 flex min-w-0 flex-wrap gap-1 break-words"
                        title={`captureConfigVersion ${t.captureConfig.captureConfigVersion}`}
                      >
                        {t.captureConfig.enabledInstruments.map((i) => {
                          const cat = catalog.find(
                            (c) =>
                              c.instrument === "tern" &&
                              c.path[0] === i.name &&
                              c.path[c.path.length - 1] === "enabled",
                          );
                          const interactive = canToggle && Boolean(cat);
                          const chip = (
                            <span
                              key={i.name}
                              role={interactive ? "button" : undefined}
                              title={i.name}
                              tabIndex={interactive ? 0 : undefined}
                              onClick={() => {
                                if (canToggle && cat) setPopoverEntry(cat);
                              }}
                              onKeyDown={(e) => {
                                if (
                                  canToggle &&
                                  cat &&
                                  (e.key === "Enter" || e.key === " ")
                                ) {
                                  e.preventDefault();
                                  setPopoverEntry(cat);
                                }
                              }}
                              className={cn(
                                "inline-flex min-h-6 items-center rounded-input border px-1.5 py-0.5 type-quantity",
                                interactive
                                  ? "cursor-pointer hover:bg-accent-wash"
                                  : "",
                                i.enabled
                                  ? "border-accent text-accent"
                                  : "border-border text-text-muted line-through",
                              )}
                            >
                              {captureTokenLabel(i.name)}
                            </span>
                          );
                          return chip;
                        })}
                        {t.captureConfig.producerStates && (
                            <span className="basis-full break-words type-caption text-text-muted">
                            {summarizeProducerStates(t.captureConfig.producerStates)}
                          </span>
                        )}
                      </div>
                      </details>
                    ) : (
                      <span className="text-text-muted">-</span>
                    )}
                  </td>
                  {canMint && <td className="sticky right-0 whitespace-nowrap bg-bg px-3 py-2 text-right align-top">
                    {t.status !== "revoked" && confirmingRevoke !== t.id && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-critical"
                        aria-label={`Revoke link for ${t.participantId}`}
                        onClick={() => setConfirmingRevoke(t.id)}
                      >
                        Revoke
                      </Button>
                    )}
                    {t.status !== "revoked" && confirmingRevoke === t.id && (
                      <span
                        role="group"
                        aria-label={`Confirm revoking ${t.participantId}`}
                        className="inline-flex items-center gap-2"
                      >
                        <span className="type-caption text-text-muted">
                          Revoke permanently?
                        </span>
                        <Button
                          size="sm"
                          variant="danger"
                          autoFocus
                          aria-label={`Confirm revoke link for ${t.participantId}`}
                          onClick={() => void revoke(t.id)}
                        >
                          Revoke
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setConfirmingRevoke(null)}
                        >
                          Cancel
                        </Button>
                      </span>
                    )}
                  </td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {roster.total === 0 && <p role="status" className="type-note text-text-muted">No matching participants. Try another search.</p>}
        <Pagination {...roster} label="Participants" onChange={setPage} />
        </div>
      )}
      {!synthetic && popoverEntry && (
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
