import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useApi, useSession } from "@/lib/session";
import { ApiError } from "@/lib/api";

/* Quick-start flow: describe a study and create it in an implicit personal
 * workspace project. No project naming step  -  it's created silently. */
export function QuickStart() {
  const api = useApi();
  const { refresh } = useSession();
  const navigate = useNavigate();

  const [title, setTitle] = useState("");
  const [question, setQuestion] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const create = async () => {
    if (!title.trim() || creating) return;
    setCreating(true);
    setError("");

    try {
      /* Create in personal project. The API should handle creating the
       * implicit personal project if it doesn't exist. */
      const project = await api.createProject("Personal");
      const study = await api.createStudy(project.slug, title);

      await refresh();

      const opening = question.trim();
      navigate(`/p/${project.slug}/studies/${study.id}`, { state: { opening } });
    } catch (e) {
      setError(
        e instanceof ApiError && e.fromServer
          ? e.message
          : "Could not create the study. Try again in a moment.",
      );
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-dvh flex-col items-center justify-center gap-6 px-4 py-12">
      <div className="w-full max-w-96 flex flex-col gap-6">
        <div className="text-center">
          <h1 className="type-title text-text">Start a developer study</h1>
          <p className="type-body mt-1 text-text-muted">
            Configure a task-based human–AI study, then run it in VS Code.
          </p>
        </div>

        <Card>
          <CardContent className="flex flex-col gap-4 p-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="study-title">Study name</Label>
              <Input
                id="study-title"
                placeholder="e.g., AI-assisted code review"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={creating}
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="opening-thought">Study brief</Label>
              <p className="type-caption text-text-muted">
                Name the coding task, AI comparison, and outcome you want to capture.
              </p>
              <Textarea
                id="opening-thought"
                placeholder="Paste the whole brief here: the coding task, who will do it, what AI changes, and what you want to measure."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                disabled={creating}
                aria-describedby="study-brief-hint"
              />
              <p id="study-brief-hint" className="type-caption text-text-muted">
                You can write it in one message. PHOENIX will extract the explicit choices and leave only genuinely missing details open.
              </p>
            </div>

            {error && <Notice kind="problem">{error}</Notice>}

            <Button
              onClick={create}
              disabled={!title.trim() || creating}
              className="mt-2"
            >
              {creating ? (
                <>
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                  Creating…
                </>
              ) : (
                "Configure study"
              )}
            </Button>

            <p className="type-caption text-center text-text-muted">
              Studies live in a personal workspace. You can share them with others later.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
