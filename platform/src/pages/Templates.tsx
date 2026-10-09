import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { BookOpen, Loader2, Info, MessageSquareText } from "lucide-react";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Notice } from "@/components/ui/notice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/shell/EmptyState";
import { Confidence } from "@/components/conversation/Confidence";
import {
  templatesApi,
  type RepertoireEntry,
  type CorpusStatus,
  type FeaturedTemplate,
} from "@/lib/templatesApi";
import { OfflineError } from "@/lib/studyApi";
import { useApi, useSession } from "@/lib/session";
import { useAuth } from "@/lib/auth.tsx";
import { ApiError } from "@/lib/api";
import { signInHref } from "@/lib/returnTo";
import { plainMatchReason } from "@/lib/uiText";
import { hasRole } from "@/lib/capabilities";
import { publicPaperReference } from "@/lib/paperReference";

const BAND_COPY: Record<RepertoireEntry["band"], string> = {
  common: "Widely used across the corpus",
  established: "Well established in the corpus",
  rare: "Rarely used, novel territory",
};

function humanizeDesignType(value: string): string {
  return value
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function Templates() {
  const [entries, setEntries] = useState<RepertoireEntry[] | null>(null);
  const [corpus, setCorpus] = useState<CorpusStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [featured, setFeatured] = useState<FeaturedTemplate[]>([]);
  const [starting, setStarting] = useState<string | null>(null);

  const api = useApi();
  const { me, loading: meLoading, refresh } = useSession();
  const { hasCredential } = useAuth();
  const signedOut = !hasCredential;
  const navigate = useNavigate();
  const { pathname, search } = useLocation();

  const [describe, setDescribe] = useState("");
  const [describeBusy, setDescribeBusy] = useState(false);
  const [describeError, setDescribeError] = useState("");

  async function studyProject() {
    return me?.memberships.find((membership) => hasRole(membership.role, "contribute"))?.projectSlug
      ?? (await api.createProject("Personal")).slug;
  }

  useEffect(() => {
    let active = true;
    void templatesApi.featured().then((items) => { if (active) setFeatured(items); })
      .catch(() => { if (active) setError("Could not load starting templates."); });
    return () => { active = false; };
  }, []);

  async function useTemplate(templateId: string, title: string) {
    if (starting || meLoading) return;
    setStarting(templateId);
    setError(null);
    try {
      const slug = await studyProject();
      const { protocol } = await templatesApi.instantiate(templateId, { title });
      const study = await api.createStudy(slug, title, protocol);
      await refresh().catch(() => {});
      navigate(`/p/${slug}/studies/${study.id}?tab=planning`);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Could not start this study.");
    } finally {
      setStarting(null);
    }
  }

  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    const load = () => {
      templatesApi
        .repertoire()
        .then((d) => {
          if (!active) return;
          setEntries(d.repertoire);
          setCorpus(d.corpus);
          if (d.corpus.state === "loading") {
            timer = window.setTimeout(load, 1200);
          }
        })
        .catch((e) => {
          if (!active) return;
          setError(
            e instanceof OfflineError
              ? "Start the middleware to browse templates."
              : "Couldn't load templates.",
          );
        });
    };
    load();
    return () => {
      active = false;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, []);

  const admitted = useMemo(
    () => (entries ?? []).filter((e) => e.admitted),
    [entries],
  );
  const held = useMemo(
    () => (entries ?? []).filter((e) => !e.admitted),
    [entries],
  );
  const corpusReady = corpus?.state === "ready";

  async function describeStudy() {
    const text = describe.trim();
    if (!text || describeBusy) return;
    setDescribeBusy(true);
    setDescribeError("");
    try {
      const slug = await studyProject();
      const title =
        text.length > 60 ? `${text.slice(0, 57).trimEnd()}…` : text;
      const study = await api.createStudy(slug, title);
      await refresh();
      navigate(`/p/${slug}/studies/${study.id}`, {
        state: { opening: text },
      });
    } catch (e) {
      setDescribeError(
        e instanceof ApiError && e.fromServer
          ? e.message
          : "Couldn't start the conversation. Try again in a moment.",
      );
    } finally {
      setDescribeBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-work flex-col gap-section p-gutter">
      <div>
        <h1 className="type-title text-text">Templates</h1>
        <p className="type-body mt-1 max-w-reading text-pretty text-text-muted">
          Start with a protocol or browse the full collection of design shapes
          and their references. No project needed to browse.
        </p>
        {entries && corpusReady && (
          <p className="mt-2 type-caption text-text-muted">
            <span className="type-quantity text-text">{admitted.length}</span> template
            {admitted.length === 1 ? "" : "s"} ready to use
            {held.length > 0 && (
              <>
                {" "}
                · <span className="type-quantity text-text-muted">{held.length}</span> held back (too rare)
              </>
            )}
          </p>
        )}
      </div>

      {error && (
        <Notice kind="problem">{error}</Notice>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="type-section text-text">Start a study</h2>
        <div className="grid gap-3 md:grid-cols-3">
          {featured.map((template) => (
            <div key={template.id} className="flex flex-col gap-3 rounded-plate border border-border bg-surface p-4">
              <h3 className="type-subhead text-text">{template.title}</h3>
              <p className="type-note text-text-muted">{template.description}</p>
              {signedOut ? <Button asChild size="sm" variant="outline"><Link to={signInHref(pathname + search)}>Sign in to use</Link></Button> :
                <Button size="sm" variant="outline" className="mt-auto" aria-busy={starting === template.id} disabled={meLoading || starting !== null} onClick={() => void useTemplate(template.id, template.title)}>{starting === template.id ? "Starting…" : "Use this template"}</Button>}
            </div>
          ))}
        </div>
      </section>

      {corpus && corpus.state !== "ready" && (
        <Notice kind={corpus.state === "error" ? "problem" : "note"}>
          {corpus.state === "error"
            ? `The literature index could not finish loading. ${corpus.error}`
            : corpus.state === "loading"
              ? `Indexing literature (${corpus.papers.toLocaleString()} of ${corpus.expected.toLocaleString()} papers). Design evidence will appear when indexing finishes.`
              : corpus.papers > 0
                ? `${corpus.papers.toLocaleString()} papers indexed. Design evidence will appear when indexing finishes. You can start with a template or describe your study.`
                : "No literature indexed yet. You can start with a template or describe your study."}
        </Notice>
      )}


      <section className="flex flex-col gap-2 rounded-card border border-border bg-surface p-4">
          <h2 className="type-subhead flex items-center gap-2 text-text">
            <MessageSquareText className="size-4" aria-hidden />
            Describe your study instead
          </h2>
          <p className="type-note text-text-muted">
            Not sure which template fits? Describe the study in plain language
            and the assistant works the design out with you.
          </p>
          <div className="flex flex-wrap gap-2">
            <Input
              value={describe}
              onChange={(e) => setDescribe(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void describeStudy()}
              placeholder="Describe the study in a sentence"
              aria-label="Describe your study"
              className="min-w-0 flex-1 basis-56"
            />
            {signedOut ? (
              <Button asChild size="field">
                <Link to={signInHref(pathname + search)}>Sign in to start</Link>
              </Button>
            ) : (
              <Button
                size="field"
                onClick={() => void describeStudy()}
                disabled={meLoading || !describe.trim() || describeBusy}
              >
                {describeBusy ? "Starting conversation…" : "Start conversation"}
              </Button>
            )}
          </div>
          {describeError && (
            <p role="alert" className="type-note text-critical">
              {describeError}
            </p>
          )}
      </section>


      {entries === null && !error ? (
        <p className="flex items-center gap-2 type-body text-text-muted">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Ranking
          templates against the corpus…
        </p>
      ) : entries && !corpusReady ? null : entries && entries.length === 0 ? (
        <EmptyState line="No templates in the registry yet." />
      ) : (
        /* A grid, not a stack: alternatives to choose between line up as
           columns you can read across. Details open in a dialog, so nothing
           grows in place. */
        <section className="flex flex-col gap-2">
          <h2 className="type-subhead text-text">Study templates</h2>
          <p className="type-note text-text-muted">
            Open a card for its full description and its references.
          </p>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {admitted.map((entry) => (
              <ShapeCard
                key={entry.id}
                entry={entry}
                onDetail={() => setDetailId(entry.id)}
                onUse={() => void useTemplate(entry.id, entry.title)}
                canUse={!signedOut && Boolean(me?.memberships.length) && starting === null}
              />
            ))}
          </div>
        </section>
      )}

      {corpusReady && held.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="type-subhead flex items-center gap-1.5 text-text-muted">
            <Info className="size-4" aria-hidden /> Held back
          </h2>
          <p className="type-note text-text-muted">
            Too rare to propose without a strong source. Shown, not hidden: the
            reason is stated so you can judge it yourself.
          </p>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {held.map((entry) => (
              <div
                key={entry.id}
                className="rounded-plate border border-dashed border-unsourced p-3"
              >
                <p className="type-label font-semibold text-text">{entry.title}</p>
                <p className="type-note mt-0.5 text-text-muted">
                  {entry.admissionNote}
                </p>
                {!signedOut && <Button className="mt-3" variant="outline" size="sm" disabled={!me?.memberships.length || starting !== null} onClick={() => void useTemplate(entry.id, entry.title)}>Use this template</Button>}
              </div>
            ))}
          </div>
        </section>
      )}


      {detailId && entries && (
        <ShapeDetailPanel
          entry={entries.find((e) => e.id === detailId)!}
          onClose={() => setDetailId(null)}
        />
      )}
    </div>
  );
}

function ShapeCard({
  entry,
  onDetail,
  onUse,
  canUse,
}: {
  entry: RepertoireEntry;
  onDetail: () => void;
  onUse: () => void;
  canUse: boolean;
}) {
  return (
    <Card className="flex flex-col transition-colors duration-fast hover:border-control-edge">
      {/* Built to stack, not to span: the things that vary in length go down
        * the page and only the fixed-size marks sit across it. The text is
        * clamped so a shelf of cards stays comparable; the full text is a
        * click away in the detail panel. */}
      <CardContent className="flex flex-1 flex-col gap-3 p-4">
        <button
          type="button"
          onClick={onDetail}
          className="flex flex-col gap-2 text-left transition-colors duration-fast hover:text-accent"
          aria-label={`View details for ${entry.title}`}
        >
          <span className="type-subhead text-text">{entry.title}</span>
          <span className="type-caption line-clamp-4 text-text-muted">
            {entry.description}
          </span>
        </button>

        <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-2 pt-1">
          <SupportBadge entry={entry} />
          <Badge variant="outline">{humanizeDesignType(entry.designType)}</Badge>
        </div>
        <Button variant="outline" size="sm" disabled={!canUse} onClick={onUse}>Use this template</Button>
      </CardContent>
    </Card>
  );
}

/* Print the corpus count; explain its evidence band in the title. */
function SupportBadge({ entry }: { entry: RepertoireEntry }) {
  return (
    <span
      className="inline-flex items-center gap-1.5"
      title={`${BAND_COPY[entry.band]}: ${entry.support} corpus paper${
        entry.support === 1 ? "" : "s"
      } match: ${entry.signature.join(", ")}`}
    >
      <span className="type-caption text-text-muted">
        <span className="type-quantity text-text">{entry.support}</span> paper
        {entry.support === 1 ? "" : "s"}
      </span>
    </span>
  );
}


/* One template in full: description, design type and the papers behind it. */
function ShapeDetailPanel({
  entry,
  onClose,
}: {
  entry: RepertoireEntry;
  onClose: () => void;
}) {
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent wide>
        <DialogHeader>
          <DialogTitle>{entry.title}</DialogTitle>
          <DialogDescription>{BAND_COPY[entry.band]}</DialogDescription>
        </DialogHeader>

        <DialogBody className="space-y-4">
          <div>
            <h3 className="type-label font-semibold text-text">Description</h3>
            <p className="mt-2 type-body text-text">{entry.description}</p>
          </div>

          <div>
            <h3 className="type-label font-semibold text-text">Design type</h3>
            <p className="mt-2 type-body text-text">{humanizeDesignType(entry.designType)}</p>
          </div>

          <div>
            <h3 className="type-label flex items-center gap-2 font-semibold text-text">
              <BookOpen className="size-4" aria-hidden />
              References ({entry.references.length})
            </h3>
            <ul className="mt-2 space-y-2">
              {entry.references.map((ref) => (
                <li key={ref.ref} className="rounded-control border border-border p-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex min-w-0 flex-col gap-1">
                      <div className="flex items-center gap-2">
                        <Confidence value={ref.confidence ?? undefined} />
                        {ref.role !== "uses-this-design" && (
                          <span className="type-caption text-text-muted">
                            {ref.role.replace(/-/g, " ")}
                          </span>
                        )}
                      </div>
                      <p className="type-caption text-text">{ref.title}</p>
                      <p className="type-caption text-text-muted">{plainMatchReason(ref.matchReason)}</p>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
            {entry.unresolvedSources.length > 0 && (
              <p className="mt-2 type-note text-text-muted">
                Additional source: {entry.unresolvedSources
                  .map((source) => publicPaperReference(source) ?? "Source record")
                  .join(", ")}
              </p>
            )}
          </div>
        </DialogBody>
        <DialogFooter>
          <Button type="button" variant="outline" size="sm" onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
