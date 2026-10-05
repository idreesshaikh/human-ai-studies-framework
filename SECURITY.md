# Security and participant data

This is research software, not a security or ethics certification. Protect
participant identities, session credentials, code, and consent records.

## Report privately

Use GitHub private vulnerability reporting if enabled. Otherwise contact a
maintainer privately through their GitHub profile before sharing sensitive
details. The code owners are listed in `.github/CODEOWNERS`. Do not include live
keys, tokens, participant data, or source code in public issues. Provide a
minimal synthetic reproduction and the affected commit/version.

## Deployment boundary

Local no-auth mode is for a loopback server on a trusted machine, not a hosted
participant deployment. Hosted access requires the documented authentication,
project scope, transport security, and operator configuration. Health checks
and passing tests do not establish a production security audit.

Raw code capture is off by default. New replay diffs require explicit task-file
selection, approved protocol configuration, and appropriate participant consent.
Review selected source files for secrets; filename checks cannot detect secrets
embedded in otherwise legitimate code. Code diffs are hidden when the current
study policy disables them. Downloaded bundles and local shadow repositories
remain sensitive artifacts even when git-ignored.

Before changing retention or deleting data, identify ownership and exact scope,
preserve a recoverable copy where appropriate, and inform the operator. Never
sweep records based only on a test-like name or a missing study mapping.
