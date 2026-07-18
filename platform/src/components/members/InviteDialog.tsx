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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useApi } from "@/lib/session";
import { ROLE_LABELS, type Role } from "@/lib/capabilities.ts";
import { ApiError, type Invitation } from "@/lib/api.ts";
import { cn } from "@/lib/cn";

const INVITABLE: Role[] = ["researcher", "viewer"];

/* Invite a colleague. Copy-link is the primary affordance — email delivery
 * is an optional enhancement, so a self-hosted instance needs no mail
 * config. Expiry is stated in plain language. */
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
        <Button size="sm">Invite</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>Invite a colleague</DialogTitle>
        <DialogDescription>
          They'll join as your chosen role. The link works once and expires in
          7 days.
        </DialogDescription>

        {!invite ? (
          <div className="mt-4 flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="invite-email">Email</Label>
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
              <div className="flex gap-2">
                {INVITABLE.map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setRole(r)}
                    className={cn(
                      "rounded-input border px-3 py-1 text-sm transition-colors duration-fast",
                      role === r
                        ? "border-accent bg-accent-soft text-accent"
                        : "border-border text-text hover:bg-accent-soft",
                    )}
                  >
                    {ROLE_LABELS[r]}
                  </button>
                ))}
              </div>
            </div>
            {error && <p className="text-sm text-unsourced">{error}</p>}
            <Button onClick={submit} disabled={!email.trim()} className="mt-1 self-start">
              Create invitation
            </Button>
          </div>
        ) : (
          <div className="mt-4 flex flex-col gap-3">
            <p className="text-sm text-text">
              Invitation for <span className="font-medium">{invite.email}</span> as{" "}
              {ROLE_LABELS[invite.role]}. Share this link:
            </p>
            <div className="flex items-center gap-2 rounded-input border border-border bg-bg px-2 py-1.5">
              <Link2 className="size-4 shrink-0 text-text-muted" aria-hidden />
              <span className="truncate font-mono text-xs text-text">
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
