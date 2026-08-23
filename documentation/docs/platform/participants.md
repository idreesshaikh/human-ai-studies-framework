# Participants

Participants is the bridge between a protocol on the platform and a person in
VS Code. It makes the install, consent, assignment, and capture boundary
visible before anyone starts a real session.

<figure markdown="span">
  ![The current Phoenix Participants tab](../assets/screens/study-participants.png){ width="900" }
  <figcaption>Install the exact TERN release first, then mint a one-use link for each participant.</figcaption>
</figure>

## The hand-off contract

1. The researcher installs the [TERN 1.0.0 release](https://github.com/idreesshaikh/human-ai-studies-framework/releases/tag/v1.0.0)
   into VS Code with **Extensions: Install from VSIX…**.
2. PHOENIX mints a participant-specific, one-use enrollment token.
3. The participant opens the link (`vscode://…/pair`) in VS Code.
4. TERN redeems the token, shows the consent statement, stores the approved
   capture configuration, and receives the participant’s assignment.
5. Events are written locally first and optionally mirrored to the middleware;
   the platform can then show session integrity in **Data**.

The deep link is intentionally not an installer. TERN is a GitHub-release VSIX,
not a Marketplace package, so the participant installs it once before pairing.

## Assignment is part of the protocol

Task order is rotated automatically so participants meet every condition in a
counterbalanced order. The participant does not choose the condition, and the
researcher does not have to keep a spreadsheet of assignments.

## What the participant sees before recording

The pairing flow keeps three things aligned:

- **Consent statement** — why the study is running and what it captures.
- **Capture config** — the protocol-approved instrument legs and endpoint.
- **Condition/task assignment** — the run that the analysis plan expects.

TERN’s preflight summary is the last gate. No session file is created until the
participant confirms **Begin session**.

## Projects, roles, and invitations

| Role | What they can do |
| --- | --- |
| Owner | Projects, roles, invitations, protocol, participants, and data |
| Researcher | Collaborate on the conversation, participants, and data |
| Viewer | Read-only access |

Run a [synthetic dry run](data.md#synthetic-dry-run) first. It exercises the
same capture boundary without asking a real participant to debug the study.
