# Security policy

## Reporting a vulnerability

**Do not open a public issue.** Use
[private vulnerability reporting](https://github.com/idreesshaikh/human-ai-studies-framework/security/advisories/new).

Include what you did, what happened, and what you expected. A proof of concept
helps; a working exploit is not required. Expect an acknowledgement within a
week — this is a single-maintainer research project, not a staffed product.

## In scope

PHOENIX handles research participant data, so the highest-severity class here
is anything that exposes it or captures more than a participant consented to:

- **Participant data exposure** — reading another project's or study's data,
  events, uploads, or paper sets. Studies are scoped per project and per study;
  a path that crosses either boundary is a vulnerability.
- **Capture beyond consent** — any way to make TERN record something the
  consent statement did not name, or to change what is captured without that
  change surfacing in the consent statement a participant sees at their next
  session start.
- **Enrollment token abuse** — redeeming a revoked or expired pairing link,
  reusing a single-use one, or minting a credential for a study you have no
  role on.
- **Authentication and authorization** — bypassing sign-in, escalating a
  `viewer` or `member` role to `owner`, or acting on a project you were
  never invited to.
- **Ingest integrity** — writing events attributed to a participant, condition,
  or task other than the one your credential was issued for. Join keys are
  server-stamped precisely so the client cannot claim them.
- **Prompt injection reaching the corpus or the protocol** — content in a paper
  or a researcher's message that causes a design move to cite a paper the
  platform does not hold, or to write a protocol field outside the declared
  fillable slots.

## Out of scope

- The design conversation producing methodologically poor advice. That is a
  quality problem, worth an issue, but not a vulnerability.
- Denial of service through volume against your own instance.
- Anything requiring an attacker to already hold the researcher's own
  credentials or filesystem access.
- Findings against a deployment's own misconfiguration — an instance run with
  `MIDDLEWARE_AUTH` unset is unauthenticated by design, for local single-user
  use.

## What the platform promises

These are the invariants worth attacking, stated so a report can name the one
that broke:

- Participant data stays on the researcher's infrastructure. Nothing under
  `.study-data/` or `results/` is ever committed, and no participant data is
  sent to a third party.
- Instruments record aggregates, shapes, timings, and salted hashes — never raw
  code, keystrokes, or clipboard contents.
- The language model sees retrieved paper metadata and the conversation. It
  never sees participant event data.
- Join keys on ingested events are stamped by the server from the pairing
  credential, not accepted from the client.
- A participant is shown what will be captured before anything is recorded, and
  the pairing consent gate is unconditional.

## Supported versions

The `main` branch is the supported version. This is active research software;
fixes land on `main` rather than being backported.
