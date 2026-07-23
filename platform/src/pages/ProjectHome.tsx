import { useNavigate, Link, useParams } from "react-router-dom";
import { useState } from "react";
import { FlaskConical, Users, Plus } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/shell/EmptyState";
import { useApi, useSession } from "@/lib/session";
import { useAuth } from "@/lib/auth.tsx";
import { useAsync } from "@/lib/useAsync";
import { memberLabel } from "@/lib/memberLabel";
import { ApiError } from "@/lib/api.ts";

/* Project home: its studies, and a preview of who's on the team. */
export function ProjectHome() {
  const api = useApi();
  const { refresh } = useSession();
  const { user } = useAuth();
  const navigate = useNavigate();
  const { slug = "" } = useParams();
  const { data, loading, error } = useAsync(() => api.projectHome(slug), [api, slug]);
  const [studyName, setStudyName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  const newStudy = async () => {
    if (!studyName.trim()) return;
    setCreating(true);
    setCreateError("");
    try {
      const study = await api.createStudy(slug, studyName);
      // Refresh `me` so the new study's membership/role resolves immediately —
      // otherwise role-gated controls (e.g. Mint links) stay hidden until an
      // unrelated refresh fires.
      await refresh();
      navigate(`/p/${slug}/studies/${study.id}`);
    } catch (e) {
      setCreateError(e instanceof ApiError ? e.message : "Could not create the study.");
      setCreating(false);
    }
  };

  if (loading) return <p className="p-6 text-sm text-text-muted">Loading…</p>;
  if (error) return <p className="p-6 text-sm text-unsourced">{error}</p>;
  if (!data) return null;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 p-6">
      <div>
        <h1 className="font-serif text-3xl font-medium tracking-tight text-text">{data.name}</h1>
        <p className="text-sm text-text-muted">/{data.slug}</p>
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="flex items-center gap-2 text-sm font-medium text-text">
          <FlaskConical className="size-4 text-text-muted" aria-hidden /> Studies
        </h2>
        <Card>
          <CardContent className="flex flex-col gap-2 p-4">
            <div className="flex gap-2">
              <Input
                placeholder="Name a new study…"
                value={studyName}
                onChange={(e) => setStudyName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && newStudy()}
                aria-label="New study name"
              />
              <Button onClick={newStudy} disabled={!studyName.trim() || creating} data-agent="new-study">
                <Plus className="size-4" aria-hidden />
                {creating ? "Creating…" : "Create"}
              </Button>
            </div>
            {createError && <p className="text-sm text-unsourced">{createError}</p>}
          </CardContent>
        </Card>
        {data.studies.length === 0 ? (
          <EmptyState line="Research goes better with a study. Start one above." />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {data.studies.map((st) => (
              <Link key={st.id} to={`/p/${slug}/studies/${st.id}`}>
                <Card className="transition-colors duration-fast hover:border-accent">
                  <CardContent className="flex items-center justify-between p-4">
                    <span className="font-medium text-text">{st.id}</span>
                    <Badge variant="outline">{st.phase}</Badge>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-sm font-medium text-text">
            <Users className="size-4 text-text-muted" aria-hidden /> Team
          </h2>
          <Link to={`/p/${slug}/members`} className="text-xs text-accent hover:underline">
            Manage members
          </Link>
        </div>
        <div className="flex flex-wrap gap-2">
          {data.members.map((m) => (
            <span
              key={m.identitySub}
              className="flex items-center gap-2 rounded-chip border border-border px-2 py-1 text-xs text-text"
            >
              <Avatar name={memberLabel(m, user)} className="size-5" />
              {memberLabel(m, user)}
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}
