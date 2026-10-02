import { useEffect, useState } from "react";

export const DEBOUNCE_MS = 300;

export function useDebouncedValue<T>(value: T, delay = DEBOUNCE_MS): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return settled;
}
