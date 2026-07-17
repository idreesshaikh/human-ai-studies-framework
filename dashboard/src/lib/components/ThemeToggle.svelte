<script lang="ts">
  import { theme, type ThemeMode } from '../theme.svelte'

  const MODES: { mode: ThemeMode; label: string; glyph: string }[] = [
    { mode: 'light', label: 'Light theme', glyph: '☀' },
    { mode: 'system', label: 'Match system theme', glyph: '◐' },
    { mode: 'dark', label: 'Dark theme', glyph: '☾' },
  ]
</script>

<div class="theme-toggle" role="group" aria-label="Color theme">
  {#each MODES as m (m.mode)}
    <button
      type="button"
      title={m.label}
      aria-label={m.label}
      aria-pressed={theme.mode === m.mode}
      class:active={theme.mode === m.mode}
      onclick={() => theme.set(m.mode)}
    >
      {m.glyph}
    </button>
  {/each}
</div>

<style>
  .theme-toggle {
    display: inline-flex;
    gap: 2px;
    padding: 2px;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: color-mix(in srgb, var(--text-muted) 8%, transparent);
  }
  .theme-toggle button {
    border: none;
    background: none;
    border-radius: 999px;
    width: 24px;
    height: 24px;
    padding: 0;
    line-height: 1;
    font-size: 12px;
    color: var(--text-muted);
    cursor: pointer;
  }
  .theme-toggle button.active {
    background: var(--surface-1);
    color: var(--text-primary);
    box-shadow: 0 0 0 1px var(--border);
  }
</style>
