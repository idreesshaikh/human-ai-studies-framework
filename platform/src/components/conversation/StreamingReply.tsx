import { useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";
import { AssistantReply } from "./StreamingTurn";

export function StreamingReply({
  ref,
  source,
}: {
  ref: Ref<{ update: () => void }>;
  source: { current: string };
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
  // The first fragments can arrive before React mounts the preview.
  useEffect(() => setText(source.current), [source]);
  useEffect(() => () => {
    if (frame.current !== null) cancelAnimationFrame(frame.current);
  }, []);
  return (
    <AssistantReply text={text} streaming />
  );
}
