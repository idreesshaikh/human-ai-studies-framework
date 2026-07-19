import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogTitle,
  DialogDescription,
  DialogClose,
  Input,
  Button,
} from "platform";

// Radix Dialog renders nothing until opened — force it open with defaultOpen so
// the portalled panel is captured. Inline styles are layout glue only; the DS
// styling lives inside the Dialog* components.
const noop = () => {};
const footer: React.CSSProperties = {
  marginTop: 20,
  display: "flex",
  justifyContent: "flex-end",
  gap: 8,
};

export function InviteCollaborator() {
  return (
    <Dialog defaultOpen>
      <DialogTrigger asChild>
        <Button variant="outline">Invite collaborator</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>Invite a collaborator</DialogTitle>
        <DialogDescription>
          They&rsquo;ll join &ldquo;Context-Ablation 2026&rdquo; as an editor
          &mdash; able to propose design moves and approve protocol amendments.
        </DialogDescription>
        <div style={{ marginTop: 16 }}>
          <Input defaultValue="p.mercer@ed.ac.uk" />
        </div>
        <div style={footer}>
          <DialogClose asChild>
            <Button variant="ghost">Cancel</Button>
          </DialogClose>
          <Button>Send invite</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function ConfirmAmendment() {
  return (
    <Dialog defaultOpen>
      <DialogContent>
        <DialogTitle>Apply this amendment?</DialogTitle>
        <DialogDescription>
          Adding a code-verification measure changes the analysis plan for 2 of
          8 enrolled participants. Sessions already recorded stay under the
          previous protocol version.
        </DialogDescription>
        <div style={footer}>
          <DialogClose asChild>
            <Button variant="ghost" onClick={noop}>
              Keep draft
            </Button>
          </DialogClose>
          <Button>Apply amendment</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
