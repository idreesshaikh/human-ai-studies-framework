import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
  DialogClose,
  Button,
} from "platform";

// DialogTitle shown in its natural home: the open dialog header.
const footer: React.CSSProperties = {
  marginTop: 20,
  display: "flex",
  justifyContent: "flex-end",
  gap: 8,
};

export function InHeader() {
  return (
    <Dialog defaultOpen>
      <DialogContent>
        <DialogTitle>Apply this amendment?</DialogTitle>
        <DialogDescription>
          Adding a code-verification measure changes the analysis plan for 2 of
          8 enrolled participants.
        </DialogDescription>
        <div style={footer}>
          <DialogClose asChild>
            <Button variant="ghost">Keep draft</Button>
          </DialogClose>
          <Button>Apply amendment</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
