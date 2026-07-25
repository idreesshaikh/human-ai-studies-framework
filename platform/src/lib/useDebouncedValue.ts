import { useEffect, useState } from "react";

/** How long a snappy input waits before the value it drives is used. Long
 * enough that ordinary typing produces one request instead of one per
 * keystroke, short enough that a deliberate pause feels immediate. */
export const DEBOUNCE_MS = 300;

/** The value, settled: it only updates once `value` has stopped changing
 * for `delay` ms.
 *
 * Use it wherever a keystroke would otherwise drive a request — corpus
 * search, the recommender refresh, an id lookup. The input stays fully
 * controlled and instant; only the *effect* of typing is debounced. */
export function useDebouncedValue<T>(value: T, delay = DEBOUNCE_MS): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return settled;
}
