import { useState } from "react";
import { Copy, Check } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useApi } from "@/lib/session";
import type { EnrollmentTokenView } from "@/lib/api";
import { cn } from "@/lib/cn";

/* Mint pairing tokens for a study. Copy-link (here: copy connection string) is
 * the primary affordance — the participant pastes it into their IDE once. */
export function MintDialog({ studyId, onMinted }: { studyId: string; onMinted: () => void }) {
  const api = useApi();
  const [open, setOpen] = useState(false);
  const [count, setCount] = useState(1);
  const [grain, setGrain] = useState<"participant" | "session">("participant");
  const [minted, setMinted] = useState<EnrollmentTokenView[]>([]);
  const [copied, setCopied] = useState<string | null>(null);

  const submit = async () => {
    const rows = await api.mintEnrollmentTokens(studyId, count, grain);
    setMinted(rows);
    onMinted();
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
              <Input id="count" type="number" min={1} max={100} value={count}
                onChange={(e) => setCount(Math.max(1, Number(e.target.value)))} />
            </div>
            <div className="flex flex-col gap-1">
              <Label>Grain</Label>
              <div className="flex gap-2">
                {(["participant", "session"] as const).map((g) => (
                  <button key={g} type="button" onClick={() => setGrain(g)}
                    className={cn("rounded-input border px-3 py-1 text-sm transition-colors duration-fast",
                      grain === g ? "border-accent bg-accent-soft text-accent" : "border-border text-text hover:bg-accent-soft")}>
                    {g === "participant" ? "Participant (reusable)" : "Session (single-use)"}
                  </button>
                ))}
              </div>
            </div>
            <Button onClick={submit} className="mt-1 self-start">Mint {count} link{count > 1 ? "s" : ""}</Button>
          </div>
        ) : (
          <div className="mt-4 flex flex-col gap-2">
            {minted.map((t) => (
              <div key={t.id} className="flex items-center gap-2 rounded-input border border-border bg-bg px-2 py-1.5">
                <span className="w-16 shrink-0 font-mono text-xs text-text">{t.participantId}</span>
                <span className="truncate font-mono text-xs text-text-muted">{t.connectionString}</span>
                <Button size="sm" variant="subtle" className="ml-auto shrink-0"
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
