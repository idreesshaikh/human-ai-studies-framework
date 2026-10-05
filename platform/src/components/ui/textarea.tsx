import * as React from "react";
import { cn } from "@/lib/cn";

/* Long-form text field: the same `.control` box as every other field. With
 * `autoGrow` it sizes to its content (no resize grip); without it, a subtle
 * vertical grip remains. */
export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  autoGrow?: boolean;
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, autoGrow, ...props }, ref) => {
    const inner = React.useRef<HTMLTextAreaElement | null>(null);
    const setRef = (node: HTMLTextAreaElement | null) => {
      inner.current = node;
      if (typeof ref === "function") ref(node);
      else if (ref) ref.current = node;
    };
    const grow = React.useCallback(() => {
      const el = inner.current;
      if (!autoGrow || !el) return;
      el.style.height = "auto";
      const edge = el.offsetHeight - el.clientHeight;
      el.style.height = `${el.scrollHeight + edge}px`;
    }, [autoGrow]);
    React.useLayoutEffect(grow, [grow, props.value]);
    React.useEffect(() => {
      const el = inner.current;
      if (!autoGrow || !el || typeof ResizeObserver === "undefined") return;
      let width = el.clientWidth;
      const observer = new ResizeObserver(() => {
        if (el.clientWidth === width) return;
        width = el.clientWidth;
        grow();
      });
      observer.observe(el);
      return () => observer.disconnect();
    }, [autoGrow, grow]);
    return (
      <textarea
        ref={setRef}
        data-autogrow={autoGrow ? "" : undefined}
        className={cn("control control-area min-w-0 type-body leading-relaxed", autoGrow && "resize-none", className)}
        {...props}
        onInput={(event) => { grow(); props.onInput?.(event); }}
      />
    );
  },
);
Textarea.displayName = "Textarea";
