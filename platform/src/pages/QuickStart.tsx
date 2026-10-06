import { useState } from "react";
import { Field } from "@/components/ui/field";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useApi, useSession } from "@/lib/session";
import { ApiError } from "@/lib/api";
import { NAME_MAX_LENGTH } from "@/lib/uiText";
import { browserNameStore, rememberStudyName } from "@/lib/studyNames";

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
      rememberStudyName(browserNameStore(), study.id, title);

      await refresh();

      const opening = question.trim();
      navigate(`/p/${project.slug}/studies/${study.id}`, {
        state: { opening },
      });
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
    <div className="mx-auto flex max-w-reading flex-col gap-6 p-gutter">
      <div className="flex w-full flex-col gap-6">
        <div>
          <h1 className="type-title text-text">Start a developer study</h1>
          <p className="type-body mt-1 text-pretty text-text-muted">
            Configure a task-based human–AI study, then run it in VS Code.
          </p>
          <p className="type-note mt-3 text-pretty text-text-muted">
            Phoenix supports coding-task comparisons with AI-assisted and unassisted
            conditions. It is not an exam, classroom, clinical, marketing, or general survey
            tool.
          </p>
        </div>

        <Card>
          <CardContent className="flex flex-col gap-4 p-4">
            <Field id="study-title" label="Study name" hint={`Up to ${NAME_MAX_LENGTH} characters.`}>
              <Input
                placeholder="e.g. AI-assisted code review"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={NAME_MAX_LENGTH}
                disabled={creating}
              />
            </Field>

            <Field
              id="opening-thought"
              label="Study brief"
              hint="Name the coding task, AI comparison, and outcome you want to capture. One message is enough; Phoenix extracts the explicit choices and leaves only genuinely missing details open."
            >
              <Textarea
                autoGrow
                rows={3}
                placeholder="Task, people, AI change, measures"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                disabled={creating}
              />
            </Field>

            {error && <Notice kind="problem">{error}</Notice>}

            <Button
              onClick={create}
              disabled={!title.trim() || creating}
              className="mt-2"
              aria-describedby={title.trim() ? undefined : "configure-hint"}
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

            {!title.trim() && (
              <p id="configure-hint" className="type-note text-center text-text-muted">
                Name the study to continue.
              </p>
            )}

            <p className="type-note text-center text-text-muted">
              Studies live in a personal workspace. You can share them with others later.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
