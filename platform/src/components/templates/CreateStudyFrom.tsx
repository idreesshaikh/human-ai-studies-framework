import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Loader2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useApi, useSession } from "@/lib/session";
import { useAuth } from "@/lib/auth.tsx";
import { ApiError } from "@/lib/api.ts";
import { hasRole } from "@/lib/capabilities";
import { signInHref } from "@/lib/returnTo";

export function CreateStudyFrom({
  protocol,
  label,
}: {

  protocol: Record<string, unknown>;

  label: string;
}) {
  const api = useApi();
  const { refresh } = useSession();
  const { hasCredential } = useAuth();
  const signedOut = !hasCredential;
  const navigate = useNavigate();
  const { pathname, search } = useLocation();
  const [projects, setProjects] = useState<{ slug: string; name: string }[] | null>(
    null,
  );
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  useEffect(() => {

    if (signedOut) return;
    api
      .listProjects()
      .then((ps) => {

        const writable = ps.filter((p) => hasRole(p.role, "contribute"));
        setProjects(writable.map((p) => ({ slug: p.slug, name: p.name })));
        setSlug((cur) => cur || writable[0]?.slug || "");
      })
      .catch(() => setProjects([]));
  }, [api, signedOut]);

  const create = async () => {
    if (!slug || !name.trim() || creating) return;
    setCreating(true);
    setCreateError("");
    try {
      const study = await api.createStudy(slug, name.trim(), protocol);

      await refresh();
      navigate(`/p/${slug}/studies/${study.id}`);
    } catch (e) {
      setCreateError(
        e instanceof ApiError && e.fromServer
          ? e.message
          : "Couldn't create the study. Check the connection and try again.",
      );
      setCreating(false);
    }
  };

  return (
    <div className="mt-4 border-t border-border pt-3">

      <p className="type-body text-text-muted">{label}</p>

      {signedOut ? (
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <p className="type-caption text-text-muted">
            Sign in to keep this  -  a study has to live in one of your projects.
          </p>
          <Button asChild size="sm" variant="outline">
            <Link to={signInHref(pathname + search)}>Sign in</Link>
          </Button>
        </div>
      ) : projects === null ? (
        <p className="mt-2 flex items-center gap-2 type-caption text-text-muted">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Loading your
          projects…
        </p>
      ) : projects.length === 0 ? (
        <p className="mt-2 type-caption text-text-muted">
          No project to put it in yet  -  create one first.
        </p>
      ) : (
        <div className="mt-2 flex flex-wrap gap-2">
          <label className="sr-only" htmlFor="seed-project">
            Project
          </label>
          <Select
            value={slug}
            onValueChange={setSlug}
            options={projects.map((p) => ({ value: p.slug, label: p.name }))}
            placeholder="Choose project…"
            className="w-auto min-w-40"
          />
          <Input
            className="min-w-0 flex-1 basis-48"
            placeholder="Name the study…"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") create();
              if (e.key === "Escape") setName("");
            }}
            aria-label="New study name"
          />
          <Button
            size="sm"
            disabled={!slug || !name.trim() || creating}
            onClick={create}
          >
            {creating ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Plus className="size-4" aria-hidden />
            )}
            Create study
          </Button>
        </div>
      )}
      {createError && (
        <p role="alert" className="mt-2 type-caption text-critical">
          {createError}
        </p>
      )}
    </div>
  );
}
