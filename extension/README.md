# TERN · StudyLoop Capture

TERN is the VS Code participant extension for [StudyLoop](../README.md).
It runs protocol-configured sessions, records disclosed events and surveys,
and writes local JSONL with optional forwarding to the study server.

## Install

Download the `.vsix` from the
[releases page](https://github.com/idreesshaikh/human-ai-studies-framework/releases/latest).
In VS Code, select **Extensions: Install from VSIX…**, then choose the file.
TERN is distributed through GitHub Releases rather than the Marketplace.

## Connect and run

1. Obtain a participant link from the researcher.
2. Open it or run **StudyLoop: Connect to a Study** and paste the connection
   string. Review the study, assignment, and capture configuration.
3. Run **StudyLoop: Start Study Session**. Recording starts only after the
   participant confirms the preflight disclosure and consent.
4. Work normally. Use the status-bar timer to pause, resume, log fatigue, or
   finish the session.
5. Complete any configured debrief. Local recording and delivery status remain
   visible in the sidebar.

Linked sessions use the server-issued identity and assignment. Inspect the
preflight rather than relying on editable local defaults. See
[session instructions](../documentation/docs/extension/using.md) and
[study configuration](docs/configuring-a-study.md).

## Try it locally

Build the extension and open the sample workspace from the repository root:

```bash
npm --prefix extension ci
npm --prefix extension run compile
code --extensionDevelopmentPath=extension extension/examples/tern-lab
```

The [sample workspace](examples/tern-lab/README.md) uses generic demo values
and disables HTTP forwarding. Its `.study-data/` output stays local.

## Capture and limitations

- Session timing, editor activity, edit shapes, and configured surveys carry
  participant, condition, session, sequence, and schema information.
- TERN does not record source text, keystrokes, or clipboard contents. Optional
  external transcript and snapshot tools have separate privacy policies.
- Edit-origin, attention, and stuck signals are heuristics. They can miss or
  misclassify activity and do not establish gaze, comprehension, or AI use
  outside the capture boundary.
- Local JSONL and HTTP retries support delivery recovery. Inspect integrity
  and send status before treating a session as complete.
- The legacy debrief is adapted and is not standard NASA-TLX. Versioned
  instruments retain their declared wording and scoring.

See [captured data](../documentation/docs/extension/captured-data.md),
[privacy](../documentation/docs/extension/privacy.md), and
[measurement mechanisms](docs/adaptation-notes.md).

## Development

From `extension/`:

```bash
npm ci
npm run check
npm run package
```

Checks include types, lint, formatting, and tests. Packaging produces an
installable `.vsix`. See [development](docs/development.md),
[validation](docs/validation.md), and [troubleshooting](docs/troubleshooting.md).

Code is available under the [MIT License](LICENSE).
