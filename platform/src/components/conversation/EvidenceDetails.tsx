import type { EvidenceCandidate } from "@/lib/evidenceApi";

export function EvidenceDetails({ candidate }: { candidate: EvidenceCandidate }) {
  return (
    <div className="mt-3 space-y-4 break-words type-caption text-text-muted">
      {[...candidate.reasons, ...candidate.constraints, ...candidate.missingFacts].length > 0 && (
        <ul className="list-disc space-y-1 pl-4">
          {[...candidate.reasons, ...candidate.constraints, ...candidate.missingFacts].map((text, i) => <li key={`${i}-${text}`}>{text}</li>)}
        </ul>
      )}
      <p>Source population: {candidate.study.population ?? "Unknown"}. Tasks: {candidate.study.tasks?.join("; ") || "Unknown"}. Constructs: {candidate.study.constructs.join(", ") || "Unknown"}.</p>
      {candidate.sources.map(source => (
        <section key={source.id} className="space-y-1">
          <p className="font-medium text-text">{source.publication.title}</p>
          <p>{source.claimType === "reported-fact" ? "Reported finding" : source.claimType === "interpretation" ? "Reviewer interpretation" : source.claimType === "recommendation" ? "Recommendation" : "Claim type unknown"} · {source.kind.replaceAll("-", " ")}</p>
          <p>Evidence quality: {source.evidenceQuality ?? "unknown"} · {source.review.status}{source.review.reviewers.length > 0 ? ` by ${source.review.reviewers.join(", ")}` : ""}</p>
          {source.review.notes && <p>{source.review.notes}</p>}
          <p>{source.claim}</p>
          <blockquote className="whitespace-pre-wrap pl-3">“{source.passage.text}”</blockquote>
          <p>{source.passage.location} · version {source.publication.version ?? "unspecified"}</p>
          {/^(https?:\/\/)/i.test(source.publication.source) ? (
            <a href={source.publication.source} target="_blank" rel="noopener noreferrer" className="text-accent underline">Open source</a>
          ) : <p className="break-all">{source.publication.source}</p>}
          <p>Applies to: {source.applicability.context}</p>
        </section>
      ))}
      <section className="space-y-1">
        <h4 className="font-medium text-text">Measurement requirements</h4>
        {candidate.study.measures.map(measure => (
          <p key={measure.id}>{measure.id}: {measure.instrument ?? "instrument unknown"} → {measure.datasetFields?.join(", ") || "dataset fields unknown"} → {measure.analysisRecipe ?? "analysis not specified"}</p>
        ))}
        {candidate.study.captureRequirements.map((capture, i) => (
          <p key={i}>{capture.producer ?? "Unknown producer"}: {capture.availability} · {capture.eventTypes?.join(", ") || "events unspecified"}</p>
        ))}
        <p>These are requirements, not a claim that capture is configured or data exists.</p>
      </section>
      <p>Analysis assumptions: {candidate.study.analysisAssumptions?.join("; ") || "Unknown"}.</p>
      <p>Limitations: {candidate.study.limitations?.join("; ") || "Unknown"}.</p>
    </div>
  );
}
