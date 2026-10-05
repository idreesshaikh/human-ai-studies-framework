/* When a reply stream fails, decide whether the same turn may be resent through
 * the blocking endpoint. Resending after the server has begun answering could
 * produce a second reply to one message, so only a stream that failed before
 * any event arrived (and was not cancelled by the researcher) is retried. */
export function shouldResendAfterStreamFailure(state: {
  aborted: boolean;
  eventsReceived: number;
}): boolean {
  return !state.aborted && state.eventsReceived === 0;
}
