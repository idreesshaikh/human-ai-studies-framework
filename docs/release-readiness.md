# Open-source release gate

For #57. This checklist is not a hosted deployment or legal/security sign-off.

- Root and extension MIT license notices are present; preserve their distinct
  copyright notices. Owners must confirm rights to contributed code and external
  artifacts. No license or attribution was replaced by this delivery.
- [Contribution guidance](../CONTRIBUTING.md), [security reporting](../SECURITY.md),
  PR/issue templates, code ownership, locked dependencies, workspace consistency,
  coverage floors, dependency audits, and docs checks are available.
- Secrets and local/generated data are ignored. Generated evaluation artifacts
  belong outside production source. Gitignore prevents accidental tracking; it
  does not remove already-tracked secrets or establish permission to publish data.
- Build and test the exact release commit. Merge only through normal code-owner
  review and required CI, then inspect the deployed version. A feature-branch PR
  showing “merged” does not prove its tree reached main.
- Rehearse chat, evidence review, planning, enrollment, replay, and exports in a
  separate synthetic database. Real participant capture still needs a physical
  VS Code rehearsal and approved recruitment/consent/withdrawal procedures.
- Check hosted authentication and project isolation, TLS, backup/restore,
  retention, and operator-owned configuration before collecting participant data.
- Freeze protocol, task material, model version, evidence map, and exclusions for
  research. Do not announce a reviewed evidence map, classifier superiority, or
  human usability score from software integration or synthetic rehearsals.

Publication, attribution approval, human research approval, and release sign-off
remain owner decisions. Do not change repository visibility as a side effect.
