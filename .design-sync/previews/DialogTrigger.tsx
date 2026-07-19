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

// DialogTrigger is the control that opens the dialog. With defaultOpen the
// trigger button and the open panel are both captured.
const footer: React.CSSProperties = {
  marginTop: 20,
  display: "flex",
  justifyContent: "flex-end",
  gap: 8,
};

export function TriggerAndPanel() {
  return (
    <Dialog defaultOpen>
      <DialogTrigger asChild>
        <Button variant="outline">Invite collaborator</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>Invite a collaborator</DialogTitle>
        <DialogDescription>
          They&rsquo;ll join &ldquo;Context-Ablation 2026&rdquo; as an editor.
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
