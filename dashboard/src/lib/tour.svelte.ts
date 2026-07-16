/**
 * Guided-tour state machine (FR-DASH-9). Auto-starts once per browser
 * (localStorage flag), re-launchable from the sidebar; each step navigates
 * to its view through the normal router, so the tour walks the real app.
 */

import { api } from './api'
import { router } from './router.svelte'
import { trace } from './trace.svelte'
import { nextStepIndex, TOUR_STEPS, type TourStep } from './tour'

export const TOUR_DONE_KEY = 'dashboard.tourDone'

class TourState {
  /** Index into TOUR_STEPS, or null when idle. */
  index = $state<number | null>(null)
  /** First session of the study, for the timeline step; null skips it. */
  sessionId = $state<string | null>(null)

  readonly step: TourStep | null = $derived(
    this.index === null ? null : (TOUR_STEPS[this.index] ?? null),
  )
  readonly active: boolean = $derived(this.index !== null)

  async start(studyId: string): Promise<void> {
    trace.close()
    this.sessionId = null
    try {
      const status = await api.status(studyId)
      this.sessionId = status.sessions[0]?.sessionId ?? null
    } catch {
      // No reachable status - the timeline step is simply skipped.
    }
    this.show(0)
  }

  /** First-run only; a dismissed/finished tour never auto-reopens. */
  maybeAutoStart(studyId: string): void {
    let done: string | null = '1'
    try {
      done = localStorage.getItem(TOUR_DONE_KEY)
    } catch {
      // Storage unavailable (private mode): don't force the tour on
      // someone who may have dismissed it before.
    }
    if (!done) void this.start(studyId)
  }

  next(): void {
    if (this.index === null) return
    const i = nextStepIndex(TOUR_STEPS, this.index, 1, this.sessionId !== null)
    if (i === null) this.finish()
    else this.show(i)
  }

  back(): void {
    if (this.index === null) return
    const i = nextStepIndex(TOUR_STEPS, this.index, -1, this.sessionId !== null)
    if (i !== null) this.show(i)
  }

  skip(): void {
    this.finish()
  }

  finish(): void {
    this.index = null
    try {
      localStorage.setItem(TOUR_DONE_KEY, '1')
    } catch {
      // Private mode: the tour will re-offer next visit. Harmless.
    }
  }

  private show(i: number): void {
    this.index = i
    const step = TOUR_STEPS[i]
    const href =
      step.view === 'sessions'
        ? router.studyHref('sessions', this.sessionId ?? undefined)
        : router.studyHref(step.view)
    if (router.path !== href) router.go(href)
  }
}

export const tour = new TourState()
