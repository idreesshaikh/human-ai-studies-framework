import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { studyApi, type ReplayFrame } from "@/lib/studyApi";
import { useAsync } from "@/lib/useAsync";

export function SessionReplay({ studyId, sessionId }: { studyId: string; sessionId: string }) {
  const replay = useAsync(() => studyApi.sessionReplay(studyId, sessionId), [studyId, sessionId]);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const frames = replay.data?.frames ?? [];
  useEffect(() => { setIndex(0); setPlaying(false); }, [studyId, sessionId]);
  useEffect(() => {
    if (!playing || frames.length < 2 || index >= frames.length - 1) return;
    const timer = window.setTimeout(() => setIndex(i => i + 1), 800);
    return () => window.clearTimeout(timer);
  }, [playing, index, frames.length]);
  const frame = frames[index];
  return <section aria-label="Session replay" className="flex min-w-0 flex-col gap-3">
    {replay.loading ? <p role="status" className="type-body text-text-muted">Loading replay…</p> :
      replay.error ? <div><p role="alert" className="type-body text-critical">{replay.error}</p><Button variant="outline" onClick={replay.reload}>Retry replay</Button></div> :
      !frame ? <p className="type-body text-text-muted">No captured events to replay.</p> : <>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" disabled={index === 0} onClick={() => { setPlaying(false); setIndex(i => i - 1); }}>Previous event</Button>
          <Button disabled={frames.length < 2} onClick={() => { if (index === frames.length - 1) { setIndex(0); setPlaying(true); } else setPlaying(p => !p); }}>{playing && index < frames.length - 1 ? "Pause replay" : "Play replay"}</Button>
          <Button variant="outline" disabled={index >= frames.length - 1} onClick={() => { setPlaying(false); setIndex(i => i + 1); }}>Next event</Button>
        </div>
        <label className="flex flex-col gap-1 type-caption text-text-muted">Event {index + 1} of {frames.length}
          <input className="scrub-range" aria-label="Replay position" type="range" min={0} max={frames.length - 1} value={index} onChange={e => { setPlaying(false); setIndex(Number(e.target.value)); }} />
        </label>
        <Frame frame={frame} />
      </>}
  </section>;
}

function Frame({ frame }: { frame: ReplayFrame }) {
  return <div className="min-w-0">
    <p className="break-words type-body text-text">{frame.type.replaceAll("_", " ")} · {frame.source}</p>
    <p className="break-words type-caption text-text-muted">{frame.ts}</p>
    {Object.keys(frame.changes).length > 0 && <p className="type-body text-text-muted">{frame.changes.filesChanged ?? 0} files · +{frame.changes.insertions ?? 0} / −{frame.changes.deletions ?? 0} lines</p>}
    {frame.flags.length > 0 && <p className="break-words type-caption text-critical">Integrity flags: {frame.flags.join(", ")}</p>}
    {frame.diff ? <pre aria-label="Captured code diff" className="max-h-96 overflow-auto rounded-control bg-well p-3 font-mono type-caption text-text">{frame.diff}</pre> :
      <p className="type-caption text-text-muted">{frame.codeState === "policy-disabled" ? "Code diffs are disabled by this study’s capture policy." : "No code diff was captured for this event."}</p>}
  </div>;
}
