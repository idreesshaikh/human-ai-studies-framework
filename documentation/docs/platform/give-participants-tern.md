# Give participants TERN

A participant needs two things: the TERN extension installed in VS Code, and the
link you created on the **Run** tab. This page covers what to send, what happens
when they connect, and the settings worth deciding before you send anything.

## What to send

1. **TERN.** Send the `.vsix` file. The Run tab has **Install TERN in VS Code**,
   with **Download the .vsix** for the latest GitHub release. TERN is not on the
   VS Code Marketplace, so a link cannot install it: participants install the file
   first with **Extensions: Install from VSIX…**, as described in
   [Install and connect](../extension/install.md).
2. **Their link.** Send either the **Open in VS Code** link, which connects in one
   click once TERN is installed, or the connection string from **Copy link**, which
   participants paste into **StudyLoop: Connect to Study**.

!!! warning "Check which TERN build you send"
    The `v1.0.1` release predates the task-folder download and **Disconnect from
    Study**, and it names its commands **TERN:** instead of **StudyLoop:**. To use
    a zipped study folder, send a VSIX built from the current source; see
    [Build TERN from source](#build-tern-from-source).

## What happens when they connect

TERN redeems the link, shows the consent statement written from your protocol and
waits for **I consent** before anything is recorded. The roster then shows the link
as **Paired**, and **Sending data** once events arrive. The participant starts a
session when ready; see [Run a session](../extension/using.md).

- **Per participant** links can be used again. **Per session** links work once, and
  TERN redeems a link before it shows the consent statement. A participant who
  declines has used up a per-session link, so create a new one if they change their
  mind.
- Every link expires after 30 days.
- The protocol decides capture. A link keeps the protocol it was issued under, and
  TERN does not ask for consent again, so settle the protocol before you send
  links. See [Changing the protocol later](protocol-draft.md#changing-the-protocol-later).

## The study folder

A link can open the task's folder in VS Code right after consent. Set the **Study
folder** once for the study, in the **Create participant links** dialog, in one of
two ways:

- **A path** that already exists on participants' computers, such as
  `~/study-task`, `/home/participant/study-task`, `C:\study\task` or a `file://`
  address. Choose **Save path**. Use this when you deliver the task separately.
- **A zip** of the folder, up to 50 MB. Choose **Upload zip…**. TERN downloads it
  with the participant's own credential, checks it against the uploaded file,
  unpacks it into its own storage and opens it. A zip with one top-level folder
  opens that folder. **Clear** removes the setting.

Without a study folder, TERN uses the task's `materials` value from the protocol
when it is an absolute path. TERN never downloads a repository from a URL.

If the folder cannot be opened, pairing and consent still succeed. The participant
sees the reason, with **Open Folder…** and **Try again**. That happens when the path
is relative or a web address, does not exist on that computer, the download fails
or does not match, VS Code cannot open it, or the participant uses VS Code for the
web. In a WSL, SSH or container window the path is checked, and a zip unpacked, on
that window's machine, so a WSL path must be a Linux path such as
`/home/participant/task`. Links open desktop VS Code only; `vscode-insiders://`
links are not generated.

## Use HTTPS for a server on another machine

TERN accepts `http://` and `https://` study servers. Events travel unencrypted over
`http://`, so use it only on your own machine. See
[Configuration](../reference/configuration.md).

## Build TERN from source

The extension lives in `extension/` and needs Node.js 22.

```bash
cd extension
npm ci
npm run package   # runs every check, then writes tern-<version>.vsix
code --install-extension tern-<version>.vsix
```

To work on TERN itself, open `extension/` in VS Code and press ++f5++. An Extension
Development Host window opens with TERN loaded and unpaired. `npm run check` runs
the type check, lint, format check and unit tests, which need no VS Code.

## Next steps

- [Review sessions and export](data.md) as data arrives
- [TERN for participants](../extension/index.md), the guide to send them
