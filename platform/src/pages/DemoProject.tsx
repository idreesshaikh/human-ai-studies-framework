import { Link } from "react-router-dom";
import { ArrowRight, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ConversationView } from "@/components/conversation/ConversationView";
import { useApi } from "@/lib/session";
import { useAsync } from "@/lib/useAsync";

/* The shared, read-only demo project everyone can open without an account.
 * It shows the finished article — a completed conversation — and points at
 * the study's report. */
export function DemoProject() {
  const api = useApi();
  const { data, loading } = useAsync(() => api.demo(), [api]);

  return (
    <div className="mx-auto flex min-h-full max-w-6xl flex-col gap-6 px-6 py-8">
      <header className="flex flex-wrap items-center gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h1 className="font-display text-2xl text-text">
              {loading ? "Demo project" : data?.projectName}
            </h1>
            <Badge variant="outline">
              <Eye className="size-3" aria-hidden /> read-only
            </Badge>
          </div>
          <p className="text-sm text-text-muted">
            Explore a completed study — the conversation, its grounded moves,
            and the protocol they compiled into. No account needed.
          </p>
        </div>
        <Button asChild>
          <Link to="/projects">
            Start your own <ArrowRight aria-hidden />
          </Link>
        </Button>
      </header>

      <div className="h-[32rem] overflow-hidden rounded-card border border-border shadow-sm">
        <ConversationView />
      </div>
    </div>
  );
}
