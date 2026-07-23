import { useEffect, useState } from "react";
import { Check, Circle, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { studyApi, EMPTY_LIFECYCLE, type Gate, type LifecycleDoc } from "@/lib/studyApi";
import { cn } from "@/lib/cn";

/* The lifecycle board (FR-DASH-2) — the study's phases and their gate
 * artifacts, derived from the protocol, never hand-set. A calm, precise
 * surface: the current phase is highlighted, satisfied gates read green, and an
 * unsatisfied gate on the current phase can be attested to advance the study.
 * Consent-adjacent, so it does not animate. */
export function LifecycleTab({
  studyId,
  onGoToConversation,
}: {
  studyId: string;
  onGoToConversation?: () => void;
}) {
  const [doc, setDoc] = useState<LifecycleDoc | null>(null);
  // Distinct from "server unreachable": the study genuinely has no compiled
  // protocol yet, so there is nothing to gate against - the design
  // conversation isn't finished, not a bug.
  const [noProtocol, setNoProtocol] = useState(false);
  const [attesting, setAttesting] = useState<string | null>(null); // gate artifact
  const [agreed, setAgreed] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setDoc(null);
    setNoProtocol(false);
    studyApi
      .lifecycle(studyId)
      .then((d) => live && setDoc(d))
      .catch((e) => {
        if (!live) return;
        if (e instanceof ApiError && e.status === 404) {
          setNoProtocol(true);
        } else {
          // Server unreachable/other error: fall back to the honest
          // first-phase board rather than hang on "Loading…" forever.
          setDoc(EMPTY_LIFECYCLE);
        }
      });
    return () => {
      live = false;
    };
  }, [studyId]);

  function openAttest(artifact: string) {
    setAttesting(artifact);
    setAgreed(false);
    setNote("");
    setError(null);
  }

  async function confirmAttest(artifact: string) {
    setBusy(true);
    setError(null);
    try {
      const next = await studyApi.attestGate(studyId, artifact, note.trim());
      setDoc(next);
      setAttesting(null);
    } catch {
      setError("Couldn't record that attestation — check your connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  if (noProtocol) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-3 p-6">
        <h2 className="text-sm font-medium text-text">Lifecycle</h2>
        <p className="text-sm text-text-muted">
          This study doesn't have a compiled protocol yet, so there's nothing to gate
          against. Finish the design conversation — choose a design, compile it, and
          approve the draft — and the lifecycle board will pick up from there.
        </p>
        {onGoToConversation && (
          <Button size="sm" className="w-fit" onClick={onGoToConversation}>
            Go to Conversation
          </Button>
        )}
      </div>
    );
  }

  if (!doc) return <p className="p-6 text-sm text-text-muted">Loading…</p>;

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 overflow-auto p-6">
      <div>
        <h2 className="text-sm font-medium text-text">
          Lifecycle · <span className="text-text-muted">{doc.currentPhase}</span>
        </h2>
        <p className="mt-1 text-xs text-text-muted">
          You're in the <span className="font-medium text-text">{doc.currentPhase}</span> phase.
          Attest this phase's gate to advance — each is a checkpoint you confirm before the study moves on.
        </p>
      </div>
      <ol className="flex flex-col">
        {doc.phases.map((p, i) => {
          const isLast = i === doc.phases.length - 1;
          return (
            <li key={p.name} className="flex gap-3">
              <div className="flex flex-col items-center">
                <span
                  className={cn(
                    "flex size-6 items-center justify-center rounded-chip border",
                    p.status === "complete" && "border-grounded bg-grounded text-accent-contrast",
                    p.status === "current" && "border-accent text-accent",
                    p.status === "upcoming" && "border-border text-text-muted",
                  )}
                >
                  {p.status === "complete" ? (
                    <Check className="size-3.5" aria-hidden />
                  ) : (
                    <Circle className="size-2 fill-current" aria-hidden />
                  )}
                </span>
                {!isLast && (
                  <span
                    className={cn(
                      "w-px flex-1",
                      p.status === "complete" ? "bg-grounded" : "bg-border",
                    )}
                  />
                )}
              </div>
              <div className={cn("flex-1 pb-6", isLast && "pb-0")}>
                <p
                  className={cn(
                    "text-sm font-medium",
                    p.status === "current" ? "text-accent" : "text-text",
                  )}
                >
                  {p.name}
                </p>
                {p.gates.length > 0 && (
                  <ul className="mt-1 flex flex-col gap-1.5">
                    {p.gates.map((g) => (
                      <GateRow
                        key={g.artifact}
                        gate={g}
                        actionable={p.status === "current" && !g.satisfied}
                        attesting={attesting === g.artifact}
                        agreed={agreed}
                        note={note}
                        busy={busy}
                        error={attesting === g.artifact ? error : null}
                        onOpen={() => openAttest(g.artifact)}
                        onCancel={() => setAttesting(null)}
                        onAgree={setAgreed}
                        onNote={setNote}
                        onConfirm={() => confirmAttest(g.artifact)}
                      />
                    ))}
                  </ul>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function GateRow({
  gate,
  actionable,
  attesting,
  agreed,
  note,
  busy,
  error,
  onOpen,
  onCancel,
  onAgree,
  onNote,
  onConfirm,
}: {
  gate: Gate;
  actionable: boolean;
  attesting: boolean;
  agreed: boolean;
  note: string;
  busy: boolean;
  error: string | null;
  onOpen: () => void;
  onCancel: () => void;
  onAgree: (v: boolean) => void;
  onNote: (v: string) => void;
  onConfirm: () => void;
}) {
  return (
    <li className="flex flex-col gap-1.5 text-xs">
      <div className="flex items-center gap-2">
        {gate.satisfied ? (
          <Check className="size-3 text-grounded" aria-hidden />
        ) : (
          <Lock className="size-3 text-unsourced" aria-hidden />
        )}
        <span className="font-mono text-text-muted">{gate.artifact}</span>
        {gate.satisfied && gate.satisfiedBy && (
          <span className="text-text-muted">· {gate.satisfiedBy.uploadedAt}</span>
        )}
        {actionable && !attesting && (
          <Button size="sm" variant="subtle" className="ml-auto" onClick={onOpen}>
            Attest & advance
          </Button>
        )}
      </div>

      {attesting && (
        <div className="ml-5 flex flex-col gap-2 rounded-input border border-border-strong bg-surface p-3">
          <label className="flex items-start gap-2 text-text">
            <input
              type="checkbox"
              checked={agreed}
              onChange={(e) => onAgree(e.target.checked)}
              className="mt-0.5"
            />
            <span>
              I confirm the requirement <span className="font-mono">{gate.artifact}</span> is met,
              and understand this advances the study to the next phase.
            </span>
          </label>
          <input
            value={note}
            onChange={(e) => onNote(e.target.value)}
            placeholder="Optional note (e.g. ethics board ref)…"
            aria-label="Attestation note"
            className="rounded-input border border-border-strong bg-bg px-2 py-1.5 text-text outline-none focus-visible:border-accent"
          />
          {error && <p className="text-unsourced">{error}</p>}
          <div className="flex items-center gap-2">
            <Button size="sm" disabled={!agreed || busy} onClick={onConfirm}>
              {busy ? "Recording…" : "Confirm & advance"}
            </Button>
            <Button size="sm" variant="ghost" onClick={onCancel} disabled={busy}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </li>
  );
}
