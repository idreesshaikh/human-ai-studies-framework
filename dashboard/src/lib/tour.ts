/**
 * The guided tour's data + sequencing (FR-DASH-9). Pure module: the runes
 * store (tour.svelte.ts) and overlay (GuidedTour.svelte) consume it; vitest
 * covers it in node. Copy rules: plain English, 2-3 sentences per step, one
 * "why it matters" line, no requirement IDs except the decoder step.
 */

import type { View } from './router.svelte'

export interface TourStep {
  id: string
  /** The view to navigate to before showing this step. */
  view: View
  /** `[data-tour="…"]` anchor to spotlight; '' = centered card, full scrim. */
  anchor: string
  title: string
  body: string
  why?: string
  /** Skipped when the study has no sessions yet. */
  needsSession?: boolean
}

export const TOUR_STEPS: readonly TourStep[] = [
  {
    id: 'welcome',
    view: 'overview',
    anchor: 'nav',
    title: 'Welcome to Mission Control',
    body:
      'This dashboard is your study’s control room. Everything on it is computed live from two sources: your study protocol (one YAML file that declares the whole study) and the data your instruments send in. The sidebar lists the views - this tour visits each one.',
    why: 'You never configure the dashboard; it reads your study and explains itself.',
  },
  {
    id: 'sessions-collected',
    view: 'overview',
    anchor: 'overview-sessions',
    title: 'The study at a glance',
    body:
      'This counter compares the sessions you have collected against the plan in your protocol - each participant works once with AI assistance and once without (the two conditions). The grid below shows exactly which sessions exist and whether their data arrived intact.',
    why: 'One glance answers: am I on track, and is my data complete?',
  },
  {
    id: 'research-questions',
    view: 'overview',
    anchor: 'overview-rqs',
    title: 'Research questions drive everything',
    body:
      'These are your study’s research questions, straight from the protocol. Each names the analyses (recipes) that will answer it: a check means an analysis is planned, a warning means a question has no way to be answered yet.',
    why: 'If a question can’t be answered, you find out before the study runs - not after.',
  },
  {
    id: 'trace-chips',
    view: 'overview',
    anchor: 'trace-chip',
    title: 'The little "i" toggles explain everything',
    body:
      'Every chart and card carries an info toggle. Hover it for a plain-English explanation of what the panel answers; click it for the full chain from the underlying requirement to the numbers on screen.',
    why: 'Every chart can prove why it exists and where its data comes from.',
  },
  {
    id: 'lifecycle',
    view: 'board',
    anchor: 'lifecycle-board',
    title: 'Your study is a pipeline with gates',
    body:
      'A study moves through phases - design, ethics, pilot, recruitment, data collection, analysis, write-up. Each phase opens only when its gate documents are uploaded (an ethics approval, a consent form…). The demo study is deliberately parked at the ethics gate.',
    why: 'The framework physically cannot let you collect data before ethics clears.',
  },
  {
    id: 'task-board',
    view: 'tasks',
    anchor: 'task-board',
    title: 'A project manager that runs itself',
    body:
      'These cards are not a to-do list you maintain - they are derived live from your study’s state. A missing gate document, an unanswerable research question, a data problem: each becomes a card, and each card clears itself the moment the underlying issue is fixed.',
    why: 'Nothing to groom, nothing to forget.',
  },
  {
    id: 'live-sessions',
    view: 'live',
    anchor: 'live-cards',
    title: 'Watch sessions as they happen',
    body:
      'During a session every instrument streams its events here. The red warning on the demo session is intentional: a gap was planted in the sample data to show that lost data is always detected and reported - never silently missing.',
    why: 'If something breaks mid-session you know immediately, without ever interrupting the participant.',
  },
  {
    id: 'timeline',
    view: 'sessions',
    anchor: 'timeline',
    needsSession: true,
    title: 'One session, every angle',
    body:
      'Each lane is one instrument’s view of the same session - self-reports, editing behavior, code metrics, and the AI conversation - on a single shared clock. Drag across the chart to zoom into a moment.',
    why: 'You can see what the participant felt, did, and asked the AI - at the same instant.',
  },
  {
    id: 'metrics',
    view: 'metrics',
    anchor: 'metrics-chart',
    title: 'Honest statistics, by construction',
    body:
      'Code-complexity metrics are compared between the two conditions. Every dot is a real observation and every group shows its own sample size; with pilot-sized data the platform deliberately refuses to overstate - summary boxes appear only when there is enough data to justify them.',
    why: 'Small studies get honest pictures, not misleading ones.',
  },
  {
    id: 'knowledge-graph',
    view: 'knowledge',
    anchor: 'knowledge-graph',
    title: 'Your literature, connected',
    body:
      'Papers you add - by DOI, arXiv id, PDF upload, or straight from a Zotero collection - grow a citation graph. Solid dots are in your library and link to the parts of the study they justify; hollow dots are suggestions worth reading.',
    why: 'Related work builds itself while you design the study.',
  },
  {
    id: 'assistant',
    view: 'knowledge',
    anchor: 'knowledge-assistant',
    title: 'Ask about your own study',
    body:
      'The assistant answers questions grounded only in your ingested papers and aggregate study statistics - by design it cannot see any individual participant’s data, and every claim carries a citation. It needs an API key; without one, everything else keeps working.',
    why: 'Ethics-safe help: useful answers with sources, zero privacy risk.',
  },
  {
    id: 'done',
    view: 'overview',
    anchor: '',
    title: 'That’s the platform',
    body:
      'Protocol in, paper out: declare the study once, run instrumented sessions, then generate the report, the LaTeX paper draft, and a replication kit - one command each. Retake this tour any time from the sidebar; TOUR.md in the repository is the written version.',
  },
]

/** The steps a given study can actually show (no-session studies skip the timeline). */
export function visibleSteps(
  steps: readonly TourStep[],
  hasSession: boolean,
): TourStep[] {
  return steps.filter((s) => !s.needsSession || hasSession)
}

/**
 * Index of the next visible step from `from` in direction `dir`, or null
 * when the tour would walk off either end.
 */
export function nextStepIndex(
  steps: readonly TourStep[],
  from: number,
  dir: 1 | -1,
  hasSession: boolean,
): number | null {
  for (let i = from + dir; i >= 0 && i < steps.length; i += dir) {
    if (!steps[i].needsSession || hasSession) return i
  }
  return null
}
