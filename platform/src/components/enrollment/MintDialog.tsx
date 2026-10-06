import { useEffect, useState } from "react";
import { Copy, Check, ExternalLink } from "lucide-react";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Field } from "@/components/ui/field";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Input } from "@/components/ui/input";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { useApi } from "@/lib/session";
import {
  type CaptureOverrides,
  type EnrollmentTokenView,
  type ToggleCatalogEntry,
} from "@/lib/api";
/* A participant who already has the extension installed can skip the paste
 * entirely. The link is built in one place: this file used to carry its own
 * copy of the authority string, and that second copy is how the identity
 * drifted out of sync with the extension manifest. */
import { vscodeDeepLink } from "@/lib/extension";
import {
  GRAIN_OPTIONS,
  captureTokenLabel,
  describeMintError,
  mintCountProblem,
} from "@/lib/uiText";
import { StudyFolderField } from "./StudyFolderField";

/* The four capture legs, for the grouped config panel. The catalog carries a
 * `leg` key; the demo backend omits it, so instrument is the fallback group. */
const LEG_LABELS: Record<string, string> = {
  metrics: "Static metrics",
  behavioral: "Behavioral",
  cognitive: "Cognitive",
  agent: "Agent interaction",
};

/** A toggle the mint dialog can render as a checkbox: an on/off switch. */
function isSwitch(e: ToggleCatalogEntry): boolean {
  const leaf = e.path[e.path.length - 1];
  return (
    typeof e.currentValue === "boolean" ||
    leaf === "enabled" ||
    leaf.startsWith("capture")
  );
}

/** The protocol-derived default for a switch: on only when it is set true. */
function defaultOn(e: ToggleCatalogEntry): boolean {
  return e.currentValue === true;
}

function toggleKey(e: ToggleCatalogEntry): string {
  return `${e.instrument}.${e.path.join(".")}`;
}

/* Create pairing links for a study. Copy-link (here: copy connection string) is
 * the primary affordance  -  the participant pastes it into their IDE once. The
 * dialog also carries the per-mint capture config: every switch the protocol
 * declares can be tuned for the whole batch before minting (AI lifecycle,
 * behavioral streams, metric toggles), layered on the protocol-derived defaults
 * rather than re-derived. Condition assignment is never touched here  -  that
 * stays the assignment engine's job. */
export function MintDialog({
  studyId,
  onMinted,
}: {
  studyId: string;
  onMinted: () => void;
}) {
  const api = useApi();
  const [open, setOpen] = useState(false);
  // The field holds raw text so it can be cleared and retyped. `count` is the
  // whole number in [1, 100] the create call uses; an invalid entry is never
  // quietly turned into 1, it shows the hint and blocks the button's action.
  const [countText, setCountText] = useState("1");
  const [countTouched, setCountTouched] = useState(false);
  const countProblem = mintCountProblem(countText);
  const count = countProblem ? 0 : Number(countText.trim());
  const onCountChange = (raw: string) => {
    setCountText(raw);
    setError(null);
  };
  const [grain, setGrain] = useState<"participant" | "session">("participant");
  const [catalog, setCatalog] = useState<ToggleCatalogEntry[] | null>(null);
  // Only the switches the researcher actually changed, keyed by instrument.path,
  // so the payload carries a diff rather than a full re-declaration.
  const [changed, setChanged] = useState<
    Record<string, { instrument: string; path: string[]; value: unknown }>
  >({});
  const [minted, setMinted] = useState<EnrollmentTokenView[]>([]);
  const [copied, setCopied] = useState<string | null>(null);
  const [minting, setMinting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    void api
      .toggleCatalog(studyId)
      .then(setCatalog)
      .catch(() => setCatalog([]));
  }, [open, studyId, api]);

  const toggle = (e: ToggleCatalogEntry, checked: boolean) => {
    setChanged((prev) => {
      const key = toggleKey(e);
      const next = { ...prev };
      if (checked === defaultOn(e)) delete next[key];
      else
        next[key] = { instrument: e.instrument, path: e.path, value: checked };
      return next;
    });
  };

  const submit = async () => {
    if (minting) return;
    if (countProblem) {
      setCountTouched(true);
      return;
    }
    setMinting(true);
    setError(null);
    try {
      const overrides: CaptureOverrides | null =
        Object.keys(changed).length > 0
          ? { toggles: Object.values(changed) }
          : null;
      const rows = await api.mintEnrollmentTokens(
        studyId,
        count,
        grain,
        overrides,
      );
      setMinted(rows);
      onMinted();
    } catch (e) {
      // Surface the reason in plain words instead of a silent no-op. Ethics
      // approval is external to Phoenix and must never be presented as an app
      // gate. A study with no protocol is told to apply one first.
      setError(describeMintError(e));
    } finally {
      setMinting(false);
    }
  };
  const copy = async (s: string, id: string) => {
    setError("");
    try {
      await navigator.clipboard.writeText(s);
      setCopied(id);
    } catch {
      setError("Could not copy the link. Select and copy it manually.");
    }
  };

  const switches = (catalog ?? []).filter(isSwitch);
  const groups = new Map<string, ToggleCatalogEntry[]>();
  for (const e of switches) {
    const group = e.leg ?? e.instrument;
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group)!.push(e);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setMinted([]);
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm">Create participant links</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create participant links</DialogTitle>
          <DialogDescription>
            Participants use these links to connect in VS Code.
          </DialogDescription>
        </DialogHeader>
        <DialogBody role="region" aria-label="Participant link settings">
          {minted.length === 0 ? (
            <div className="form-stack">
              <Field
                id="count"
                label="How many"
                hint={countTouched && countProblem ? undefined : "A whole number from 1 to 100."}
                error={countTouched ? countProblem ?? undefined : undefined}
              >
                <Input
                  type="number"
                  min={1}
                  max={100}
                  inputMode="numeric"
                  stepper
                  quantity
                  value={countText}
                  onChange={(e) => onCountChange(e.target.value)}
                  onBlur={() => setCountTouched(true)}
                />
              </Field>
              <div className="field">
                <span id="link-type-label" className="type-label text-text">Link type</span>
                <SegmentedControl
                  aria-label="Link type"
                  value={grain}
                  onChange={setGrain}
                  className="flex-wrap"
                  options={[...GRAIN_OPTIONS]}
                />
                <p className="type-note text-text-muted">
                  {grain === "participant"
                    ? "Reusable across a participant’s sessions."
                    : "Single use: create a new link for each session."}
                </p>
              </div>
              <StudyFolderField studyId={studyId} />

              {switches.length > 0 && (
                <details className="border-t border-border pt-3">
                  <summary className="cursor-pointer type-control text-text">
                    Capture settings
                  </summary>
                  <div className="mt-3 flex flex-col gap-3">
                    <p className="type-note text-text-muted">
                      Protocol defaults apply. Changes affect every link in this
                      batch.
                    </p>
                    {[...groups.entries()].map(([group, entries]) => (
                      <div key={group} className="flex flex-col gap-1">
                        <p className="type-legend text-text-muted">
                          {LEG_LABELS[group] ?? captureTokenLabel(group)}
                        </p>
                        {entries.map((e) => {
                          const key = toggleKey(e);
                          const checked =
                            key in changed
                              ? (changed[key].value as boolean)
                              : defaultOn(e);
                          return (
                            <Checkbox
                              key={key}
                              label={e.label}
                              description={e.description}
                              checked={checked}
                              onChange={(ev) => toggle(e, ev.target.checked)}
                            />
                          );
                        })}
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {minted.map((t) => (
                <div
                  key={t.id}
                  className="flex flex-col gap-2 rounded-input border border-border bg-bg p-3"
                >
                  <span className="type-quantity text-text">
                    {t.participantId}
                  </span>
                  <Input
                    aria-label={`Connection link for ${t.participantId}`}
                    readOnly
                    value={t.connectionString ?? ""}
                    className="type-quantity"
                    onFocus={(event) => event.currentTarget.select()}
                  />
                  <div className="flex flex-wrap justify-end gap-2">
                    <Button asChild size="sm" variant="ghost" className="shrink-0">
                      <a href={vscodeDeepLink(t.connectionString ?? "")}>
                        <ExternalLink aria-hidden />
                        Open in VS Code
                      </a>
                    </Button>
                    <Button
                      size="sm"
                      variant="subtle"
                      className="shrink-0"
                      onClick={() => copy(t.connectionString ?? "", t.id)}
                    >
                      {copied === t.id ? <Check aria-hidden /> : <Copy aria-hidden />}
                      {copied === t.id ? "Copied" : "Copy"}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
          {error && (
            <div className="mt-4">
              <Notice kind="problem">{error}</Notice>
            </div>
          )}
        </DialogBody>
        <DialogFooter aria-busy={minting}>
          {minted.length === 0 ? (
            <>
              <Button type="button" variant="outline" size="sm" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button size="sm" onClick={submit} disabled={minting}>
                {minting
                  ? "Creating…"
                  : count > 0
                    ? `Create ${count} link${count > 1 ? "s" : ""}`
                    : "Create links"}
              </Button>
            </>
          ) : (
            <Button size="sm" onClick={() => { setOpen(false); setMinted([]); }}>
              Done
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
