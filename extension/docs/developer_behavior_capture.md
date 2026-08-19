> **Superseded.** This is the original scoping note that picked Tako,
> ActivityWatch, and WakaTime as reference plugins. What TERN actually built
> from them, including where this note's plan diverged (Python-only scope
> dropped, no raw keystroke/character-volume capture per the privacy
> invariant), is recorded in [`adaptation-notes.md`](adaptation-notes.md).
> Kept here for history, not as current instruction.

SUMMARY - TO BUILD A CUSTOM PLUGIN IN IDE TO CAPTURE DEVELOPER BEHAVIOR (Non-Intrusive) - VS-Code for now - Will be extended later

One part of capturing metrics for our framework is capturing the developer behavior. Developer behavior in this sense means how the developer interacts with the codebase (switching tabs, actively writing code, opening and closing files and tabs, time spent on a specific line of code, etc). And from these data, we can analyze and gain insights.

*Note: This plugin focuses strictly on human behavior telemetry. Another teammate is handling the source-code metrics side of things, so we don't need to worry about static code analysis here.*

The good thing is we don't have to build a plugin from scratch to capture these metrics, there are already existing tools (open-source) which we can adapt/adopt their implementation (only necessary parts) and build a custom plugin for our use case.

3 already existing plugins that are open source came up. They are:

### 1. Tako
* **What it does:** Captures developer actions in the background. Non-intrusive therefore does not interfere with the workflow of the developer. It tracks tab switches, text edits, and when a developer accepts or rejects an AI code completion snippet.
* **Repo:** https://github.com/si-codelounge/tako
* **How it helps us:** We can look directly at how they hook into the VS Code API to catch text document mutations and AI lifecycle events. This will help us track how long a dev actually reviews an agent's code before accepting it.

### 2. ActivityWatch (`aw-watcher-vscode`)
* **What it does:** This is specifically a privacy-first time tracker that logs what file you are working on, cursor movements, and window changes, then sends them as background heartbeats to a local daemon server.
* **Repo:** https://github.com/ActivityWatch/aw-watcher-vscode
* **How it helps us:** We can adapt their decoupled architecture. Our custom plugin will just be a lightweight "sensor" inside the IDE that instantly fires raw JSON event objects to our local Python middleware server on port 8000. This keeps the IDE running smoothly without any typing lag.

### 3. WakaTime
* **What it does:** Automatically tracks coding metrics by separating active programming mechanics (typing, selecting lines, scrolling) from passive background idle states.
* **Repo:** https://github.com/wakatime/vscode-wakatime
* **How it helps us:** We can adopt their logic for detecting when a developer is actually thinking/working versus when the editor is just left open in the background. We can also steal their language filter approach to make sure we restrict our tracking strictly to Python files (`.py`) for this first stage.

---

### Exact Data Points Our Custom Extension Will Collect:

* **Tab & File Swapping:** Knowing the exact file paths, names, and when a developer switches focus between different parts of the system.
* **Visual Viewing Ranges:** Tracking the top and bottom lines currently shown on the screen to see if they actually scrolled through and reviewed a massive multi-file code change.
* **Text Changes:** Catching the exact millisecond timestamp, character volume, and lines modified. If a massive block of code appears in 1 millisecond, our backend knows it was injected by an agent. If it's written step-by-step, it's logged as manual human writing.
* **Clipboard Pastes:** Spotting when raw compiler or terminal errors are copied and pasted directly into the agent's chat pane, showing how often devs rely on the tool to fix simple bugs.
