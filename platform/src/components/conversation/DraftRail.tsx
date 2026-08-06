import { MANDATORY_SLOTS, SLOT_LABELS, type ProtocolDraft } from "@/lib/types";
import { summarizeProtocol, type ProtocolSection } from "@/lib/protocolFormat";
import { Button } from "@/components/ui/button";
import { SlotMeter } from "./SlotMeter";
import { ProtocolGuide } from "./ProtocolGuide";

/* The draft rail: the protocol compiled so far, told as prose sections
 * rather than raw YAML — a researcher should be able to read it, not parse
 * it. The literal compiled document is still one click away behind "View
 * raw YAML" for anyone (or any agent) that wants it verbatim. */
export function DraftRail({
  draft,
  serverYaml,
  protocol,
  compileValid,
  onApply,
  applying,
  onFinish,
}: {
  draft: ProtocolDraft;
  serverYaml?: string;
  protocol?: Record<string, unknown>;
  compileValid?: boolean;
  onApply?: () => void;
  applying?: boolean;
  onFinish?: () => void;
}) {
  const complete = MANDATORY_SLOTS.every((s) => draft[s].length > 0);
  const sections: ProtocolSection[] | null = protocol
    ? summarizeProtocol(protocol)
    : null;

  return (
    <aside
      data-agent="draft-rail"
      className="flex h-full flex-col gap-stack bg-surface p-gutter"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="type-subhead text-text">
            Protocol draft
          </h2>
          <p className="type-caption text-text-muted">
            Compiled from the moves you've accepted.
          </p>
        </div>
        <ProtocolGuide />
      </div>

      <SlotMeter draft={draft} />

      {onFinish && (
        <Button
          size="sm"
          variant={complete ? "default" : "subtle"}
          data-agent="draft-finish"
          onClick={onFinish}
        >
          {complete ? "Finish & prepare protocol draft" : "Review protocol draft"}
        </Button>
      )}

      {onApply && (
        <Button
          size="sm"
          variant="subtle"
          disabled={!compileValid || applying}
          data-agent="draft-apply"
          onClick={onApply}
        >
          {applying ? "Applying…" : "Apply validated draft"}
        </Button>
      )}

      <div className="min-h-0 flex-1 overflow-auto rounded-input border border-border-strong bg-bg p-3">
        {sections ? (
          sections.length > 0 ? (
            <div className="flex flex-col gap-3">
              {sections.map((section) => (
                <SectionBlock key={section.heading} section={section} />
              ))}
            </div>
          ) : (
            <p className="type-caption text-text-muted">
              The compiled protocol is empty so far.
            </p>
          )
        ) : serverYaml?.trim() ? (
          <pre className="tabular type-caption whitespace-pre-wrap font-mono leading-relaxed text-text">
            {serverYaml}
          </pre>
        ) : (
          <div className="flex flex-col gap-3">
            {MANDATORY_SLOTS.map((s) => (
              <div key={s}>
                <h3 className="type-label text-text">{SLOT_LABELS[s]}</h3>
                {draft[s].length > 0 ? (
                  <ul className="mt-0.5 flex flex-col gap-0.5">
                    {draft[s].map((v, i) => (
                      <li key={i} className="type-body text-text">
                        {v}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="type-caption text-text-muted">Not yet resolved.</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {sections && sections.length > 0 && serverYaml?.trim() && (
        <details className="group">
          <summary className="type-caption cursor-pointer text-text-muted select-none">
            View raw YAML
          </summary>
          <pre className="tabular type-caption mt-1 max-h-56 overflow-auto whitespace-pre-wrap rounded-input border border-border-strong bg-bg p-2 font-mono leading-relaxed text-text">
            {serverYaml}
          </pre>
        </details>
      )}
    </aside>
  );
}

function SectionBlock({ section }: { section: ProtocolSection }) {
  return (
    <div>
      <h3 className="type-label text-text">{section.heading}</h3>
      {section.lines.length > 1 ? (
        <ul className="mt-0.5 flex flex-col gap-0.5">
          {section.lines.map((line, i) => (
            <li key={i} className="type-body text-text">
              {line}
            </li>
          ))}
        </ul>
      ) : (
        <p className="type-body mt-0.5 text-text">{section.lines[0]}</p>
      )}
    </div>
  );
}
