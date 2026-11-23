import { HelpCircle } from "lucide-react";
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
import { DialogClose } from "@radix-ui/react-dialog";
import { Button } from "@/components/ui/button";
import {
  MANDATORY_SLOTS,
  OPTIONAL_SLOTS,
  SLOT_LABELS,
  SLOT_DESCRIPTIONS,
} from "@/lib/types";

/* A short reference for the core sections of the protocol draft, plus the
 * optional ethics posture that should never become an approval gate. */
export function ProtocolGuide() {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label="What are these sections?"
        >
          <HelpCircle className="size-4" aria-hidden />
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>The sections of a protocol draft</DialogTitle>
          <DialogDescription>
            Unfinished sections can stay open while you draft. Ethics status is recorded, not approved.
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
        <dl className="flex flex-col gap-3">
          {MANDATORY_SLOTS.map((slot) => (
            <div key={slot}>
              <dt className="type-body font-medium text-text">
                {SLOT_LABELS[slot]}
              </dt>
              <dd className="type-caption text-text-muted">
                {SLOT_DESCRIPTIONS[slot]}
              </dd>
            </div>
          ))}
          {OPTIONAL_SLOTS.map((slot) => (
            <div key={slot} className="border-t border-border pt-3">
              <dt className="type-body font-medium text-text">
                {SLOT_LABELS[slot]} <span className="type-caption text-text-muted">(optional)</span>
              </dt>
              <dd className="type-caption text-text-muted">{SLOT_DESCRIPTIONS[slot]}</dd>
            </div>
          ))}
        </dl>

        <p className="type-note mt-4 border-t border-border pt-3 text-text-muted">
          The compiler checks the draft against the{" "}
          <a
            href="/schemas/protocol"
            target="_blank"
            rel="noreferrer"
            className="underline decoration-border underline-offset-4 hover:text-text hover:decoration-control-edge"
          >
            protocol schema
          </a>{" "}
          and names anything still missing.
        </p>
        </DialogBody>
        <DialogFooter>
          <DialogClose asChild>
            <Button size="sm" variant="outline">Close</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
