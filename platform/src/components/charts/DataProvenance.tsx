import { Button } from "@/components/ui/button";

export function DataProvenance({ onDryRun, dryRunBusy = false }: {
  onDryRun: () => void;
  dryRunBusy?: boolean;
}) {
  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="type-subhead text-text">Where does your data come from?</h2>
        <p className="mt-1 type-caption text-text-muted">
          A study needs data to analyse. Collect it live from instrumented
          sessions, or rehearse with synthetic data first.
        </p>
      </div>

      <div className="grid overflow-hidden rounded-plate border border-border bg-surface sm:grid-cols-2">
        <div className="flex flex-col gap-1.5 border-b border-border p-4 sm:border-b-0 sm:border-r">
          <h3 className="type-label text-text">Collect it live</h3>
          <p className="type-caption flex-1 text-text-muted">
            Mint enrollment links in the Run tab. Each participant
            pastes one into their editor and their real coding sessions stream
            in.
          </p>
          <span className="type-caption text-text-muted">
            Next: the Run tab
          </span>
        </div>

        <div className="flex flex-col items-start gap-1.5 p-4">
          <h3 className="type-label text-text">Rehearse first</h3>
          <p className="type-caption flex-1 text-text-muted">
            No data yet? Run a synthetic dry run: simulated participants
            through the real capture path, so you can see the shape of your
            analysis before collecting anything. Clearly labelled, for
            rehearsal only.
          </p>
          <Button size="sm" onClick={onDryRun} className="mt-1" disabled={dryRunBusy}>
            {dryRunBusy
              ? "Running dry run…"
              : "Run a dry run (10 simulated participants)"}
          </Button>
        </div>
      </div>

    </section>
  );
}
