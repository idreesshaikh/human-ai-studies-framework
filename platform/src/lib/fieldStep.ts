/* The next value of a number field after a stepper press. Pure, so the
 * integrated +/- buttons and the native arrow keys agree on clamping and on
 * decimal steps (0.1 + 0.1 must read 0.2, not 0.20000000000000004). */
export interface StepBounds {
  min?: number;
  max?: number;
  step?: number;
}

const decimals = (n: number) => {
  const [mantissa, exponent = "0"] = String(n).split("e");
  return Math.max(0, (mantissa.split(".")[1]?.length ?? 0) - Number(exponent));
};

export function stepNumber(raw: string, direction: 1 | -1, { min, max, step = 1 }: StepBounds = {}): string {
  const current = Number.parseFloat(raw);
  const places = Math.min(100, Math.max(
    decimals(step),
    Number.isFinite(current) ? decimals(current) : 0,
    min === undefined ? 0 : decimals(min),
    max === undefined ? 0 : decimals(max),
  ));
  let next: number;
  if (!Number.isFinite(current)) next = min ?? (direction === 1 ? step : 0);
  else next = current + direction * step;
  if (min !== undefined && next < min) next = min;
  if (max !== undefined && next > max) next = max;
  return String(Number(next.toFixed(places)));
}
