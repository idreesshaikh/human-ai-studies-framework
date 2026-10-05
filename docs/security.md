# Security policy

Report vulnerabilities through
[private vulnerability reporting](https://github.com/idreesshaikh/human-ai-studies-framework/security/advisories/new).
Do not include participant data in a public issue. Describe reproduction steps,
expected behavior, and observed behavior using synthetic data where possible.

This is a single-maintainer research project. The main branch is supported;
fixes are not routinely backported.

## Relevant issues

- Reading or exporting another project's participant data.
- Recording beyond the participant's disclosed capture configuration.
- Abusing expired or revoked participant links or forging session identity.
- Bypassing authentication or project membership.
- Allowing model output to bypass protocol validation or invent source links.

Poor methodological advice is a quality issue and can be reported publicly
without including private study material.

## Deployment boundaries

The default unauthenticated mode is for local single-user use. Configure token
or Clerk authentication before sharing an instance. Participant credentials and
researcher credentials have different roles; do not expose either in examples.

TERN excludes raw source, keystrokes, and clipboard text. Optional transcript
tools support metadata-only, redacted, and full-content policies, and workspace
snapshots store code locally. Review the configured policies and consent before
enabling those producers.

The model receives the design conversation and retrieved literature, not
participant event rows. The operator controls where study data is stored and
for how long. Synthetic rehearsals remain in their selected study and must be
separated from participant findings.

## Telemetry retention

Telemetry collected under a participant's disclosed capture configuration is
retained in full and stays available for authorized analysis:

- A capture toggle changes only future collection. Turning an instrument off
  updates the capture configuration, which the editor applies at the next
  session boundary. It never hides or deletes telemetry already collected. Rows
  and payload fields recorded before the change stay in the study's dataset and
  exports.
- Collection follows the disclosed configuration. A field a researcher has
  disabled is not collected, and is never collected in the background to keep it
  available later. Retention only applies to data that was collected under the
  consented configuration.
- The join keys every row carries (participant, condition, session, timestamp,
  schema version, sequence, and event type) are never governed by a capture
  toggle, so a toggle cannot drop a field that analysis needs to join or order
  the data.
- The JSON and CSV exports and the analysis dataset read the full retained
  payload. They do not filter fields by the current toggle state, so changing a
  toggle does not change what earlier sessions already exported.

Access controls still apply: retained telemetry is readable only through the
study's authorized, project-scoped access.
