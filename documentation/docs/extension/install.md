# Install and connect

Participants install TERN into VS Code once, then connect it to the study with the
link the researcher sends. TERN needs VS Code 1.134 or later, on your own
computer: VS Code for the web cannot open the study folder.

!!! note "Check which extension build you have"
    The `v1.0.1` release names the extension **TERN: Telemetry for Engineering &
    Reasoning Norms** and uses **TERN:** command names. It has no **Disconnect from
    Study** command or task-folder download. The current source uses **StudyLoop:**
    commands but still reports version 1.0.1, so the version number alone cannot
    tell these builds apart. This guide follows the current source. Use the file
    your researcher sends, which they can
    [build from the current source](../platform/give-participants-tern.md#build-tern-from-source).

## Install TERN

1. **Get the file.** Use the `tern-1.0.1.vsix` file your researcher sends.
2. **Install it.** In VS Code, run **Extensions: Install from VSIX…** from the
   Command Palette and choose the file. It appears in the Extensions view as
   **StudyLoop Capture**.

## Connect to the study

1. **Open your study link.** Click the `vscode://` link from the researcher. It
   only works once TERN is installed. If you were sent a connection string
   instead, run **StudyLoop: Connect to Study** from the Command Palette and paste
   it.
2. **Read the consent statement** and choose **I consent**. Nothing is recorded
   before you do.
3. **Open the study folder.** If the researcher provided a folder, TERN opens the
   path or downloads and opens the supplied archive. If it cannot, you see the
   reason with **Open Folder…** and **Try again**, and you are still connected.

A message then lists what this study will capture, and the **StudyLoop study**
sidebar shows the same list under **What is captured**. Start when you are ready
with **StudyLoop: Start Study Session**, as described in
[Run a session](using.md).

!!! note "Single-use links"
    A single-use link is used up as soon as TERN contacts the study server, even if
    you then decline to consent. If you change your mind, ask the researcher for a
    new link.

## Leave a study

Run **StudyLoop: Disconnect from Study**. TERN removes the study's settings and
its stored connection. It does not delete events already recorded; see
[Privacy](privacy.md#delete-your-data). You cannot disconnect while a session is
running.

## If the server is not on your computer

The study server's address is in your link. Over `http://` your events travel
unencrypted; over `https://` they do not. If your researcher uses `http://` for a
server on another machine, ask them about it before you connect. See
[Privacy](privacy.md#where-the-data-goes).

## Next steps

- [Run a session](using.md)
- [What TERN captures](captured-data.md) and [your privacy](privacy.md)
