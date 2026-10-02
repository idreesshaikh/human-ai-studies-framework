export function remainingSeconds(remainingMs: number): number {
  return Math.ceil(Math.max(0, remainingMs) / 1000);
}

export function formatRemaining(remainingMs: number): string {
  const total = remainingSeconds(remainingMs);
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}
