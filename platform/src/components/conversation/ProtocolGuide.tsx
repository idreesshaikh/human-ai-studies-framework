import { HelpCircle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { MANDATORY_SLOTS, SLOT_LABELS, SLOT_DESCRIPTIONS } from "@/lib/types";

/* A short reference for the 8 mandatory sections of the protocol draft:
 * what each one means, right where the draft rail shows them being filled. */
export function ProtocolGuide() {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label="What are these sections?"
          data-agent="protocol-guide-open"
        >
          <HelpCircle className="size-4" aria-hidden />
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogTitle>The 8 sections of a protocol draft</DialogTitle>
        <DialogDescription>
          Every study protocol needs all 8 filled before it can compile and
          validate. Each design move you accept fills one of these.
        </DialogDescription>
        <dl className="mt-3 flex max-h-96 flex-col gap-3 overflow-auto">
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
        </dl>
      </DialogContent>
    </Dialog>
  );
}
