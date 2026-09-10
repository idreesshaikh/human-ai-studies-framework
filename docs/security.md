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
participant event rows. The operator controls study storage and retention.
Synthetic rehearsals remain in their selected study and must be separated from
participant findings.
