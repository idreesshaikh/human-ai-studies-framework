# Scope and limits

StudyLoop supports task-based studies of human-AI software development. It connects
study design, participant capture and analysis hand-off through one explicit
protocol. This page says what that covers, what it does not, and what its numbers
and signals cannot show.

## What it supports

- Configuring questions, tasks, conditions, participants, measures and an analysis
  plan from templates, a conversation or a form.
- Compiling the decisions you review into a validated protocol.
- Deriving assignment, consent and instrumentation for TERN in VS Code.
- Collecting study-scoped events, with optional code or provider measurements.
- Running tagged pilot sessions to check capture and recipe compatibility.
- Exporting datasets, dictionaries, notebooks, reports and replication kits.
- Exploring literature and inspecting planning calculations with their assumptions.

## What it does not do

PHOENIX does not grant ethics approval, recruit participants, enforce university
workflows or certify statistical validity. It is not a general research assistant, a
paper-writing service, or a tool for exams, classrooms or surveys.

## What its numbers and signals cannot show

- **AI use.** TERN's signals are heuristics whose error rates have not been
  measured. They cannot verify that a no-AI condition stayed free of AI, and a
  missing signal does not show that no AI was used. See
  [Control-arm session review](../platform/control-arm-review.md).
- **Sample sizes.** An estimate depends on the effect, spread and dropout you
  assume. See [Plan recruitment](../platform/planning.md).
- **Capture.** TERN records editor and tool events. It excludes source text,
  keystrokes and clipboard content. Other tools you enable, such as transcript or
  snapshot capture, have their own content policies to review first. See
  [Privacy](../extension/privacy.md).
- **Examples.** Synthetic sessions are marked, left out of research exports and
  estimates, and never a finding.

## More detail

The repository documents the design behind these limits:

- [Scope](https://github.com/idreesshaikh/human-ai-studies-framework/blob/main/docs/scope.md)
  for the project's boundaries
- [Architecture](https://github.com/idreesshaikh/human-ai-studies-framework/blob/main/docs/architecture.md)
  for how the web app, server, TERN and analysis fit together
- [Planner guide](https://github.com/idreesshaikh/human-ai-studies-framework/blob/main/docs/planner.md)
  for methods, supported combinations and numerical checks

## Next steps

- [Design a study](../platform/index.md)
- [Install and run](../get-started/index.md)
