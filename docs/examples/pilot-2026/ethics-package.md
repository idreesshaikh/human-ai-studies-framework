# Ethics package: AI assistance and developer cognitive load: a within-subjects pilot

**Researchers:** Idrees Razak, Project Supervisor  
**Ethics reference:** UoM CS ethics application (pending — not yet obtained)  

## Research questions

- How does AI assistance affect self-reported cognitive load (fatigue probes, stuck episodes, TLX debrief)?
- How does AI assistance affect the static cognitive-load profile of the code produced (9-metric matrix over workspace snapshots)?
- How does AI assistance change working behavior - pasting, file switching, edit provenance, active vs idle time?
- How do developers review AI-generated code before accepting it (review latency, scroll coverage, accept rate by suggestion size)?
- How does the conversation with the agent unfold over a session - turn cadence, tool-call mix, reliance loops - and how does it relate to outcomes?

## Study design

- **Participants:** 6
- **Design:** within-subjects
- **Condition order:** counterbalanced
- **Conditions:** ai-assisted, unassisted
- **Session length:** 45 minutes

## What participants do

### 1. The study task

Two matched Python maintenance tasks (one per condition, order counterbalanced with condition pairing per the runbook's Latin square): Task A "expenses" and Task B "logbook", each a small existing codebase with two seeded defects and one feature request, shipped with acceptance tests providing outcome ground truth (FR-INST-16, via the task harness). In ai-assisted sessions the participant uses Claude Code in the integrated terminal; in unassisted sessions AI tooling is disabled.

## What is captured

Every instrument below records aggregates, shapes, and timings — never raw code content, keystrokes, or clipboard text.

- **Static metrics** (declared, switched off): Measures the shape of the code you produce.
- **Behavioral** (declared, switched off): Records what you did in the editor — never what you wrote.
- **Cognitive** (active): Asks how you're finding the work, in short probes timed into pauses.
- **Agent interaction** (declared, switched off): Records your coding-agent turns on the same timeline.

## Informed consent statement

The text below is shown to every participant before their session begins, and pairing cannot proceed without it (FR-INST-21). One version per condition, since the instruments a participant meets can differ by condition.

**ai-assisted condition:**

> You are joining "AI assistance and developer cognitive load: a within-subjects pilot" in the ai-assisted condition. While you work, this study captures aggregate signals from these instruments: agentCapture, metrics, tern. It never records raw code content, keystrokes, or clipboard text — only sizes, shapes, timings, and salted hashes. Agent-conversation capture is set to "metadata-only": Only the shape of your conversation with the AI assistant is recorded: how many messages, how long they were, when they were sent, and which tools the assistant used. The words of the conversation - your prompts and the assistant's replies - are never stored. You appear in all data only as an anonymized ID. You can stop the session at any time.

**unassisted condition:**

> You are joining "AI assistance and developer cognitive load: a within-subjects pilot" in the unassisted condition. While you work, this study captures aggregate signals from these instruments: agentCapture, metrics, tern. It never records raw code content, keystrokes, or clipboard text — only sizes, shapes, timings, and salted hashes. Agent-conversation capture is set to "metadata-only": Only the shape of your conversation with the AI assistant is recorded: how many messages, how long they were, when they were sent, and which tools the assistant used. The words of the conversation - your prompts and the assistant's replies - are never stored. You appear in all data only as an anonymized ID. You can stop the session at any time.

## Withdrawal

A participant may stop a session at any time, from within the editor, with no explanation required. Data already collected up to that point is retained unless the participant separately requests its deletion; nothing further is captured after the session ends.
