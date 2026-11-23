import { useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";
import { StreamingTurn } from "./StreamingTurn";

export function StreamingReply({
  ref,
  source,
  follow,
}: {
  ref: Ref<{ update: () => void }>;
  source: { current: string };
  follow: () => void;
}) {
  const [text, setText] = useState(() => source.current);
  const frame = useRef<number | null>(null);

  // Publish at most once per frame, without re-rendering the saved thread or draft.
  useImperativeHandle(ref, () => ({
    update() {
      if (frame.current !== null) return;
      frame.current = requestAnimationFrame(() => {
        frame.current = null;
        setText(source.current);
      });
    },
  }), [source]);
  useEffect(() => () => {
    if (frame.current !== null) cancelAnimationFrame(frame.current);
  }, []);
  useEffect(follow, [text, follow]);

  if (!text) {
    return <p role="status" className="px-1 py-1 type-caption text-text-muted">Thinking…</p>;
  }
  return (
    <div aria-hidden="true">
      <StreamingTurn turn={{
        turnId: "streaming",
        role: "platform",
        author: "Assistant",
        text,
        moves: [],
        recommendations: [],
      }} />
    </div>
  );
}
