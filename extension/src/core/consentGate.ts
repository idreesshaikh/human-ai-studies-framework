/**
 * The consent acknowledgment gate (FR-ETH-1, FR-AGENT-5). No event may leave
 * the machine until the participant accepts the protocol-derived consent
 * statement and its content policy. Portable core: the adapter renders the
 * statement and calls acknowledge().
 */

export class ConsentNotGivenError extends Error {}

export class ConsentGate {
  private _accepted = false;

  constructor(
    readonly statement: string,
    readonly policy: string,
  ) {}

  get accepted(): boolean {
    return this._accepted;
  }

  acknowledge(): void {
    this._accepted = true;
  }

  assertAccepted(): void {
    if (!this._accepted) {
      throw new ConsentNotGivenError('capture may not start before consent is acknowledged');
    }
  }
}
