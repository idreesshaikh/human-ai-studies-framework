import { Link } from "react-router-dom";
import { ArrowRight, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ConversationView } from "@/components/conversation/ConversationView";
import { DEMO_TRANSCRIPT } from "@/lib/demoTranscript";
import { useApi } from "@/lib/session";
import { useAsync } from "@/lib/useAsync";

export function DemoProject() {
  const api = useApi();
  const { data, loading } = useAsync(() => api.demo().catch(() => null), []);

  return (
    <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-8">
      <Link to="/" className="text-sm text-text-muted hover:text-text">
        &larr; Phoenix
      </Link>

      <header className="flex flex-wrap items-center gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h1 className="font-serif text-3xl font-medium tracking-tight text-text">
              {loading ? "Demo project" : data?.projectName ?? "Demo project"}
            </h1>
            <Badge variant="outline">
              <Eye className="size-3" aria-hidden /> read-only
            </Badge>
          </div>
          <p className="text-sm text-text-muted">
            A real design conversation, start to finish. Every move and
            citation below came from an actual session, not a script.
          </p>
        </div>
        <Button asChild>
          <Link to="/projects">
            Start your own <ArrowRight aria-hidden />
          </Link>
        </Button>
      </header>

      <div className="overflow-hidden rounded-card border border-border-strong bg-surface shadow-brutal-lg">
        <div className="border-b border-border bg-surface-raised px-4 py-2.5">
          <span className="font-mono text-xs font-medium tracking-wide text-text-muted">
            Design session
          </span>
        </div>
        <div className="h-[50vh] min-h-[20rem] max-h-[32rem]">
          <ConversationView
            studyId={data?.studyId || "demo"}
            stubOnly
            replay={DEMO_TRANSCRIPT}
          />
        </div>
      </div>
    </div>
  );
}
