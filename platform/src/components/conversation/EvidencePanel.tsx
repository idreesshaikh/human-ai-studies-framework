import { useRef, useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { evidenceApi, type EvidenceContext } from "@/lib/evidenceApi";
import { useAsync } from "@/lib/useAsync";
import { EvidenceDetails } from "./EvidenceDetails";
import { Checkbox } from "@/components/ui/checkbox";

const EMPTY: EvidenceContext = { query: "", population: "", task: "", construct: "", producers: [], instruments: [], confirmedRelationIds: [] };
const STATUS = { compatible: "Compatible", conditional: "Conditional", incompatible: "Incompatible", "insufficient-evidence": "More evidence needed" };

export function EvidencePanel({ studyId, onProposed, onClose }: { studyId: string; onProposed: () => Promise<void>; onClose?: () => void }) {
  const fileInput = useRef<HTMLInputElement>(null);
  const map = useAsync(() => evidenceApi.load(studyId), [studyId]);
  const [context, setContext] = useState<EvidenceContext>(EMPTY);
  const [compared, setCompared] = useState<EvidenceContext | null>(null);
  const results = useAsync(async () => compared ? { ...await evidenceApi.compare(studyId, compared), context: compared } : null, [studyId, compared]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<string[]>([]);
  const proposal = useRef<{ key: string; id: string } | null>(null);
  const studies = map.data?.document?.studies ?? [];
  const suggestions: Partial<Record<keyof EvidenceContext, string[]>> = {
    population: studies.flatMap(study => study.population ? [study.population] : []),
    task: studies.flatMap(study => study.tasks ?? []),
    construct: studies.flatMap(study => study.constructs),
  };
  const comparisonCurrent = results.data?.context === compared && !results.loading && !results.error;
  // Source confirmation refreshes the same comparison. Keep its controls
  // mounted so keyboard focus survives; changed constraints hide old results.
  const sameConstraints = compared && results.data && (Object.keys(EMPTY) as (keyof EvidenceContext)[])
    .filter(key => key !== "confirmedRelationIds")
    .every(key => JSON.stringify(compared[key]) === JSON.stringify(results.data!.context[key]));

  function change(key: keyof EvidenceContext, value: string) {
    setContext(current => ({ ...current, [key]: key === "producers" || key === "instruments" ? value.split(",") : value, confirmedRelationIds: [] }));
    setCompared(null);
    setError("");
  }

  async function importFile(file?: File) {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      if (file.size > 1_000_000) throw new Error("Choose a JSON evidence map smaller than 1 MB.");
      await evidenceApi.import(studyId, JSON.parse(await file.text()));
      setCompared(null);
      setContext(current => ({ ...current, confirmedRelationIds: [] }));
      map.reload();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not import this map. Try again."); }
    finally { setBusy(false); }
  }

  async function propose(candidateId: string) {
    if (!compared || !results.data || !comparisonCurrent) return;
    setBusy(true);
    setError("");
    const key = JSON.stringify([candidateId, compared, results.data.digest]);
    if (proposal.current?.key !== key) proposal.current = { key, id: crypto.randomUUID() };
    try {
      await evidenceApi.propose(studyId, compared, candidateId, results.data.digest, proposal.current.id);
      await onProposed();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save the choice. Try again."); }
    finally { setBusy(false); }
  }

  return (
    <section aria-label="Evidence-linked methods" className="mx-auto w-full max-w-reading space-y-4 px-4 py-5 sm:px-8">
      <div className="flex items-center justify-between gap-3">
        <h3 className="type-subhead text-text">Evidence-linked methods</h3>
        {onClose && <Button variant="ghost" size="icon" aria-label="Close method comparison" onClick={onClose}><X aria-hidden /></Button>}
      </div>
      <p className="type-note text-text-muted">Compare source-backed methods. No choice changes the protocol without your approval.</p>
      {map.loading && <p role="status" className="type-caption text-text-muted">Loading evidence…</p>}
      {map.error && <Notice kind="problem">{map.error} <button className="underline" onClick={map.reload}>Retry</button></Notice>}
      {map.data?.document && <p className="type-caption text-text-muted">{map.data.document.mapId} · {map.data.document.mapVersion}<br />{map.data.document.description}</p>}
      <div className="space-y-2">
        <Button variant="outline" size="sm" disabled={busy} onClick={() => fileInput.current?.click()}>
          {map.data?.document ? "Import a new map version" : "Import evidence map"}
        </Button>
        <input ref={fileInput} id="evidence-file" aria-label={map.data?.document ? "Import a new map version" : "Import an evidence map (JSON)"} tabIndex={-1} type="file" accept=".json,application/json" disabled={busy} className="sr-only" onChange={e => { void importFile(e.target.files?.[0]); e.target.value = ""; }} />
      </div>
      {map.data?.document && (
        <form className="space-y-4" onSubmit={e => { e.preventDefault(); const next = { ...context, producers: context.producers.map(v => v.trim()).filter(Boolean), instruments: context.instruments.map(v => v.trim()).filter(Boolean) }; setContext(next); setCompared(next); }}>
          <div className="grid gap-3 sm:grid-cols-2">
            {([['query', 'Research question'], ['population', 'Population'], ['task', 'Task'], ['construct', 'Construct'], ['producers', 'Available producers (comma-separated)'], ['instruments', 'Available instruments (comma-separated)']] as const).map(([key, label]) => (
              <div key={key} className={key === 'query' ? 'space-y-1 sm:col-span-2' : 'space-y-1'}>
                <Label htmlFor={`evidence-${key}`}>{label}</Label>
                <Input id={`evidence-${key}`} list={suggestions[key]?.length ? `evidence-${key}-options` : undefined} value={Array.isArray(context[key]) ? context[key].join(',') : context[key]} onChange={e => change(key, e.target.value)} disabled={busy} />
                {suggestions[key] && <datalist id={`evidence-${key}-options`}>
                  {[...new Set(suggestions[key])].map(value => <option key={value} value={value} />)}
                </datalist>}
              </div>
            ))}
          </div>
          <p className="type-note text-text-muted">Suggestions come from this map. Choose them only when they match your study; other contexts need an applicability review. Equipment listed here is your declaration, not a capture check.</p>
          <Button type="submit" size="sm" disabled={busy || results.loading}>Compare methods</Button>
        </form>
      )}
      {error && <Notice kind="problem">{error}</Notice>}
      {compared && results.loading && <p role="status" className="type-note text-text-muted">Checking constraints…</p>}
      {compared && results.error && <Notice kind="problem">{results.error} <button className="underline" onClick={results.reload}>Retry comparison</button></Notice>}
      {compared && results.data && sameConstraints && !results.error && (
        <ol className="divide-y divide-border" aria-label="Method alternatives">
          {results.data.candidates.length === 0 && <li className="type-caption text-text-muted">No mapped studies. Import a map with study evidence.</li>}
          {results.data.candidates.map(candidate => (
            <li key={candidate.id} className="space-y-3 py-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h4 className="type-control text-text">{candidate.designFamily ?? "Unspecified design"}</h4>
                <span className="type-caption text-text-muted">{comparisonCurrent ? STATUS[candidate.status] : "Checking constraints…"}</span>
              </div>
              <p className="type-note text-text-muted">{candidate.missingFacts[0] ?? candidate.reasons[0] ?? 'Inspect the source and its conditions.'}</p>
              <details open={expanded.includes(candidate.id)} onToggle={event => {
                const open = event.currentTarget.open;
                setExpanded(current => open ? current.includes(candidate.id) ? current : [...current, candidate.id] : current.filter(id => id !== candidate.id));
              }}>
                <summary className="type-caption cursor-pointer text-accent">Sources, limits and capture requirements</summary>
                <EvidenceDetails candidate={candidate} />
                {candidate.sources.filter(s => s.review.status === 'reviewed' && s.kind !== 'reported-method-use' && ['compatible', 'conditional'].includes(s.applicability.status)).map(source => (
                  <Checkbox key={source.id} rowClassName="mt-3" label={`I checked the source context: ${source.applicability.context}`} checked={context.confirmedRelationIds.includes(source.id)} disabled={busy} onChange={e => {
                    const next = { ...context, confirmedRelationIds: e.target.checked ? [...context.confirmedRelationIds, source.id] : context.confirmedRelationIds.filter(id => id !== source.id) };
                    setContext(next); setCompared(next);
                  }} />
                ))}
              </details>
              <Button size="sm" variant="subtle" disabled={busy || !comparisonCurrent || !['compatible', 'conditional'].includes(candidate.status)} onClick={() => void propose(candidate.id)}>Review this choice in chat</Button>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
