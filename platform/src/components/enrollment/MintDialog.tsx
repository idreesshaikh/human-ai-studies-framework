import { useState } from "react";
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
import { ApiError, type EnrollmentTokenView } from "@/lib/api";
/* A participant who already has the extension installed can skip the paste
 * entirely. The link is built in one place: this file used to carry its own
 * copy of the authority string, and that second copy is how the identity
 * drifted out of sync with the extension manifest. */
import { vscodeDeepLink } from "@/lib/extension";

/* Mint pairing tokens for a study. Copy-link (here: copy connection string) is
 * the primary affordance — the participant pastes it into their IDE once. */
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
  const [minted, setMinted] = useState<EnrollmentTokenView[]>([]);
  const [copied, setCopied] = useState<string | null>(null);
  const [minting, setMinting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (minting) return;
    setMinting(true);
    setError(null);
    try {
      const rows = await api.mintEnrollmentTokens(studyId, count, grain);
      setMinted(rows);
      onMinted();
    } catch (e) {
      // Surface the server's reason instead of a silent no-op — the common case
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
