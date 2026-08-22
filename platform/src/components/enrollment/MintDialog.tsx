import { useEffect, useState } from "react";
import { Copy, Check, ExternalLink } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { useApi } from "@/lib/session";
import {
  ApiError,
  type CaptureOverrides,
  type EnrollmentTokenView,
  type ToggleCatalogEntry,
} from "@/lib/api";
/* A participant who already has the extension installed can skip the paste
 * entirely. The link is built in one place: this file used to carry its own
 * copy of the authority string, and that second copy is how the identity
 * drifted out of sync with the extension manifest. */
import { vscodeDeepLink } from "@/lib/extension";

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

/* Mint pairing tokens for a study. Copy-link (here: copy connection string) is
 * the primary affordance  -  the participant pastes it into their IDE once. The
 * dialog also carries the per-mint capture config: every switch the protocol
 * declares can be tuned for the whole batch before minting (AI lifecycle,
 * behavioral streams, metric toggles), layered on the protocol-derived defaults
 * rather than re-derived. Condition assignment is never touched here  -  that
 * stays the assignment engine's job. */
export function MintDialog({ studyId, onMinted }: { studyId: string; onMinted: () => void }) {
  const api = useApi();
  const [open, setOpen] = useState(false);
  const [count, setCount] = useState(1);
  // The field holds raw text so it can be cleared and retyped; `count` is the
  // validated whole number in [1, 100] the mint call actually uses.
  const [countText, setCountText] = useState("1");
  const onCountChange = (raw: string) => {
    setCountText(raw);
    const n = parseInt(raw, 10);
    if (Number.isFinite(n) && n >= 1 && n <= 100) setCount(n);
  };
  const onCountBlur = () => {
    const n = Math.min(100, Math.max(1, parseInt(countText, 10) || 1));
    setCount(n);
    setCountText(String(n));
  };
  const [grain, setGrain] = useState<"participant" | "session">("participant");
  const [catalog, setCatalog] = useState<ToggleCatalogEntry[] | null>(null);
  // Only the switches the researcher actually changed, keyed by instrument.path,
  // so the payload carries a diff rather than a full re-declaration.
  const [changed, setChanged] = useState<Record<string, { instrument: string; path: string[]; value: unknown }>>({});
  const [minted, setMinted] = useState<EnrollmentTokenView[]>([]);
  const [copied, setCopied] = useState<string | null>(null);
  const [minting, setMinting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    void api.toggleCatalog(studyId).then(setCatalog).catch(() => setCatalog([]));
  }, [open, studyId, api]);

  const toggle = (e: ToggleCatalogEntry, checked: boolean) => {
    setChanged((prev) => {
      const key = toggleKey(e);
      const next = { ...prev };
      if (checked === defaultOn(e)) delete next[key];
      else next[key] = { instrument: e.instrument, path: e.path, value: checked };
      return next;
    });
  };

  const submit = async () => {
    if (minting) return;
    setMinting(true);
    setError(null);
    try {
      const overrides: CaptureOverrides | null =
        Object.keys(changed).length > 0
          ? { toggles: Object.values(changed) }
          : null;
      const rows = await api.mintEnrollmentTokens(studyId, count, grain, overrides);
      setMinted(rows);
      onMinted();
    } catch (e) {
      // Surface the server's reason instead of a silent no-op  -  the common case
      // is the 409 "clear the ethics gate first" (production keeps that gate;
      // set MIDDLEWARE_DEV_MODE to mint on an unapproved study while testing).
      setError(e instanceof ApiError ? e.message : "Could not mint links. Check your connection and try again.");
    } finally {
      setMinting(false);
    }
  };
  const copy = async (s: string, id: string) => {
    await navigator.clipboard.writeText(s);
    setCopied(id);
  };

  const switches = (catalog ?? []).filter(isSwitch);
  const groups = new Map<string, ToggleCatalogEntry[]>();
  for (const e of switches) {
    const group = e.leg ?? e.instrument;
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group)!.push(e);
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) setMinted([]); }}>
      <DialogTrigger asChild>
        <Button size="sm" data-agent="mint-tokens">Mint links</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>Mint enrollment links</DialogTitle>
        <DialogDescription>
          Each participant pastes one link into their IDE to join the study. A
          participant link is reusable across their sessions; a session link is
          single-use.
        </DialogDescription>
        {minted.length === 0 ? (
          <div className="mt-4 flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="count">How many</Label>
              <Input id="count" type="number" min={1} max={100} inputMode="numeric"
                value={countText}
                onChange={(e) => onCountChange(e.target.value)}
                onBlur={onCountBlur} />
              <p className="type-caption text-text-muted">A whole number from 1 to 100.</p>
            </div>
            <div className="flex flex-col gap-1">
              <Label>Grain</Label>
              <SegmentedControl
                aria-label="Grain"
                value={grain}
                onChange={setGrain}
                options={[
                  { value: "participant", label: "Participant (reusable)" },
                  { value: "session", label: "Session (single-use)" },
                ]}
              />
            </div>

            {switches.length > 0 && (
              <div className="flex flex-col gap-2 rounded-input border border-border bg-bg p-3">
                <p className="type-caption text-text-muted">
                  Capture config for these links, defaulted to the protocol. Any
                  switch you change here applies to all {count} link
                  {count > 1 ? "s" : ""} you are about to mint.
                </p>
                {[...groups.entries()].map(([group, entries]) => (
                  <div key={group} className="flex flex-col gap-1">
                    <p className="type-legend text-text-muted">
                      {LEG_LABELS[group] ?? group}
                    </p>
                    {entries.map((e) => {
                      const key = toggleKey(e);
                      const checked = key in changed
                        ? (changed[key].value as boolean)
                        : defaultOn(e);
                      return (
                        <label
                          key={key}
                          className="flex cursor-pointer items-start gap-2"
                        >
                          <input
                            type="checkbox"
                            className="mt-0.5 size-4 cursor-pointer"
                            checked={checked}
                            onChange={(ev) => toggle(e, ev.target.checked)}
                          />
                          <span className="min-w-0">
                            <span className="type-body text-text">{e.label}</span>
                            <span className="block type-caption text-text-muted">
                              {e.description}
                            </span>
                          </span>
                        </label>
                      );
                    })}
                  </div>
                ))}
              </div>
            )}

            <Button onClick={submit} disabled={minting} className="mt-1 self-start">
              {minting ? "Minting…" : `Mint ${count} link${count > 1 ? "s" : ""}`}
            </Button>
            {error && (
              <Notice kind="problem">{error}</Notice>
            )}
          </div>
        ) : (
          <div className="mt-4 flex flex-col gap-2">
            {minted.map((t) => (
              <div key={t.id} className="flex items-center gap-2 rounded-input border border-border bg-bg px-2 py-1.5">
                <span className="w-16 shrink-0 type-quantity text-text">{t.participantId}</span>
                <span className="truncate type-quantity text-text-muted">{t.connectionString}</span>
                <Button asChild size="sm" variant="ghost" className="ml-auto shrink-0">
                  <a href={vscodeDeepLink(t.connectionString ?? "")} data-agent="open-in-vscode">
                    <ExternalLink aria-hidden />
                    Open in VS Code
                  </a>
                </Button>
                <Button size="sm" variant="subtle" className="shrink-0"
                  onClick={() => copy(t.connectionString ?? "", t.id)}>
                  {copied === t.id ? <Check aria-hidden /> : <Copy aria-hidden />}
                  {copied === t.id ? "Copied" : "Copy"}
                </Button>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
