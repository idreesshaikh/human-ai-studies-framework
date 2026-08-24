import { HelpCircle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
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
          data-agent="protocol-guide-open"
        >
          <HelpCircle className="size-4" aria-hidden />
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogTitle>The sections of a protocol draft</DialogTitle>
        <DialogDescription>
          These sections help you shape a runnable study. Open choices can stay
          open while you draft. Ethics status is recorded when you have it; the
          platform does not issue or verify approval.
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
          {OPTIONAL_SLOTS.map((slot) => (
            <div key={slot} className="border-t border-border pt-3">
              <dt className="type-body font-medium text-text">
                {SLOT_LABELS[slot]} <span className="type-caption text-text-muted">(optional)</span>
              </dt>
              <dd className="type-caption text-text-muted">{SLOT_DESCRIPTIONS[slot]}</dd>
            </div>
          ))}
        </dl>

        {/* Where the list comes from, because "the app says so" is not a
          * citable answer. The core sections organise the conversation, while
          * the schema's `required` list is the authority for validation. Ethics
          * status is intentionally outside that required list. */}
        <p className="type-caption mt-4 border-t border-border pt-3 text-text-muted">
          These are the core sections the design conversation works through.
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
