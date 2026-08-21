import { useState } from "react";
import { Copy, Check, Link2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { useApi } from "@/lib/session";
import { ApiError, type Invitation } from "@/lib/api.ts";

/* Invite a colleague with a reusable share link. Anyone who opens it joins
 * as a member; links are revocable. */
export function InviteDialog({ slug, onInvited }: { slug: string; onInvited: () => void }) {
  const api = useApi();
  const [open, setOpen] = useState(false);
  const [invite, setInvite] = useState<Invitation | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const reset = () => {
    setInvite(null);
    setCopied(false);
    setError("");
    setBusy(false);
  };

  const submit = async () => {
    setError("");
    setBusy(true);
    try {
      const inv = await api.createInvitation(slug, "member");
      setInvite(inv);
      onInvited();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create the invitation.");
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    const link = window.location.origin + (invite?.url ?? "");
    await navigator.clipboard.writeText(link);
    setCopied(true);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm" data-agent="invite">
          Invite
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>Share this project</DialogTitle>
        <DialogDescription>
          Create a link and share it with teammates. The link works for anyone
          who clicks it and can be revoked anytime.
        </DialogDescription>

        {!invite ? (
          <div className="mt-4 flex flex-col gap-3">
            {error && <Notice kind="problem">{error}</Notice>}
            <Button onClick={submit} disabled={busy} className="mt-1 self-start">
              {busy ? "Creating…" : "Create link"}
            </Button>
          </div>
        ) : (
          <div className="mt-4 flex flex-col gap-3">
            <p className="type-body text-text">
              Share this link to invite people as a member:
            </p>
            <div className="flex items-center gap-2 rounded-input border border-border bg-bg px-2 py-1.5">
              <Link2 className="size-4 shrink-0 text-text-muted" aria-hidden />
              <span className="truncate type-quantity text-text">
                {window.location.origin + (invite.url ?? "")}
              </span>
              <Button size="sm" variant="subtle" onClick={copy} className="ml-auto shrink-0">
                {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
                {copied ? "Copied" : "Copy"}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
