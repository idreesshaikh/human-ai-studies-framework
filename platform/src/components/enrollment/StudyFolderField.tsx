import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
    <div className="flex flex-col gap-2 rounded-input border border-border bg-bg p-3">
      <Label htmlFor="study-folder">Study folder</Label>
      <p className="type-caption text-text-muted">
        What each link opens in the participant&apos;s VS Code. Type a path that
        exists on their computers, or upload a zip of the folder.
      </p>
      <div className="flex gap-2">
        <Input
          id="study-folder"
          placeholder="/home/participant/study-task"
          value={pathText}
          onChange={(e) => setPathText(e.target.value)}
        />
        <Button size="sm" variant="subtle" disabled={busy} onClick={savePath}>
          Save path
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <input
          ref={fileInput}
          type="file"
          accept=".zip,application/zip"
          className="sr-only"
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
        <p className="type-caption text-text-muted" aria-live="polite">
          {describeWorkspace(workspace)}
        </p>
      )}
      {workspace?.kind === null && (
        <Notice kind="note">
          Without a study folder, participants connect but VS Code opens nothing
          for them.
        </Notice>
      )}
      {error && <Notice kind="problem">{error}</Notice>}
    </div>
  );
}
