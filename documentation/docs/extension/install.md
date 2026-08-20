# Installing TERN

## For participants (paired install)

1. Create a participant link on the platform's **Participants** tab.
2. Open the link (`vscode://…/pair` deep link) — or copy it into VS Code.
3. The editor joins the study already configured as designed: consent
   statement, capture config, everything.

!!! tip
    The consent statement and capture config are approved in the protocol
    before any real session runs. A capture config the researcher has not
    approved never runs.

## For local development

TERN ships as a `.vsix` on the
[releases page](https://github.com/idreesshaikh/human-ai-studies-framework/releases/latest).
Install it via **Extensions: Install from VSIX…**:

```bash
# build the .vsix yourself, or download it from the releases page
npm install
npm run package            # produces tern-<version>.vsix
code --install-extension tern-<version>.vsix
```

## Running the extension development host

```bash
npm install
npm run compile
```

Open the extension folder in VS Code and press **F5** — an Extension
Development Host window opens with the extension loaded. In that window:

1. Click **`Study: idle`** in the status bar (or run
   _TERN: Start Study Session_ from the command palette).
2. Enter a participant ID (e.g. `P07`) and pick the condition.
3. Work normally — the countdown runs in the status bar, and fatigue prompts
   appear every 15 min (default).
4. When the timer elapses (or you run _End Study Session_), the debrief survey
   opens and the data file is finalized.

### Development workflow

```bash
npm run compile     # build the extension to out/
npm run typecheck   # strict type-check, no emit
npm test            # compile + run the core unit suite (node:test)
```

The portable core (`src/core/*` — session clock, stuck heuristics, recorder,
sinks) is covered by a fast, dependency-free unit suite under `test/`, using
Node's built-in test runner with mocked timers so the time-based logic is
exercised deterministically without launching an IDE.

## Configuration

TERN is configured by the study protocol via the pair link. Advanced settings
are exposed as VS Code settings under `tern.*` — e.g. `tern.stuck.thresholdSeconds`,
`tern.stuck.cooldownMinutes`, `tern.stuck.languages`, and
`tern.output.httpEndpoint`.