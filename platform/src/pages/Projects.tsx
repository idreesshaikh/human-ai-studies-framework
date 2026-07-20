import { useState } from "react";
import { Link } from "react-router-dom";
import { FolderOpen, Plus } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/shell/EmptyState";
import { useApi } from "@/lib/session";
import { useAsync } from "@/lib/useAsync";
import { ROLE_LABELS } from "@/lib/capabilities.ts";
import { ApiError } from "@/lib/api.ts";

/* The project list, and the one place a project is created. */
export function Projects() {
  const api = useApi();
  const { data, loading, error, reload } = useAsync(() => api.listProjects(), [api]);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  const create = async () => {
    if (!name.trim()) return;
    setCreating(true);
    setCreateError("");
    try {
      await api.createProject(name);
      setName("");
      reload();
    } catch (e) {
      setCreateError(e instanceof ApiError ? e.message : "Could not create the project.");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl font-medium tracking-tight text-text">Projects</h1>
          <p className="text-sm text-text-muted">The rooms your studies live in.</p>
        </div>
      </div>

      <Card>
        <CardContent className="flex flex-col gap-2 p-4">
          <div className="flex gap-2">
            <Input
              placeholder="Name a new project…"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && create()}
              aria-label="New project name"
            />
            <Button onClick={create} disabled={!name.trim() || creating}>
              <Plus aria-hidden /> Create
            </Button>
          </div>
          {createError && <p className="text-sm text-unsourced">{createError}</p>}
        </CardContent>
      </Card>

      {loading && <p className="text-sm text-text-muted">Loading projects…</p>}
      {error && <p className="text-sm text-unsourced">{error}</p>}
      {data && data.length === 0 && (
        <EmptyState line="Research goes better with company. Create your first project above." />
      )}
      {data && data.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {data.map((p) => (
            <Link key={p.slug} to={`/p/${p.slug}`} className="group">
              <Card className="transition-colors duration-fast group-hover:border-accent">
                <CardContent className="flex items-center gap-3 p-4">
                  <FolderOpen className="size-5 text-text-muted" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-text">{p.name}</p>
                    <p className="truncate text-xs text-text-muted">/{p.slug}</p>
                  </div>
                  <Badge variant="outline">{ROLE_LABELS[p.role]}</Badge>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
