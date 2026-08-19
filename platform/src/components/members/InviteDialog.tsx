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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { useApi } from "@/lib/session";
import { ROLE_LABELS, type Role } from "@/lib/capabilities.ts";
import { ApiError, type Invitation } from "@/lib/api.ts";

const INVITABLE: Role[] = ["researcher", "viewer"];

/* Invite a colleague. When email delivery is configured (D40) the invite is
 * sent to their address; either way a one-time copy-link is returned, so a
 * self-hosted instance with no mail config still works. Expiry is stated in
 * plain language. */
export function InviteDialog({ slug, onInvited }: { slug: string; onInvited: () => void }) {
  const api = useApi();
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("researcher");
  const [invite, setInvite] = useState<Invitation | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  const reset = () => {
    setEmail("");
    setRole("researcher");
    setInvite(null);
    setCopied(false);
    setError("");
  };

  const submit = async () => {
    setError("");
    try {
      const inv = await api.createInvitation(slug, email, role);
      setInvite(inv);
      onInvited();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create the invitation.");
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
        <DialogTitle>Invite a colleague</DialogTitle>
        <DialogDescription>
          We'll email them an invite link if mail is set up here, and you
          always get a one-time link to share yourself. It works once and
          expires in 7 days.
        </DialogDescription>

        {!invite ? (
          <div className="mt-4 flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="invite-email">Their email</Label>
              <p className="type-caption text-text-muted">
                Where we send the invite link (when mail is configured).
              </p>
              <Input
                id="invite-email"
                type="email"
                placeholder="colleague@lab.example"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label>Role</Label>
              <SegmentedControl
                aria-label="Role"
                value={role}
                onChange={setRole}
                options={INVITABLE.map((r) => ({ value: r, label: ROLE_LABELS[r] }))}
              />
            </div>
            {error && <Notice kind="problem">{error}</Notice>}
            <Button onClick={submit} disabled={!email.trim()} className="mt-1 self-start">
              Create invitation
            </Button>
          </div>
        ) : (
          <div className="mt-4 flex flex-col gap-3">
            <p className="type-body text-text">
              {invite.emailed ? (
                <>
                  Sent to <span className="font-medium">{invite.email}</span> as{" "}
                  {ROLE_LABELS[invite.role]}. You can also share this link directly:
                </>
              ) : (
                <>
                  Ready for <span className="font-medium">{invite.email}</span> as{" "}
                  {ROLE_LABELS[invite.role]}. Copy this link and send it to them
                  yourself, email, chat, however you'd normally reach them:
                </>
              )}
            </p>
            {!invite.emailed && invite.emailReason && (
              <p className="rounded-input border border-border bg-bg p-2 type-caption text-text-muted">
                {invite.emailReason}
              </p>
            )}
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
