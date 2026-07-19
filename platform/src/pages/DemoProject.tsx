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
            <h1 className="font-display text-2xl font-bold uppercase tracking-tight text-text">
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

      <div className="overflow-hidden rounded-card border-2 border-border-strong bg-surface shadow-brutal-lg">
        <div className="flex items-center justify-between gap-3 border-b-2 border-border-strong bg-bg px-3 py-2">
          <span className="font-display text-xs font-bold uppercase tracking-wider text-text-muted">
            demo.session — read-only
          </span>
          <span className="flex items-center gap-1.5" aria-hidden>
            <span className="size-3 rounded-chip border-2 border-border-strong bg-accent" />
            <span className="size-3 rounded-chip border-2 border-border-strong bg-unsourced" />
            <span className="size-3 rounded-chip border-2 border-border-strong bg-grounded" />
          </span>
        </div>
        <div className="crt-scanlines h-[32rem]">
          <ConversationView />
        </div>
      </div>
    </div>
  );
}
