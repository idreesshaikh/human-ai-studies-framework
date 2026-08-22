import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Input } from "@/components/ui/input";
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
          <h1 className="type-title text-text">Start your study</h1>
          <p className="type-body mt-1 text-text-muted">
            Describe your research idea. We'll work through the design with you.
          </p>
        </div>

        <Card>
          <CardContent className="flex flex-col gap-4 p-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="study-title">Study name</Label>
              <Input
                id="study-title"
                placeholder="My research question"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={creating}
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="opening-thought">Your initial thought</Label>
              <p className="type-caption text-text-muted">
                What do you want to find out?
              </p>
              <Input
                id="opening-thought"
                placeholder="e.g., Does code review catch security issues?"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                disabled={creating}
              />
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
                "Start designing"
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
