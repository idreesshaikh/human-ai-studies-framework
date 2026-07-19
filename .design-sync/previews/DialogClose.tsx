import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
  DialogClose,
  Button,
} from "platform";

// DialogClose: the dismiss control. DialogContent already renders the corner
// close (X); here it also wraps the footer's "Cancel" button via asChild.
const footer: React.CSSProperties = {
  marginTop: 20,
  display: "flex",
  justifyContent: "flex-end",
  gap: 8,
};

export function CloseControls() {
  return (
    <Dialog defaultOpen>
      <DialogContent>
        <DialogTitle>Discard unsaved moves?</DialogTitle>
        <DialogDescription>
          You have 3 accepted design moves that haven&rsquo;t been compiled into
          the protocol yet. Leaving now discards them.
        </DialogDescription>
        <div style={footer}>
          <DialogClose asChild>
            <Button variant="ghost">Cancel</Button>
          </DialogClose>
          <DialogClose asChild>
            <Button variant="outline">Discard</Button>
          </DialogClose>
        </div>
      </DialogContent>
    </Dialog>
  );
}
