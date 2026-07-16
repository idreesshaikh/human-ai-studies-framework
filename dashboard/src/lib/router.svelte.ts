/**
 * Hand-rolled history router for the fixed route set (MP-06):
 *
 *   /study/:id/{overview|board|tasks|live|sessions/:sid|metrics|knowledge}
 *
 * A routing library would be a dependency for one URL shape (see
 * build-vs-adopt D18); the middleware re-serves the SPA shell for deep
 * links, so plain history navigation works in both dev and production.
 */

export type View =
  | 'overview'
  | 'board'
  | 'tasks'
  | 'live'
  | 'sessions'
  | 'metrics'
  | 'knowledge'

export interface Route {
  studyId: string | null
  view: View
  sessionId: string | null
}

const VIEWS: View[] = [
  'overview',
  'board',
  'tasks',
  'live',
  'sessions',
  'metrics',
  'knowledge',
]

export function parseRoute(path: string): Route {
  const m = path.match(/^\/study\/([^/]+)(?:\/([^/]+))?(?:\/([^/]+))?/)
  if (!m) return { studyId: null, view: 'overview', sessionId: null }
  const [, studyId, view, sessionId] = m
  if (view === 'sessions' && sessionId) {
    return { studyId, view: 'sessions', sessionId }
  }
  return {
    studyId,
    view: VIEWS.includes(view as View) ? (view as View) : 'overview',
    sessionId: null,
  }
}

class Router {
  path = $state(window.location.pathname)

  constructor() {
    window.addEventListener('popstate', () => {
      this.path = window.location.pathname
    })
  }

  readonly route: Route = $derived(parseRoute(this.path))

  go(to: string, replace = false): void {
    if (replace) window.history.replaceState({}, '', to)
    else window.history.pushState({}, '', to)
    this.path = to
  }

  studyHref(view: View, sessionId?: string): string {
    const study = this.route.studyId ?? ''
    const tail = sessionId ? `/sessions/${sessionId}` : `/${view}`
    return `/study/${encodeURIComponent(study)}${tail}`
  }
}

export const router = new Router()

/** Intercepts clicks on internal links so navigation stays client-side. */
export function link(node: HTMLAnchorElement): { destroy(): void } {
  const onClick = (e: MouseEvent) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return
    e.preventDefault()
    router.go(node.getAttribute('href') ?? '/')
  }
  node.addEventListener('click', onClick)
  return { destroy: () => node.removeEventListener('click', onClick) }
}
