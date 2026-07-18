import { Link, useParams } from "react-router-dom";
import { FlaskConical, Users } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar } from "@/components/ui/avatar";
import { EmptyState } from "@/components/shell/EmptyState";
import { useApi } from "@/lib/session";
import { useAsync } from "@/lib/useAsync";

/* Project home: its studies, and a preview of who's on the team. */
export function ProjectHome() {
  const api = useApi();
  const { slug = "" } = useParams();
  const { data, loading, error } = useAsync(() => api.projectHome(slug), [api, slug]);

  if (loading) return <p className="p-6 text-sm text-text-muted">Loading…</p>;
  if (error) return <p className="p-6 text-sm text-unsourced">{error}</p>;
  if (!data) return null;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 p-6">
      <div>
        <h1 className="font-display text-2xl text-text">{data.name}</h1>
        <p className="text-sm text-text-muted">/{data.slug}</p>
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="flex items-center gap-2 text-sm font-medium text-text">
          <FlaskConical className="size-4 text-text-muted" aria-hidden /> Studies
        </h2>
        {data.studies.length === 0 ? (
          <EmptyState line="No studies yet — open the designer to talk one into existence." />
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
              <Avatar name={m.identitySub} className="size-5" />
              {m.identitySub}
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}
