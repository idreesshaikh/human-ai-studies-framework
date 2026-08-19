import { useId } from "react";
import { cn } from "@/lib/cn";
import { STEER_STOPS, steerStop, type SteerLevel } from "@/lib/steer";

/* The steer dial — how much the assistant drives this conversation.
 *
 * It sits at the head of the thread, not on the composer. What it governs is
 * the conversation as a whole, not the one message about to be sent, and a
 * control stacked directly above the input reads as a property of that input
 * — as well as pushing the thing the researcher actually came to type further
 * down the screen every time the window gets short.
 *
 * The track is a gradient, because the thing being set is a continuum: at the
 * quiet end the assistant answers and little else, and the field fills toward
 * the accent as it takes on more of the work. Colour alone carries the
 * direction of travel. Tick marks drawn on top of it were fighting the
 * gradient for the same job and losing at both, and the readout beside the
 * track already names the stop the thumb is resting on.
 *
 * It states its effect twice — the stop's name, and a line saying what changes
 * about the next turn — and both update as it is dragged, before anything is
 * committed. A control whose effect you cannot see from where it lives is a
 * control nobody trusts.
 *
 * A native range input carries the keyboard contract for free: arrows step,
 * Home and End jump to the ends, and the value is announced. Nothing here
 * re-implements that. */
export function SteerDial({
  value,
  onChange,
  className,
}: {
  value: SteerLevel;
  onChange: (next: SteerLevel) => void;
  className?: string;
}) {
  const id = useId();
  const stop = steerStop(value);
  const max = STEER_STOPS.length - 1;

  return (
    <div
      data-agent="steer-dial"
      /* Wraps rather than truncating: the effect line is the half of this
        * control that says what it DOES, and hiding it below `md:` left a
        * phone with a gradient and one word. */
      className={cn("flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1", className)}
    >
      <label htmlFor={id} className="type-legend shrink-0 text-text-muted">
        Steer
      </label>

      <input
        id={id}
        type="range"
        className="steer-range focus-ring-owned shrink-0"
        min={0}
        max={max}
        step={1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value) as SteerLevel)}
        aria-valuetext={`${stop.label}. ${stop.summary}`}
      />

      {/* The readout. `aria-live` is deliberately absent: the range input
        * already announces its own value text on every step, and a live
        * region here would say the same sentence a second time. */}
      <p className="type-caption min-w-0 text-text-muted">
        <span className="font-semibold text-text">{stop.label}</span>
        {". "}
        {stop.summary}
      </p>
    </div>
  );
}
