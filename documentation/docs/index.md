# StudyLoop

StudyLoop helps researchers design, run and inspect studies of developers
working with and without AI. **PHOENIX**, the researcher web app, turns a
research question into a protocol. **TERN**, an extension for VS Code, runs that
protocol with each participant and records what it allows.

<div class="grid cards" markdown>

-   **For researchers**

    ---

    Install StudyLoop, design a study, recruit participants and read the data.

    [Get started](get-started/index.md)

-   **For participants**

    ---

    Install TERN in VS Code and connect it with the link you were sent.

    [Install TERN](extension/install.md)

</div>

## The researcher's path

A study moves through five tabs in PHOENIX. Each one has a guide.

| Tab | What you do | Guide |
| --- | --- | --- |
| **Setup** | Describe the study in the design conversation, start from a template or enter the details directly, then review and apply the protocol | [Design a study](platform/index.md) |
| **Literature** | Collect the papers behind the study and link them to the protocol | [Literature](platform/library.md) |
| **Plan** | Estimate how many participants the analysis needs | [Plan recruitment](platform/planning.md) |
| **Run** | Create participant links, give participants TERN and watch sessions arrive | [Participant links](platform/participants.md) |
| **Data** | Check sessions, record inclusion decisions and download the records | [Review sessions](platform/data.md) |

The protocol you apply is the only thing that configures a participant's
session, so the study you designed is the study that runs. Participants follow
[their own guide](extension/index.md).

## What StudyLoop does not claim

- **AI use.** TERN records accepted inline suggestions, and agent activity from
  hooks you install. Its error rates have not been measured, so a signal is a
  reason to look and not proof of AI use. TERN cannot verify that a no-AI group
  stayed free of AI, and a missing signal does not show that no AI was used.
- **Validity.** Calculations depend on the assumptions shown beside them.
  StudyLoop does not certify a study, and it does not replace ethics review or
  statistical judgement.
- **Results from examples.** Synthetic sessions are left out of research
  exports and estimates.

!!! warning "Example data is not a finding"
    The example study uses synthetic data and must never be reported as a result.

[Scope and limits](reference/scope.md) lists what the project supports.
