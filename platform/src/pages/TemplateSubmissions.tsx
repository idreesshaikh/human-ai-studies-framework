import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronLeft, Loader2, Check, X, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/shell/EmptyState";
import {
  templatesApi,
  type TemplateSubmission,
  type TemplateSubmissionDetail,
} from "@/lib/templatesApi";

/* The template-submission review queue (FR-TPL-5). A mined draft and a
 * hand-authored template arrive as the same thing here — a `pending` row a
 * human approves or rejects. Approval is what writes the YAML into the
 * registry; until then nothing is added, so a proposal is reviewed as a
 * proposal. Owners see every submission; everyone else sees their own. */
export function TemplateSubmissions() {
  const [rows, setRows] = useState<TemplateSubmission[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [detail, setDetail] = useState<TemplateSubmissionDetail | null>(null);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(() => {
    templatesApi
      .submissions()
      .then((d) => setRows(d.submissions))
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Couldn't load submissions."),
      );
  }, []);

  useEffect(load, [load]);

  useEffect(() => {
    if (openId === null) {
      setDetail(null);
      setComment("");
      return;
    }
    templatesApi
      .submission(openId)
      .then(setDetail)
      .catch(() => setDetail(null));
  }, [openId]);

  const decide = async (id: number, status: "approved" | "rejected") => {
    if (busy) return;
    setBusy(true);
    setNotice(null);
    try {
      await templatesApi.decideSubmission(id, status, comment.trim());
      setOpenId(null);
      setNotice(
        status === "approved"
          ? "Approved. The template is now in the registry."
          : "Rejected.",
      );
      load();
    } catch (e) {
      setNotice(
        e instanceof Error ? e.message : "Couldn't record that decision.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-work flex-col gap-section p-gutter">
      <div>
        <Link
          to="/repertoire"
          className="type-label flex items-center gap-1 text-text-muted hover:text-text"
        >
          <ChevronLeft className="size-4" aria-hidden /> Repertoire
        </Link>
        <h1 className="type-title mt-1 text-text">Template submissions</h1>
        <p className="type-body mt-1 max-w-reading text-text-muted">
          Proposals for the registry, from researchers and from the corpus
          miner. Approving one writes its YAML into the registry; until then it
          is only a proposal.
        </p>
      </div>

      {error && <Notice kind="problem">{error}</Notice>}
      {notice && <Notice kind="note">{notice}</Notice>}

      {rows === null && !error ? (
        <p className="flex items-center gap-2 type-body text-text-muted">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Loading
          submissions…
        </p>
      ) : rows && rows.length === 0 ? (
        <EmptyState line="No template submissions yet." />
      ) : (
        <ul className="flex flex-col gap-2">
          {rows?.map((r) => (
            <li key={r.id}>
              <div className="flex flex-wrap items-center gap-2 rounded-card border border-border bg-surface p-3">
                <button
                  type="button"
                  onClick={() => setOpenId(openId === r.id ? null : r.id)}
                  className="flex min-w-0 flex-1 flex-col items-start gap-1 text-left"
                >
                  <span className="type-subhead text-text">{r.name}</span>
                  <span className="flex flex-wrap items-center gap-2 type-caption text-text-muted">
                    <Badge
                      variant={r.source === "mined" ? "outline" : "grounded"}
                    >
                      {r.source === "mined" ? (
                        <>
                          <Sparkles className="size-3" aria-hidden /> mined
                        </>
                      ) : (
                        "researcher"
                      )}
                    </Badge>
                    <span>{r.status}</span>
                    {r.reviewComment && <span>· {r.reviewComment}</span>}
                  </span>
                </button>
                {r.status === "pending" && (
                  <Button
                    size="sm"
                    variant="subtle"
                    onClick={() => setOpenId(openId === r.id ? null : r.id)}
                  >
                    Review
                  </Button>
                )}
              </div>

              {openId === r.id && (
                <div className="mt-2 rounded-card border border-border bg-surface-raised p-3">
                  {detail && detail.id === r.id ? (
                    <>
                      <pre className="max-h-72 overflow-auto rounded-input border border-border bg-bg p-3 type-quantity text-text">
                        {detail.templateYaml}
                      </pre>
                      {detail.status === "pending" && (
                        <div className="mt-3 flex flex-col gap-2">
                          <textarea
                            className="w-full rounded-input border border-border bg-bg p-2 type-body text-text"
                            rows={2}
                            placeholder="Review comment (optional for approval, useful for rejection)"
                            value={comment}
                            onChange={(e) => setComment(e.target.value)}
                            aria-label="Review comment"
                          />
                          <div className="flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              onClick={() => void decide(r.id, "approved")}
                              disabled={busy}
                            >
                              <Check className="size-4" aria-hidden /> Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => void decide(r.id, "rejected")}
                              disabled={busy}
                            >
                              <X className="size-4" aria-hidden /> Reject
                            </Button>
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <p className="flex items-center gap-2 type-caption text-text-muted">
                      <Loader2 className="size-4 animate-spin" aria-hidden />
                      Loading YAML…
                    </p>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
