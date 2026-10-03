import { useCallback, useEffect, useRef, useState } from "react";
import { Plus, Upload, X, ExternalLink, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Surface } from "@/components/shell/Surface";
import { Constellation } from "./Constellation";
import {
  studyApi,
  OfflineError,
  type Paper,
  type PaperGraph,
} from "@/lib/studyApi";
import { cn } from "@/lib/cn";
import { paperIdentifier } from "@/lib/paperReference";

import { hasRole, type Role } from "@/lib/capabilities";

export function LibraryTab({ studyId, role }: { studyId: string; role: Role | null }) {
  const canEdit = hasRole(role, "contribute");
  const fileInput = useRef<HTMLInputElement>(null);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [graph, setGraph] = useState<PaperGraph | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [idInput, setIdInput] = useState("");
  const [linkDraft, setLinkDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [edgesPending, setEdgesPending] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [ps, g] = await Promise.all([
        studyApi.papers(studyId),
        studyApi.papersGraph(studyId),
      ]);
      setPapers(ps);
      setGraph(g);
      return g;
    } catch (error) {
      setLoadError(
        error instanceof OfflineError
          ? error.message
          : "The library could not be loaded. Try again.",
      );
      throw error;
    } finally {
      setLoading(false);
    }
  }, [studyId]);

  useEffect(() => {
    void load().catch(() => undefined);
  }, [load]);

  useEffect(() => {
    if (!edgesPending) return;
    let cancelled = false;
    let timer: number | undefined;
    let attempts = 0;

    const poll = async () => {
      try {
        const next = await load();
        if (cancelled) return;
        if (next.edges.length > 0 || attempts >= 5) {
          setEdgesPending(false);
          return;
        }
        attempts += 1;
        timer = window.setTimeout(() => void poll(), 1000);
      } catch {
        if (!cancelled) setEdgesPending(false);
      }
    };

    timer = window.setTimeout(() => void poll(), 1000);
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [edgesPending, load]);

  async function run(fn: () => Promise<unknown>) {
    if (busy || !canEdit) return false;
    setBusy(true);
    setNote(null);
    try {
      await fn();
      await load();
      return true;
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Could not update the library. Try again.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  function ingest() {
    const raw = idInput.trim();
    if (!raw) return;
    const id = raw.toLowerCase().includes("arxiv")
      ? { arxivId: raw.replace(/.*arxiv[:/]?/i, "") }
      : /^10\./.test(raw)
        ? { doi: raw }
        : { arxivId: raw };
    run(async () => {
      const result = await studyApi.ingestPaper(studyId, id);
      setEdgesPending(Boolean(result.edgesPending));
      return result;
    }).then((saved) => { if (saved) setIdInput(""); });
  }

  function uploadPdf(ev: React.ChangeEvent<HTMLInputElement>) {
    const file = ev.target.files?.[0];
    if (file) run(() => studyApi.uploadPaperPdf(studyId, file));
  }

  function select(ref: string) {
    setSelected(ref);
    setLinkDraft((papers.find((p) => p.paperRef === ref)?.links ?? []).join(", "));
  }

  const selectedPaper = papers.find((p) => p.paperRef === selected) ?? null;
  const selectedNode = graph?.nodes.find((n) => n.paperRef === selected) ?? null;

  return (

    <Surface measure="work" label="Library">

        {canEdit && <div className="flex flex-wrap items-center gap-2">
          <Input
            value={idInput}
            onChange={(e) => setIdInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ingest()}
            placeholder="arXiv id or DOI, e.g. 2302.06590"
            aria-label="arXiv id or DOI"
            className="flex-1"
          />
          <Button size="sm" variant="subtle" onClick={ingest} disabled={busy || !idInput.trim()}>
            <Plus aria-hidden /> Add
          </Button>

          <Button size="sm" variant="subtle" disabled={busy || !canEdit} onClick={() => fileInput.current?.click()}>
            <Upload aria-hidden /> PDF
          </Button>
          <input ref={fileInput} type="file" accept="application/pdf" hidden onChange={uploadPdf} />
        </div>}

        {busy && (
          <p className="flex items-center gap-2 type-caption text-text-muted" role="status">
            <Loader2 className="size-3 animate-spin" aria-hidden />
            Updating the library…
          </p>
        )}
        {edgesPending && !busy && (
          <p className="type-caption text-text-muted" role="status">
            Paper added. Its citation neighbourhood is filling in.
          </p>
        )}
        {note && (
          <p role="alert" className="rounded-input border border-border bg-surface p-3 type-body text-text-muted">
            {note}
          </p>
        )}
        {loadError && (
          <div className="flex items-center justify-between gap-3 rounded-input border border-border bg-surface p-3">
            <p className="type-body text-text-muted">{loadError}</p>
            <Button size="sm" variant="subtle" onClick={() => void load().catch(() => undefined)}>
              Try again
            </Button>
          </div>
        )}

        <div className="rounded-card border border-border bg-surface">
          <div className="flex items-center justify-between border-b border-border px-4 py-2">
            <h3 className="type-subhead text-text">Library</h3>
            <span className="type-caption text-text-muted">
              {papers.length} {papers.length === 1 ? "paper" : "papers"}
            </span>
          </div>
          <ul className="max-h-64 overflow-y-auto">
            {loading ? (
              <li className="px-4 py-3 type-body text-text-muted" role="status">
                Loading papers…
              </li>
            ) : papers.map((p) => (
              <li
                key={p.paperRef}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 type-body",
                  p.paperRef === selected && "bg-zone-9",
                )}
              >
                <button
                  className="flex-1 truncate text-left text-text hover:text-accent"
                  onClick={() => select(p.paperRef)}
                  title={p.title || p.paperRef}
                >
                  {p.title || "Untitled paper"}
                </button>
                {p.year && (
                  <span className="tabular type-caption text-text-muted">{p.year}</span>
                )}
                <button
                  className="text-text-muted hover:text-status-critical"
                  aria-label={`Remove ${p.title || p.paperRef}`}
                  onClick={() => run(() => studyApi.deletePaper(studyId, p.paperRef))}
                  disabled={busy || !canEdit}
                >
                  <X className="size-4" aria-hidden />
                </button>
              </li>
            ))}
            {!loading && papers.length === 0 && (
              <li className="px-4 py-3 type-body text-text-muted">
                {canEdit ? "No papers yet: add one above." : "No papers have been added to this study."}
              </li>
            )}
          </ul>
        </div>

        <div
          className={cn(
            "items-stretch gap-4",
            selectedNode &&
              "grid min-h-0 lg:min-h-[var(--library-pane-h)] lg:grid-cols-[minmax(0,1fr)_minmax(16rem,20rem)]",
          )}
        >
          <div className="flex min-w-0 flex-col overflow-hidden rounded-card border border-border bg-surface p-4">
            <h3 className="type-subhead text-text">Literature map</h3>
            <p className="mt-0.5 shrink-0 type-caption text-text-muted">
              Relationships determine the constellation; year gives temporal context, node
              size shows citation weight, and edge colour shows how papers are related.
            </p>
            {loading ? (
              <div className="flex h-[var(--constellation-h)] items-center justify-center rounded-card bg-bg type-body text-text-muted" role="status">
                Mapping your literature…
              </div>
            ) : graph ? (
              <div className="min-h-0 flex-1">
                <Constellation graph={graph} selected={selected} onSelect={select} />
              </div>
            ) : null}
          </div>

          {selectedNode && (
            <aside className="relative flex min-h-0 min-w-0 flex-col overflow-hidden rounded-card border border-border bg-surface-raised p-4 lg:h-full">
              <button
                className="absolute right-3 top-3 text-text-muted hover:text-text"
                onClick={() => setSelected(null)}
                aria-label="Close detail"
              >
                <X className="size-4" aria-hidden />
              </button>
              <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain pr-2">
                <h4 className="pr-6 font-medium text-text">
                  {selectedNode.title || selected}
                </h4>
                <p className="mt-0.5 type-caption text-text-muted">
                  {paperIdentifier(selectedPaper ?? { paperRef: selected ?? "" }) ?? "Library paper"}
                  {selectedNode.year ? ` · ${selectedNode.year}` : ""}
                  {selectedNode.citationCount != null
                    ? ` · ${selectedNode.citationCount} citations`
                    : ""}
                </p>
                {(selectedPaper?.abstract || selectedNode.abstract) ? (
                  <p className="mt-2 type-body leading-relaxed text-text-muted">
                    {selectedPaper?.abstract || selectedNode.abstract}
                  </p>
                ) : (
                  <p className="mt-2 type-body text-text-muted">
                    No abstract is available from the source yet.
                  </p>
                )}
                {!selectedPaper && (
                  <p className="mt-2 type-caption text-text-muted">
                    Suggested paper, not yet in the study. Its preview is already warm
                    and can be added without another provider request.
                  </p>
                )}
              </div>

              {selectedPaper ? (
                <div className="mt-3 shrink-0 border-t border-border pt-3">
                  <label className="block type-body text-text">
                    Protocol links
                    <Input
                      disabled={!canEdit || busy}
                      value={linkDraft}
                      onChange={(e) => setLinkDraft(e.target.value)}
                      placeholder="RQ-1, metric:parameter_count, recipe:…"
                      className="mt-1"
                    />
                  </label>
                  <div className="mt-2 flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="subtle"
                      disabled={busy || !canEdit}
                      onClick={() =>
                        run(() =>
                          studyApi.setPaperLinks(
                            studyId,
                            selected!,
                            linkDraft.split(",").map((t) => t.trim()).filter(Boolean),
                          ),
                        )
                      }
                    >
                      Save links
                    </Button>
                    {selectedPaper.url && (
                      <a
                        href={selectedPaper.url}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-1 type-body text-accent hover:underline"
                      >
                        <ExternalLink className="size-3" aria-hidden /> open
                      </a>
                    )}
                  </div>
                </div>
              ) : (
                <div className="mt-3 shrink-0 border-t border-border pt-3">
                  <Button
                    size="sm"
                    variant="subtle"
                    disabled={busy || !canEdit}
                    onClick={() =>
                      run(async () => {
                        const result = await studyApi.addPaperFromGraph(
                          studyId,
                          selected!,
                        );
                        setEdgesPending(Boolean(result.edgesPending));
                        return result;
                      })
                    }
                  >
                    <Plus aria-hidden /> Add to study
                  </Button>
                </div>
              )}
            </aside>
          )}
        </div>
    </Surface>
  );
}
