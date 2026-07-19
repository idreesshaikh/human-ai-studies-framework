import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
  DialogClose,
  Button,
} from "platform";

// DialogDescription: the muted supporting copy under the title.
const footer: React.CSSProperties = {
  marginTop: 20,
  display: "flex",
  justifyContent: "flex-end",
  gap: 8,
};

export function InBody() {
  return (
    <Dialog defaultOpen>
      <DialogContent>
        <DialogTitle>Archive this study?</DialogTitle>
        <DialogDescription>
          &ldquo;Comprehension Debt 2026&rdquo; will move to the archive.
          Recorded sessions and the elicitation transcript are preserved and can
          be restored at any time.
        </DialogDescription>
        <div style={footer}>
          <DialogClose asChild>
            <Button variant="ghost">Cancel</Button>
          </DialogClose>
          <Button>Archive study</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
