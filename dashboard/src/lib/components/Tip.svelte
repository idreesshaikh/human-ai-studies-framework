<script lang="ts">
  import type { Snippet } from 'svelte'
  import { placeTip } from '../place'

  /**
   * Anchored plain-language tooltip (FR-DASH-9). Wrap any inline element;
   * the text appears above it (flipping below near the top edge) on hover
   * or keyboard focus, after a short delay. Touch: tap toggles. Empty text
   * renders the children untouched.
   */
  let { text, children }: { text: string; children: Snippet } = $props()

  const tipId = $props.id()
  let wrap: HTMLSpanElement | undefined = $state()
  let tipEl: HTMLDivElement | undefined = $state()
  let visible = $state(false)
  let pos = $state({ x: -9999, y: -9999 })
  let timer: number | undefined

  function show(delay = 250) {
    if (!text) return
    clearTimeout(timer)
    timer = window.setTimeout(() => (visible = true), delay)
  }

  function hide() {
    clearTimeout(timer)
    visible = false
  }

  function onPointerdown(e: PointerEvent) {
    if (e.pointerType === 'touch') {
      clearTimeout(timer)
      visible = !visible
    }
  }

  // Position after the tooltip has rendered (it starts off-screen, so the
  // first measured frame never flickers in the wrong place).
  $effect(() => {
    if (visible && wrap && tipEl) {
      pos = placeTip(
        wrap.getBoundingClientRect(),
        { width: tipEl.offsetWidth, height: tipEl.offsetHeight },
        { width: window.innerWidth, height: window.innerHeight },
      )
    }
  })

  // While visible: describe the focusable child for screen readers, close
  // on outside taps and on scroll (the tooltip is fixed; drifting is worse
  // than hiding).
  $effect(() => {
    if (!visible || !wrap) return
    const target = wrap.querySelector('button, a, input, select, [tabindex]')
    target?.setAttribute('aria-describedby', tipId)
    const outside = (e: PointerEvent) => {
      if (!wrap!.contains(e.target as Node)) hide()
    }
    const onScroll = () => hide()
    document.addEventListener('pointerdown', outside)
    window.addEventListener('scroll', onScroll, { capture: true, passive: true })
    return () => {
      target?.removeAttribute('aria-describedby')
      document.removeEventListener('pointerdown', outside)
      window.removeEventListener('scroll', onScroll, { capture: true })
    }
  })
</script>

<!-- Presentational wrapper: the handlers only proxy hover/focus for the
     interactive child it wraps; the tooltip is described via aria-describedby. -->
<span
  bind:this={wrap}
  role="presentation"
  class="tip-wrap"
  onmouseenter={() => show()}
  onmouseleave={hide}
  onfocusin={() => show(100)}
  onfocusout={hide}
  onkeydown={(e) => e.key === 'Escape' && hide()}
  onpointerdown={onPointerdown}
>
  {@render children()}
</span>

{#if visible && text}
  <div
    bind:this={tipEl}
    id={tipId}
    role="tooltip"
    class="tip"
    style:left="{pos.x}px"
    style:top="{pos.y}px"
  >
    {text}
  </div>
{/if}

<style>
  .tip-wrap {
    display: inline-flex;
  }

  .tip {
    position: fixed;
    z-index: 70;
    max-width: 280px;
    padding: 8px 10px;
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-secondary);
    font-size: 12px;
    line-height: 1.45;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
    pointer-events: none;
  }
</style>
