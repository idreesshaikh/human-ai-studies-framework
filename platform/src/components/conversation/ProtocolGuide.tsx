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

        {/* Where the list comes from, because "the app says so" is not a
          * citable answer and a reviewer asked for one outright. Deliberately
          * careful about the distinction SlotMeter documents: these eight are
          * how the CONVERSATION is organised, while what a protocol must
          * carry to validate is the schema's own `required` list. They
          * overlap but are not the same list, and claiming otherwise here is
          * what made the old "8/8 = ready to compile" readout untrue. */}
        <p className="type-caption mt-4 border-t border-border pt-3 text-text-muted">
          These eight are the sections the design conversation works through.
          What a protocol must contain in order to validate is defined by the
          study protocol schema, which you can read at{" "}
          <a
            href="/schemas/protocol"
            target="_blank"
            rel="noreferrer"
            className="underline decoration-border underline-offset-4 hover:text-text hover:decoration-control-edge"
          >
            /schemas/protocol
          </a>
          . The compiler checks the draft against that schema and names
          anything still missing in plain words.
        </p>
      </DialogContent>
    </Dialog>
  );
}
