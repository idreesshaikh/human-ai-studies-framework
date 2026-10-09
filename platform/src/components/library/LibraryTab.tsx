import { useEffect, useRef, useState } from "react";
import { Plus, Upload, X, ExternalLink, Loader2, Trash2 } from "lucide-react";
import { Field } from "@/components/ui/field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Notice } from "@/components/ui/notice";
import { Surface } from "@/components/shell/Surface";
import { Constellation } from "./Constellation";
import { studyApi } from "@/lib/studyApi";
import { cn } from "@/lib/cn";
import {
  paperIdentifier,
  paperLookupInput,
  paperSourceHref,
} from "@/lib/paperReference";
import { plainErrorMessage, libraryFreshness } from "@/lib/uiText";
import { templatesApi } from "@/lib/templatesApi";
import { useAsync } from "@/lib/useAsync";
import { hasRole } from "@/lib/capabilities";
import type { RoleState } from "@/lib/role";

const SORT_OPTIONS = [
  { value: "recent", label: "Recently added" },
  { value: "title", label: "Title" },
  { value: "year", label: "Newest publication" },
];
const targetsOf = (text: string) => [
  ...new Set(
    text
      .split(",")
      .map((target) => target.trim())
      .filter(Boolean),
  ),
];

export function LibraryTab({
  studyId,
  roleState,
}: {
  studyId: string;
  roleState: RoleState;
}) {
  const paperRequest = useAsync(() => studyApi.papers(studyId), [studyId]);
  const graphRequest = useAsync(() => studyApi.papersGraph(studyId), [studyId]);
  const freshness = useAsync(() => templatesApi.corpusStatus(), []);
  const papers = paperRequest.data ?? [];
  const graph = graphRequest.data;
  const initialLoading = paperRequest.loading && paperRequest.data === null;
  const canEdit =
    roleState.status === "known" && hasRole(roleState.role, "contribute");
  const [selected, setSelected] = useState<string | null>(null);
  const [idInput, setIdInput] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("recent");
  const [linkDrafts, setLinkDrafts] = useState<Record<string, string>>({});
  const [pending, setPending] = useState<string | null>(null);
  const [pendingPaper, setPendingPaper] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const pdfInput = useRef<HTMLInputElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const paperList = useRef<HTMLDivElement>(null);
  const inspectRequested = useRef(false);
  const selectedPaper = papers.find((paper) => paper.paperRef === selected);
  const selectedNode = graph?.nodes.find((node) => node.paperRef === selected);
  const linkDraft =
    (selected ? linkDrafts[selected] : undefined) ??
    (selectedPaper?.links ?? []).join(", ");
  const detail = selectedPaper ?? selectedNode;
  const inStudy = Boolean(selectedPaper || selectedNode?.ingested);
  const sourceHref = detail ? paperSourceHref(detail) : null;
  const linksChanged =
    targetsOf(linkDraft).sort().join(",") !==
    [...(selectedPaper?.links ?? [])].sort().join(",");
  const needle = query.trim().toLowerCase();
  const filtered = papers.filter((paper) =>
    [
      paper.title,
      ...(paper.authors ?? []),
      paper.year,
      paperIdentifier(paper),
      paper.venue,
    ]
      .join(" ")
      .toLowerCase()
      .includes(needle),
  );
  const visible = [...filtered].sort((a, b) =>
    sort === "title"
      ? (a.title || "").localeCompare(b.title || "")
      : sort === "year"
        ? (b.year ?? 0) - (a.year ?? 0) ||
          (a.title || "").localeCompare(b.title || "")
        : b.addedAt.localeCompare(a.addedAt) ||
          (a.title || "").localeCompare(b.title || ""),
  );

  useEffect(() => {
    if (!inspectRequested.current || !detail) return;
    inspectRequested.current = false;
    heading.current?.focus({ preventScroll: true });
    heading.current?.scrollIntoView({ block: "nearest" });
  }, [selected, detail]);

  useEffect(() => {
    if (
      pendingPaper &&
      graph?.edges.some(
        (edge) => edge.src === pendingPaper || edge.dst === pendingPaper,
      )
    )
      setPendingPaper(null);
  }, [pendingPaper, graph]);

  useEffect(() => {
    if (!pendingPaper) return;
    let timer: number;
    let attempts = 0;
    const poll = () => {
      graphRequest.reload();
      if (++attempts < 6) timer = window.setTimeout(poll, 1000);
      else setPendingPaper(null);
    };
    timer = window.setTimeout(poll, 1000);
    return () => window.clearTimeout(timer);
  }, [pendingPaper, graphRequest.reload]);

  function select(ref: string) {
    inspectRequested.current = true;
    setSelected(ref);
    setConfirmRemove(false);
    setActionError(null);
    if (ref === selected) heading.current?.focus();
  }

  async function mutate<T>(
    label: string,
    work: () => Promise<T>,
    success: (result: T) => string,
  ): Promise<T | null> {
    if (pending || !canEdit) return null;
    setPending(label);
    setActionError(null);
    setMessage(null);
    try {
      const result = await work();
      setMessage(success(result));
      paperRequest.reload();
      graphRequest.reload();
      return result;
    } catch (error) {
      setActionError(
        plainErrorMessage(
          error,
          "The change could not be saved. Check your connection and try again.",
        ),
      );
      return null;
    } finally {
      setPending(null);
    }
  }

  async function ingest() {
    const lookup = paperLookupInput(idInput);
    if (!lookup) {
      setInputError(
        "Paste an arXiv or DOI link, or enter an identifier such as 2507.09089 or 10.1145/1234567.",
      );
      return;
    }
    setInputError(null);
    const result = await mutate(
      "Adding paper…",
      () => studyApi.ingestPaper(studyId, lookup),
      (paper) => `Added ${paper.title || "paper"} to this study.`,
    );
    if (!result) return;
    setIdInput("");
    select(result.paperRef);
    if (result.edgesPending) setPendingPaper(result.paperRef);
  }

  async function uploadPdf(file: File) {
    const result = await mutate(
      "Uploading PDF…",
      () => studyApi.uploadPaperPdf(studyId, file),
      () => "PDF added to this study.",
    );
    if (result) select(result.paperRef);
    if (pdfInput.current) pdfInput.current.value = "";
  }

  async function removePaper() {
    if (!selectedPaper) return;
    const result = await mutate(
      "Removing paper…",
      () => studyApi.deletePaper(studyId, selectedPaper.paperRef),
      () => "Paper and its protocol links removed from this study.",
    );
    if (result) {
      setSelected(null);
      setConfirmRemove(false);
      paperList.current?.focus();
    }
  }

  return (
    <Surface measure="work" label="Evidence">
      <header className="flex flex-col gap-2">
        <h1 className="type-section text-text">Evidence</h1>
        <p className="max-w-reading type-body text-text-muted">
          Collect the papers behind your study. Read their abstracts, connect
          them to your protocol and explore related work.
        </p>
        {freshness.error ? (
          <p className="type-note text-text-muted">
            Library freshness is unavailable.{" "}
            <button
              className="text-accent underline"
              onClick={freshness.reload}
            >
              Check again
            </button>
          </p>
        ) : (
          <p className="type-note text-text-muted" role="status">
            {libraryFreshness(freshness.data)}
          </p>
        )}
      </header>

      {canEdit && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void ingest();
          }}
          className="flex flex-wrap items-start gap-3"
        >
          <Field
            id="evidence-paper-id"
            label="Paper link or identifier"
            hint="arXiv and DOI links, or their identifiers."
            error={inputError}
            className="min-w-0 flex-1 basis-64"
          >
            <Input
              value={idInput}
              maxLength={2048}
              disabled={Boolean(pending)}
              onChange={(event) => {
                setIdInput(event.target.value);
                setInputError(null);
              }}
              placeholder="Paste a paper link or identifier"
            />
          </Field>
          <div className="flex flex-wrap items-center gap-2 self-center">
            <Button
              type="submit"
              size="field"
              disabled={Boolean(pending) || !idInput.trim()}
            >
              <Plus aria-hidden /> Add paper
            </Button>
            <input
              ref={pdfInput}
              type="file"
              accept="application/pdf"
              className="sr-only"
              tabIndex={-1}
              aria-label="Upload a PDF"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void uploadPdf(file);
              }}
            />
            <Button
              type="button"
              size="field"
              variant="outline"
              disabled={Boolean(pending)}
              onClick={() => pdfInput.current?.click()}
            >
              <Upload aria-hidden /> Upload PDF
            </Button>
          </div>
        </form>
      )}
      {roleState.status === "known" && !canEdit && (
        <p className="type-note text-text-muted">
          You have read-only access. Owners and members can add papers and edit
          protocol links.
        </p>
      )}
      {pending && (
        <p
          role="status"
          className="flex items-center gap-2 type-note text-text-muted"
        >
          <Loader2 className="size-4 animate-spin" aria-hidden />
          {pending}
        </p>
      )}
      {message && (
        <Notice kind="note" role="status">
          {message}
        </Notice>
      )}
      {actionError && <Notice kind="problem">{actionError}</Notice>}

      <div className="grid min-w-0 items-start gap-4 lg:grid-cols-[minmax(14rem,1fr)_minmax(0,2fr)]">
        <section
          className="min-w-0 overflow-hidden rounded-plate border border-border bg-surface"
          aria-labelledby="evidence-papers-heading"
        >
          <div className="flex items-center justify-between gap-2 border-b border-border p-4">
            <h2 id="evidence-papers-heading" className="type-subhead text-text">
              Study papers
            </h2>
            <span className="type-caption text-text-muted">
              {papers.length} {papers.length === 1 ? "paper" : "papers"}
            </span>
          </div>
          {papers.length > 0 && (
            <div className="flex flex-col gap-2 border-b border-border p-3">
              <Field id="evidence-filter" label="Filter papers">
                <Input
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Title, author, year or identifier"
                />
              </Field>
              <Field id="evidence-sort" label="Sort papers">
                <Select
                  value={sort}
                  onValueChange={setSort}
                  options={SORT_OPTIONS}
                />
              </Field>
            </div>
          )}
          {paperRequest.error && (
            <Notice kind="problem" className="m-3">
              Could not refresh study papers.{" "}
              <Button variant="subtle" size="sm" onClick={paperRequest.reload}>
                Try again
              </Button>
            </Notice>
          )}
          <div
            ref={paperList}
            tabIndex={0}
            role="region"
            aria-label="Study paper list"
            className="max-h-[var(--library-pane-h)] overflow-y-auto overscroll-contain"
          >
            {initialLoading ? (
              <p role="status" className="p-4 type-body text-text-muted">
                Loading study papers…
              </p>
            ) : visible.length > 0 ? (
              <ul aria-label="Study papers" className="divide-y divide-border">
                {visible.map((paper) => (
                  <li key={paper.paperRef}>
                    <button
                      type="button"
                      onClick={() => select(paper.paperRef)}
                      aria-current={
                        selected === paper.paperRef ? "true" : undefined
                      }
                      className={cn(
                        "flex w-full flex-col gap-1 p-4 text-left transition-colors duration-fast hover:bg-zone-9",
                        selected === paper.paperRef && "bg-zone-9",
                      )}
                    >
                      <span className="line-clamp-2 type-body font-medium text-text">
                        {paper.title || "Untitled paper"}
                      </span>
                      <span className="type-caption text-text-muted">
                        {[(paper.authors ?? []).join(", "), paper.year]
                          .filter(Boolean)
                          .join(" · ") || "Bibliographic details unavailable"}
                      </span>
                      {paper.links.length > 0 && (
                        <span className="type-caption text-text-muted">
                          {paper.links.length} protocol{" "}
                          {paper.links.length === 1 ? "link" : "links"}
                        </span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="flex flex-col gap-2 p-4 type-body text-text-muted">
                <p>
                  {paperRequest.error && !paperRequest.data
                    ? "Study papers are unavailable."
                    : needle
                      ? "No study papers match this filter."
                      : "No papers in this study yet."}
                </p>
                {needle ? (
                  <Button
                    size="sm"
                    variant="subtle"
                    onClick={() => setQuery("")}
                  >
                    Clear filter
                  </Button>
                ) : (
                  !paperRequest.error && (
                    <p className="type-note">
                      {canEdit
                        ? "Add a paper above, or accept a recommendation in Setup."
                        : "Papers added to this study will appear here."}
                    </p>
                  )
                )}
              </div>
            )}
          </div>
        </section>

        <aside
          aria-label="Paper details"
          className="min-w-0 rounded-plate border border-border bg-surface p-4"
        >
          {detail ? (
            <>
              <div className="flex items-start justify-between gap-3">
                <h2
                  ref={heading}
                  tabIndex={-1}
                  className="type-subhead break-words text-text"
                >
                  {detail.title || "Untitled paper"}
                </h2>
                <Button
                  size="icon-sm"
                  variant="ghost"
                  aria-label="Close paper details"
                  onClick={() => {
                    setSelected(null);
                    paperList.current?.focus();
                  }}
                >
                  <X aria-hidden />
                </Button>
              </div>
              <p className="mt-2 type-note text-text-muted">
                {[
                  (detail.authors ?? []).join(", "),
                  detail.year,
                  selectedPaper?.venue,
                ]
                  .filter(Boolean)
                  .join(" · ") || "Bibliographic details unavailable"}
              </p>
              <p className="mt-1 type-caption text-text-muted">
                {paperIdentifier(
                  selectedPaper ?? { paperRef: detail.paperRef },
                ) ??
                  (selectedPaper?.hasFullText
                    ? "Uploaded PDF"
                    : "Library paper")}
                {detail.citationCount != null
                  ? ` · ${detail.citationCount} citations`
                  : ""}
              </p>
              {sourceHref && (
                <a
                  href={sourceHref}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-3 inline-flex items-center gap-1 type-control text-accent underline underline-offset-4"
                >
                  <ExternalLink className="size-4" aria-hidden /> Open source
                </a>
              )}
              <div className="mt-4 border-t border-border pt-4">
                <h3
                  id="evidence-abstract-heading"
                  className="type-label text-text"
                >
                  Abstract
                </h3>
                <div
                  tabIndex={0}
                  role="region"
                  aria-labelledby="evidence-abstract-heading"
                  className="mt-2 max-h-[var(--library-pane-h)] overflow-y-auto overscroll-contain"
                >
                  <p className="max-w-reading whitespace-pre-line break-words type-body text-text-muted">
                    {detail.abstract ||
                      "The source has not supplied an abstract for this paper."}
                  </p>
                </div>
              </div>
              {!inStudy && (
                <div className="mt-4 flex flex-col items-start gap-2 border-t border-border pt-4">
                  <p className="type-note text-text-muted">
                    Related paper. It is not yet part of this study.
                  </p>
                  {canEdit && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={Boolean(pending)}
                      onClick={() =>
                        void mutate(
                          "Adding related paper…",
                          () =>
                            studyApi.addPaperFromGraph(
                              studyId,
                              detail.paperRef,
                            ),
                          () => "Related paper added to this study.",
                        )
                      }
                    >
                      <Plus aria-hidden /> Add to study
                    </Button>
                  )}
                </div>
              )}
              {selectedPaper && (
                <div className="mt-4 flex flex-col gap-3 border-t border-border pt-4">
                  {canEdit ? (
                    <>
                      <Field
                        id="protocol-links"
                        label="Protocol links"
                        hint="Separate protocol identifiers with commas. For example: RQ-1, RQ-2."
                      >
                        <Input
                          value={linkDraft}
                          disabled={Boolean(pending)}
                          onChange={(event) =>
                            setLinkDrafts((drafts) => ({
                              ...drafts,
                              [selectedPaper.paperRef]: event.target.value,
                            }))
                          }
                          placeholder="e.g. RQ-1"
                        />
                      </Field>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={Boolean(pending) || !linksChanged}
                          onClick={() =>
                            void mutate(
                              "Saving protocol links…",
                              () =>
                                studyApi.setPaperLinks(
                                  studyId,
                                  selectedPaper.paperRef,
                                  targetsOf(linkDraft),
                                ),
                              (result) => {
                                setLinkDrafts((drafts) => ({
                                  ...drafts,
                                  [selectedPaper.paperRef]:
                                    result.links.join(", "),
                                }));
                                return "Protocol links saved.";
                              },
                            )
                          }
                        >
                          Save links
                        </Button>
                        <Button
                          size="sm"
                          variant="subtle"
                          disabled={Boolean(pending)}
                          onClick={() => setConfirmRemove(true)}
                        >
                          <Trash2 aria-hidden /> Remove paper
                        </Button>
                      </div>
                      {confirmRemove && (
                        <div className="flex flex-col gap-2 rounded-control border border-border p-3">
                          <p className="type-note text-text">
                            Remove this paper and its protocol links from the
                            study?
                          </p>
                          <div className="flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              variant="danger"
                              disabled={Boolean(pending)}
                              onClick={() => void removePaper()}
                            >
                              Remove from study
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={Boolean(pending)}
                              onClick={() => setConfirmRemove(false)}
                            >
                              Cancel
                            </Button>
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <>
                      <h3 className="type-label text-text">Protocol links</h3>
                      <p className="type-note text-text-muted">
                        {selectedPaper.links.join(", ") ||
                          "No protocol links yet."}
                      </p>
                    </>
                  )}
                </div>
              )}
            </>
          ) : (
            <div className="flex flex-col gap-2 py-4">
              <h2 className="type-subhead text-text">
                Read and connect a paper
              </h2>
              <p className="type-body text-text-muted">
                Select a study paper to read its abstract and protocol links.
                Select a related paper in the map to inspect it before adding
                it.
              </p>
            </div>
          )}
        </aside>
      </div>

      <section
        className="min-w-0 rounded-plate border border-border bg-surface p-4"
        aria-labelledby="evidence-map-heading"
      >
        <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 id="evidence-map-heading" className="type-subhead text-text">
              Literature map
            </h2>
            <p className="mt-1 type-note text-text-muted">
              Explore references, later citations and similar work. Selecting a
              paper opens its details above.
            </p>
          </div>
          {pendingPaper && (
            <p role="status" className="type-note text-text-muted">
              Finding related literature…
            </p>
          )}
        </div>
        {graphRequest.error && (
          <Notice kind="problem">
            Could not refresh the literature map.{" "}
            <Button variant="subtle" size="sm" onClick={graphRequest.reload}>
              Try again
            </Button>
          </Notice>
        )}
        {graphRequest.loading && !graph ? (
          <p role="status" className="py-4 type-body text-text-muted">
            Loading the literature map…
          </p>
        ) : graph ? (
          <Constellation graph={graph} selected={selected} onSelect={select} />
        ) : null}
      </section>
    </Surface>
  );
}
