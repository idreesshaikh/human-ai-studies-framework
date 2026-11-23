# Participant links

The **Run** tab connects people to the study. You create a link for each
participant, they open it in VS Code with [TERN](../extension/index.md), and
their sessions appear here while they run.

<figure markdown="span">
  ![Run tab showing synthetic participant links](../assets/screens/run-light.webp#only-light)
  ![Run tab showing synthetic participant links](../assets/screens/run-dark.webp#only-dark)
  <figcaption>The example links are illustrative and cannot connect an editor.</figcaption>
</figure>

## Create links

Apply the protocol first; links carry the applied version. Then choose
**Create participant links**:

| Field | What to choose |
| --- | --- |
| **How many** | 1 to 100 links at once. Participant IDs are assigned in order: P01, P02, and so on |
| **Link type** | **Per participant**: one link a participant keeps for all their sessions. **Per session**: a new link for every session, usable once |
| **Study folder** | The task folder TERN opens after consent. See below |
| **Capture settings** | Which instruments this link records: Static metrics, Behavioral, Cognitive, Agent interaction |

Links expire after 30 days. **Revoke** stops a link from working, after you
confirm **Revoke permanently**.

## Send them

Participants need TERN installed first; see
[Install and connect](../extension/install.md). Then send either:

- the **Open in VS Code** link, which connects in one click; or
- the connection string from **Copy link**, which participants paste into
  **StudyLoop: Connect to Study**.

TERN reads the link, shows the consent statement, and waits for
**I consent** before anything is recorded. The roster then shows the link as
paired, and **Will capture** shows what it records.

!!! note "Per-session links and consent"
    TERN redeems a link before it shows the consent statement. A participant
    who declines has used up a **Per session** link; create a new one if they
    change their mind.

## The study folder

A link can open the task's folder in VS Code right after consent. Set the
**Study folder** once for the study, in one of two ways:

- **A path** that already exists on participants' computers, such as
  `~/study-task`, `/home/participant/study-task`, `C:\study\task` or a `file://`
  address. Use this when you deliver the task separately.
- **A zip** of the folder, up to 50 MB. TERN downloads it with the
  participant's own credential, checks it against the uploaded file, unpacks it
  into its own storage and opens it. A zip with one top-level folder opens that
  folder.

Without a study folder, TERN uses the task's `materials` value from the
protocol when it is an absolute path. TERN never downloads a repository from a
URL.

If the folder cannot be opened, pairing and consent still succeed. The
participant sees the reason, with **Open Folder…** and **Try again**. That
happens when the path is relative or a web address, does not exist on that
computer, the download fails or does not match, VS Code cannot open it, or the
participant uses VS Code for the web. In a WSL, SSH or container window, the
path is checked and a zip unpacked on that window's machine, so a WSL path must
be a Linux path such as `/home/participant/task`.

`vscode-insiders://` links are not generated; use desktop VS Code.

## Who gets which condition

The protocol assigns conditions; participants never choose, and TERN never
shows them theirs.

- **Within subjects, counterbalanced:** each participant meets every condition,
  and the order rotates across participants.
- **Within subjects, not counterbalanced:** every participant meets the
  conditions in the same order.
- **Between subjects:** each participant gets one condition, assigned in turn.

## Watch sessions

While sessions run, the Run tab shows each one's event rate and the gaps in its
event sequence. This is also the way to check that TERN's events are arriving.

Run a small pilot with a few real participants first, and tag those sessions as
pilots on [Data](data.md). Pilot sessions stay in exports but are left out of
confirmatory analysis.
