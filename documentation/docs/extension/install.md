# Install and connect

Participants install TERN into VS Code once, then connect it to the study with
the link the researcher sends. TERN needs VS Code 1.134 or later.

!!! note "The published release is older than this guide"
    The [1.0.1 release](https://github.com/idreesshaikh/human-ai-studies-framework/releases/tag/v1.0.1)
    from 25 August 2026 is listed as
    **TERN: Telemetry for Engineering & Reasoning Norms**, and its commands
    start with **TERN:** rather than **StudyLoop:**. It has no
    **Disconnect from Study** command and does not download a study's task
    folder. The code in the repository still reports version 1.0.1. To get the
    version this guide describes, [build it from source](#build-from-source).

## For participants

1. **Install TERN.** Use the `tern-1.0.1.vsix` file your researcher sends. In
   VS Code, run **Extensions: Install from VSIX…** and choose the file. It
   appears in the Extensions view as **StudyLoop Capture**.
2. **Open your study link.** Click the `vscode://` link from the researcher.
   The link only works once TERN is installed. If you were sent a connection
   string instead, run **StudyLoop: Connect to Study** from the Command Palette
   and paste it.
3. **Read the consent statement** and choose **I consent**. Nothing is
   recorded before you do.
4. **Wait for the study folder.** If the study has a task folder, TERN
   downloads it and opens it in the window.

A message then lists what this study will capture, and the **StudyLoop study**
sidebar shows the same list under **What is captured**. Start when you are
ready with **StudyLoop: Start Study Session**, as described in
[Run a session](using.md).

To leave a study, run **StudyLoop: Disconnect from Study**. TERN removes the
study's settings and its stored connection. It does not delete events already
recorded; see [Privacy](privacy.md#delete-your-data). You cannot disconnect
while a session is running.

## For researchers

Create participant links on the **Run** tab of your study in PHOENIX.
**Copy link** copies a connection string that participants can paste into
**StudyLoop: Connect to Study**.

Before you send links, know how they behave:

- **Per participant** links can be used again. **Per session** links work
  once, and TERN redeems a link when it first contacts the study server,
  before it shows the consent statement. A participant who declines has used
  a per-session link, so create a new one if they change their mind.
- Every link expires after 30 days.
- At the start of every session, TERN fetches the capture settings of the
  study's applied protocol and applies them. If it changed since the last session, the
  **Session** view says **A change is waiting**. TERN does not ask for
  consent again, so settle the capture configuration before you send links.

!!! warning "Use HTTPS for a server on another machine"
    TERN accepts `http://` and `https://` study servers. Events travel
    unencrypted over `http://`, so use it only on your own machine.

## Build from source

The extension lives in `extension/` and needs Node.js 22.

```bash
cd extension
npm ci
npm run package   # runs every check, then writes tern-1.0.1.vsix
code --install-extension tern-1.0.1.vsix
```

To work on TERN itself, open `extension/` in VS Code and press ++f5++. An
Extension Development Host window opens with TERN loaded and unpaired.

```bash
npm run compile     # build to out/
npm run typecheck   # strict type check, no output
npm test            # unit tests with Node's test runner
npm run check       # type check, lint, format check and tests
```

The unit tests cover the session clock, the stuck heuristics, the recorder and
the sinks with mocked timers, so they run without launching VS Code.

## Settings for unpaired sessions

Unpaired sessions read the `tern.*` settings. While a study is connected, the
study sets them and your changes are ignored. These are the ones you are most
likely to change:

| Setting | Default | What it does |
| --- | --- | --- |
| `tern.session.durationMinutes` | `60` | Session length |
| `tern.fatigue.intervalMinutes` | `15` | Time between fatigue questions, varied by ±20% |
| `tern.fatigue.quietTailMinutes` | `5` | No fatigue questions in this final stretch |
| `tern.stuck.enabled` | `true` | Show the stuck prompt |
| `tern.stuck.thresholdSeconds` | `90` | Time on one region without editing before the prompt appears |
| `tern.stuck.cooldownMinutes` | `5` | Minimum time between stuck prompts |
| `tern.behavior.enabled` | `true` | Record editor activity |
| `tern.behavior.languages` | `["python"]` | Languages whose files are recorded. Empty means all |
| `tern.output.directory` | empty | Folder for event files. Empty means `.study-data/` in the workspace |
| `tern.output.httpEndpoint` | empty | Also send events to this server, for example `http://127.0.0.1:8000/ingest/events` |

All 45 settings, with descriptions, are in the **Settings** editor under
*StudyLoop Capture*.
