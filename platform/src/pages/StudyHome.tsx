import { Link, useParams } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { ConversationView } from "@/components/conversation/ConversationView";

/* A study's home: the design conversation, now living inside a project. */
export function StudyHome() {
  const { slug = "", id = "" } = useParams();
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-border bg-surface px-4 py-2 text-sm">
        <Link
          to={`/p/${slug}`}
          className="flex items-center gap-1 text-text-muted hover:text-text"
        >
          <ChevronLeft className="size-4" aria-hidden /> {slug}
        </Link>
        <span className="text-text-muted">/</span>
        <span className="font-medium text-text">{id}</span>
      </div>
      <div className="min-h-0 flex-1">
        <ConversationView />
      </div>
    </div>
  );
}
