# Security and participant data

## Report privately

Use [GitHub private vulnerability reporting](https://github.com/idreesshaikh/human-ai-studies-framework/security/advisories/new).
If unavailable, contact a maintainer through their GitHub profile. Provide the
affected version and a minimal synthetic reproduction. Never put credentials,
participant records, consent materials, or private source code in public issues.

Report cross-project access, authentication bypass, invalid participant
credentials, undisclosed capture, and model-output validation bypass privately.
Methodological advice issues can be reported publicly using synthetic examples.

## Access and capture

Unauthenticated mode is for local use on a trusted machine. Configure access
controls before sharing an instance. Passing tests do not constitute a security
or ethics certification.

TERN excludes source text, keystrokes, and clipboard content. Optional transcript
and snapshot tools have separate content policies. Review their configuration,
selected files, and participant consent before enabling them. Filename checks
cannot detect secrets embedded in otherwise legitimate source files.

The model receives the design conversation and retrieved literature, not
participant event rows. Study reads and exports require project-scoped access.
Operators are responsible for storage, access, and retention arrangements.

## Retention

Capture toggles change future collection at session boundaries. They do not
erase previously collected events or filter historical fields from exports.
Disabled fields are not collected for possible later use. Attribution keys
remain available for joining and ordering records.

Downloaded bundles, transcript exports, and local shadow repositories may hold
sensitive information even when ignored by Git. Before deleting data, identify
ownership and exact scope and preserve a recoverable copy where appropriate.
