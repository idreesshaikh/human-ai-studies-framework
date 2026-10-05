import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { evidenceApi, type EvidenceContext } from "@/lib/evidenceApi";
import { useAsync } from "@/lib/useAsync";
import { EvidenceDetails } from "./EvidenceDetails";

const EMPTY: EvidenceContext = { query: "", population: "", task: "", construct: "", producers: [], instruments: [], confirmedRelationIds: [] };
const STATUS = { compatible: "Compatible", conditional: "Conditional", incompatible: "Incompatible", "insufficient-evidence": "More evidence needed" };

export function EvidencePanel({ studyId, onProposed }: { studyId: string; onProposed: () => Promise<void> }) {
  const map = useAsync(() => evidenceApi.load(studyId), [studyId]);
  const [context, setContext] = useState<EvidenceContext>(EMPTY);
  const [compared, setCompared] = useState<EvidenceContext | null>(null);
  const results = useAsync(async () => compared ? { ...await evidenceApi.compare(studyId, compared), context: compared } : null, [studyId, compared]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<string[]>([]);
  const proposal = useRef<{ key: string; id: string } | null>(null);

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
    if (!compared || !results.data) return;
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
      <h3 className="type-subhead text-text">Evidence-linked methods</h3>
      <p className="type-caption text-text-muted">Compare source-backed methods. No choice changes the protocol without your approval.</p>
      {map.loading && <p role="status" className="type-caption text-text-muted">Loading evidence…</p>}
      {map.error && <Notice kind="problem">{map.error} <button className="underline" onClick={map.reload}>Retry</button></Notice>}
      {map.data?.document && <p className="type-caption text-text-muted">{map.data.document.mapId} · {map.data.document.mapVersion}<br />{map.data.document.description}</p>}
      <div className="space-y-2">
        <Label htmlFor="evidence-file">{map.data?.document ? "Import a new map version" : "Import an evidence map (JSON)"}</Label>
        <input id="evidence-file" type="file" accept=".json,application/json" disabled={busy} className="block w-full min-w-0 type-caption text-text-muted" onChange={e => { void importFile(e.target.files?.[0]); e.target.value = ""; }} />
      </div>
      {map.data?.document && (
        <form className="space-y-4" onSubmit={e => { e.preventDefault(); const next = { ...context, producers: context.producers.map(v => v.trim()).filter(Boolean), instruments: context.instruments.map(v => v.trim()).filter(Boolean) }; setContext(next); setCompared(next); }}>
          <div className="grid gap-3 sm:grid-cols-2">
            {([['query', 'Research question'], ['population', 'Population'], ['task', 'Task'], ['construct', 'Construct'], ['producers', 'Available producers (comma-separated)'], ['instruments', 'Available instruments (comma-separated)']] as const).map(([key, label]) => (
              <div key={key} className={key === 'query' ? 'space-y-1 sm:col-span-2' : 'space-y-1'}>
                <Label htmlFor={`evidence-${key}`}>{label}</Label>
                <Input id={`evidence-${key}`} value={Array.isArray(context[key]) ? context[key].join(',') : context[key]} onChange={e => change(key, e.target.value)} disabled={busy} />
              </div>
            ))}
          </div>
          <p className="type-caption text-text-muted">Use the map’s exact population, task and construct labels. Different contexts need a curator’s applicability assessment. Equipment listed here is your declaration, not an automatic capture check.</p>
          <Button type="submit" size="sm" disabled={busy || results.loading}>Compare methods</Button>
        </form>
      )}
      {error && <Notice kind="problem">{error}</Notice>}
      {compared && results.loading && <p role="status" className="type-caption text-text-muted">Checking constraints…</p>}
      {compared && results.error && <Notice kind="problem">{results.error} <button className="underline" onClick={results.reload}>Retry comparison</button></Notice>}
      {compared && results.data && results.data.context === compared && !results.loading && !results.error && (
        <ol className="divide-y divide-border" aria-label="Method alternatives">
          {results.data.candidates.length === 0 && <li className="type-caption text-text-muted">No mapped studies. Import a map with study evidence.</li>}
          {results.data.candidates.map(candidate => (
            <li key={candidate.id} className="space-y-3 py-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h4 className="type-control text-text">{candidate.designFamily ?? "Unspecified design"}</h4>
                <span className="type-caption text-text-muted">{STATUS[candidate.status]}</span>
              </div>
              <p className="type-caption text-text-muted">{candidate.missingFacts[0] ?? candidate.reasons[0] ?? 'Inspect the source and its conditions.'}</p>
              <details open={expanded.includes(candidate.id)} onToggle={event => {
                const open = event.currentTarget.open;
                setExpanded(current => open ? current.includes(candidate.id) ? current : [...current, candidate.id] : current.filter(id => id !== candidate.id));
              }}>
                <summary className="type-caption cursor-pointer text-accent">Sources, limits and capture requirements</summary>
                <EvidenceDetails candidate={candidate} />
                {candidate.sources.filter(s => s.review.status === 'reviewed' && s.kind !== 'reported-method-use' && ['compatible', 'conditional'].includes(s.applicability.status)).map(source => (
                  <label key={source.id} className="mt-3 flex items-start gap-2 type-caption text-text">
                    <input type="checkbox" className="mt-0.5 size-4 shrink-0 accent-accent" checked={context.confirmedRelationIds.includes(source.id)} disabled={busy} onChange={e => {
                      const next = { ...context, confirmedRelationIds: e.target.checked ? [...context.confirmedRelationIds, source.id] : context.confirmedRelationIds.filter(id => id !== source.id) };
                      setContext(next); setCompared(next);
                    }} />
                    <span>I checked the source context: {source.applicability.context}</span>
                  </label>
                ))}
              </details>
              <Button size="sm" variant="subtle" disabled={busy || !['compatible', 'conditional'].includes(candidate.status)} onClick={() => void propose(candidate.id)}>Review this choice in chat</Button>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
