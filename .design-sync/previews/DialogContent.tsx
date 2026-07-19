import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
  DialogClose,
  Input,
  Button,
} from "platform";

// DialogContent is the portalled panel — force the Dialog open so it renders.
const footer: React.CSSProperties = {
  marginTop: 20,
  display: "flex",
  justifyContent: "flex-end",
  gap: 8,
};

export function Panel() {
  return (
    <Dialog defaultOpen>
      <DialogContent>
        <DialogTitle>Invite a collaborator</DialogTitle>
        <DialogDescription>
          They&rsquo;ll join &ldquo;Context-Ablation 2026&rdquo; as an editor
          &mdash; able to propose design moves and approve amendments.
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
