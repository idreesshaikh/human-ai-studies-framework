import { useEffect, useRef, useState } from "react";
import { Field } from "@/components/ui/field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Notice } from "@/components/ui/notice";
import { useApi } from "@/lib/session";
import { ApiError } from "@/lib/api";
import {
  describeWorkspace,
  workspaceFileProblem,
  workspacePathProblem,
  type StudyWorkspace,
} from "@/lib/workspaceSetting";

/* The folder a minted link opens on the participant's machine: a path they
 * already have, or a zip the extension downloads and unpacks. Set once for the
 * study; every link minted afterwards opens it. */
export function StudyFolderField({ studyId }: { studyId: string }) {
  const api = useApi();
  const [workspace, setWorkspace] = useState<StudyWorkspace | null>(null);
  const [pathText, setPathText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    void api
      .getWorkspace(studyId)
      .then((w) => {
        setWorkspace(w);
        if (w.kind === "path") setPathText(w.path);
      })
      .catch(() => setWorkspace(null));
  }, [api, studyId]);

  const run = async (action: () => Promise<StudyWorkspace>) => {
    setBusy(true);
    setError(null);
    try {
      const next = await action();
      setWorkspace(next);
      setPathText(next.kind === "path" ? next.path : "");
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : "Could not save the study folder. Check your connection and try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  const savePath = () => {
    const problem = workspacePathProblem(pathText);
    if (problem) return setError(problem);
    void run(() => api.setWorkspacePath(studyId, pathText.trim()));
  };

  const pickFile = (file: File | undefined) => {
    if (!file) return;
    const problem = workspaceFileProblem(file);
    if (problem) return setError(problem);
    void run(() => api.uploadWorkspaceZip(studyId, file));
  };

  return (
    <div className="flex min-w-0 flex-col gap-2 border-t border-border pt-4">
      <Field
        id="study-folder"
        label="Study folder"
        className="min-w-0"
        hint="Open a folder already on participants’ computers, or distribute a zip."
      >
        <Input
          aria-describedby="study-folder-status"
          placeholder="/home/participant/study-task"
          value={pathText}
          onChange={(e) => setPathText(e.target.value)}
        />
      </Field>
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="subtle" disabled={busy} onClick={savePath}>
          Save path
        </Button>
        <input
          ref={fileInput}
          type="file"
          accept=".zip,application/zip"
          className="sr-only"
          tabIndex={-1}
          aria-label="Upload a zip of the study folder"
          onChange={(e) => {
            pickFile(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        <Button
          size="sm"
          variant="outline"
          disabled={busy}
          onClick={() => fileInput.current?.click()}
        >
          Upload zip…
        </Button>
        {workspace && workspace.kind !== null && (
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => void run(() => api.clearWorkspace(studyId))}>
            Clear
          </Button>
        )}
      </div>
      {workspace && (
        <p id="study-folder-status" className="type-note text-text-muted" aria-live="polite">
          {describeWorkspace(workspace)}
        </p>
      )}
      {error && <Notice kind="problem">{error}</Notice>}
    </div>
  );
}
