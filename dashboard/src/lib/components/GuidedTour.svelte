<script lang="ts">
  import { placeCard, type Rect } from '../place'
  import { TOUR_STEPS, nextStepIndex, visibleSteps } from '../tour'
  import { tour } from '../tour.svelte'

  /**
   * The guided-tour overlay (FR-DASH-9): a scrim with a spotlight cut out
   * around the current step's anchor, plus the step card. Hand-rolled -
   * one div's oversized box-shadow is the scrim, so the cut-out is
   * seam-free and follows the anchor on resize/scroll.
   */

  let anchorEl: Element | null = null
  let anchorRect = $state<Rect | null>(null)
  let cardEl = $state<HTMLDivElement>()
  let nextBtn = $state<HTMLButtonElement>()
  let cardW = $state(340)
  let cardH = $state(200)
  let vw = $state(window.innerWidth)
  let vh = $state(window.innerHeight)

  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches

  const hasSession = $derived(tour.sessionId !== null)
  const steps = $derived(visibleSteps(TOUR_STEPS, hasSession))
  const stepNo = $derived(tour.step ? steps.indexOf(tour.step) + 1 : 0)
  const isFirst = $derived(
    tour.index !== null && nextStepIndex(TOUR_STEPS, tour.index, -1, hasSession) === null,
  )
  const isLast = $derived(
    tour.index !== null && nextStepIndex(TOUR_STEPS, tour.index, 1, hasSession) === null,
  )

  /** Spotlight box: the anchor plus breathing room. */
  const spot = $derived(
    anchorRect && {
      x: anchorRect.x - 8,
      y: anchorRect.y - 8,
      width: anchorRect.width + 16,
      height: anchorRect.height + 16,
    },
  )
  const cardPos = $derived(
    placeCard(spot, { width: cardW, height: cardH }, { width: vw, height: vh }),
  )

  function measure() {
    vw = window.innerWidth
    vh = window.innerHeight
    if (anchorEl?.isConnected) {
      const r = anchorEl.getBoundingClientRect()
      anchorRect = { x: r.x, y: r.y, width: r.width, height: r.height }
    }
  }

  // Locate the step's anchor. The view may still be fetching, so poll
  // briefly; on timeout the card just centers - the tour never blocks.
  $effect(() => {
    const step = tour.step
    anchorEl = null
    anchorRect = null
    if (!step?.anchor) return
    let tries = 0
    const timer = setInterval(() => {
      const el = document.querySelector(`[data-tour="${step.anchor}"]`)
      if (el) {
        clearInterval(timer)
        anchorEl = el
        el.scrollIntoView({
          block: 'center',
          behavior: reducedMotion ? 'auto' : 'smooth',
        })
        measure()
      } else if (++tries >= 30) {
        clearInterval(timer)
      }
    }, 100)
    return () => clearInterval(timer)
  })

  // Follow the anchor while active (rAF-throttled), and own the keyboard.
  $effect(() => {
    if (!tour.active) return
    const previous = document.activeElement as HTMLElement | null
    let raf = 0
    const onMove = () => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(measure)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') tour.skip()
      else if (e.key === 'ArrowRight') tour.next()
      else if (e.key === 'ArrowLeft') tour.back()
      else if (e.key === 'Tab') {
        // Keep focus cycling inside the card while the page is inert.
        const focusables = [...(cardEl?.querySelectorAll('button') ?? [])]
        if (!focusables.length) return
        e.preventDefault()
        const i = focusables.indexOf(document.activeElement as HTMLButtonElement)
        const n = focusables.length
        focusables[(i + (e.shiftKey ? -1 : 1) + n) % n].focus()
      }
    }
    window.addEventListener('resize', onMove)
    window.addEventListener('scroll', onMove, { capture: true, passive: true })
    window.addEventListener('keydown', onKey)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onMove)
      window.removeEventListener('scroll', onMove, { capture: true })
      window.removeEventListener('keydown', onKey)
      if (previous?.isConnected) previous.focus()
    }
  })

  // Each step starts with Next focused, so Enter walks the whole tour.
  $effect(() => {
    if (tour.step) nextBtn?.focus()
  })
</script>

{#if tour.active && tour.step}
  <div class="blocker" aria-hidden="true"></div>
  {#if spot}
    <!-- Scrim as four rectangles around the cut-out: giant box-shadow
         spreads get clamped by the compositor, plain rects never do. -->
    <div class="shade" style:inset="0 0 auto 0" style:height="{Math.max(0, spot.y)}px"></div>
    <div
      class="shade"
      style:top="{spot.y}px"
      style:left="0"
      style:width="{Math.max(0, spot.x)}px"
      style:height="{spot.height}px"
    ></div>
    <div
      class="shade"
      style:top="{spot.y}px"
      style:left="{spot.x + spot.width}px"
      style:right="0"
      style:height="{spot.height}px"
    ></div>
    <div class="shade" style:inset="auto 0 0 0" style:top="{spot.y + spot.height}px"></div>
    <div
      class="spotlight"
      style:left="{spot.x}px"
      style:top="{spot.y}px"
      style:width="{spot.width}px"
      style:height="{spot.height}px"
    ></div>
  {:else}
    <div class="scrim" aria-hidden="true"></div>
  {/if}

  <div
    bind:this={cardEl}
    bind:clientWidth={cardW}
    bind:clientHeight={cardH}
    class="tour-card"
    role="dialog"
    aria-modal="true"
    aria-labelledby="tour-title"
    style:left="{cardPos.x}px"
    style:top="{cardPos.y}px"
  >
    <h3 id="tour-title">{tour.step.title}</h3>
    <p class="body">{tour.step.body}</p>
    {#if tour.step.why}
      <p class="why">{tour.step.why}</p>
    {/if}
    <div class="controls">
      <span class="counter">{stepNo} of {steps.length}</span>
      <button type="button" class="quiet" onclick={() => tour.skip()}>
        Skip tour
      </button>
      {#if !isFirst}
        <button type="button" onclick={() => tour.back()}>Back</button>
      {/if}
      <button
        bind:this={nextBtn}
        type="button"
        class="primary"
        onclick={() => tour.next()}
      >
        {isLast ? 'Done' : 'Next'}
      </button>
    </div>
  </div>
{/if}

<style>
  .blocker {
    position: fixed;
    inset: 0;
    z-index: 60;
  }

  .scrim {
    position: fixed;
    inset: 0;
    z-index: 60;
    background: rgba(0, 0, 0, 0.5);
    pointer-events: none;
  }

  .shade {
    position: fixed;
    z-index: 60;
    pointer-events: none;
    background: rgba(0, 0, 0, 0.45);
  }

  .spotlight {
    position: fixed;
    z-index: 60;
    pointer-events: none;
    border-radius: 10px;
    outline: 2px solid var(--series-1);
    outline-offset: 1px;
    transition:
      top 0.2s,
      left 0.2s,
      width 0.2s,
      height 0.2s;
  }

  .tour-card {
    position: fixed;
    z-index: 61;
    width: 340px;
    max-width: calc(100vw - 32px);
    padding: 16px 18px;
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 10px;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
    transition:
      top 0.2s,
      left 0.2s;
  }

  .tour-card h3 {
    margin: 0 0 8px;
    font-size: 15px;
  }

  .body {
    margin: 0 0 8px;
    font-size: 13px;
    line-height: 1.55;
    color: var(--text-secondary);
  }

  .why {
    margin: 0 0 10px;
    font-size: 12.5px;
    font-style: italic;
    color: var(--text-muted);
  }

  .controls {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .counter {
    margin-right: auto;
    font-size: 11px;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }

  .quiet {
    color: var(--text-muted);
    border-color: transparent;
    background: none;
  }

  .primary {
    background: var(--series-1);
    border-color: var(--series-1);
    color: #fff;
  }

  @media (prefers-reduced-motion: reduce) {
    .spotlight,
    .tour-card {
      transition: none;
    }
  }
</style>
