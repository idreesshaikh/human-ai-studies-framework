import { useState } from "react";
import { Copy, Check, Link2 } from "lucide-react";
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
        <Button size="sm">
          Invite
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Share this project</DialogTitle>
          <DialogDescription>
            Anyone with the link can join as a member. You can revoke it anytime.
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          {error && <Notice kind="problem">{error}</Notice>}
          {!invite ? (
            !error && (
              <p className="type-body text-text-muted">
                Create a link to share with teammates.
              </p>
            )
          ) : (
            <div className="flex flex-col gap-3">
              <p className="type-body text-text">
                Share this link to invite people as a member:
              </p>
              <div className="control control-group gap-2 pl-3">
                <Link2 className="size-4 shrink-0 text-text-muted" aria-hidden />
                <span className="min-w-0 flex-1 truncate type-quantity text-text">
                  {window.location.origin + (invite.url ?? "")}
                </span>
                <Button size="sm" variant="subtle" onClick={copy} className="m-1 shrink-0">
                  {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
                  {copied ? "Copied" : "Copy"}
                </Button>
              </div>
            </div>
          )}
        </DialogBody>
        <DialogFooter>
          <Button type="button" variant="outline" size="sm" onClick={() => setOpen(false)}>
            {invite ? "Done" : "Cancel"}
          </Button>
          {!invite && (
            <Button size="sm" onClick={submit} disabled={busy}>
              {busy ? "Creating…" : "Create link"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
