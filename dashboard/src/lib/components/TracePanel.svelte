<script lang="ts">
  import { trace } from '../trace.svelte'
</script>

{#if trace.openId}
  <aside class="panel" aria-label="Trace chain">
    <header>
      <h3>Trace: <code>{trace.openId}</code></h3>
      <button onclick={() => trace.close()} aria-label="Close">x</button>
    </header>
    <ol>
      {#each trace.chain(trace.openId) as step (step.label)}
        <li>
          <div class="label">{step.label}</div>
          <div class="secondary small">{step.detail}</div>
        </li>
      {/each}
    </ol>
  </aside>
{/if}

<style>
  .panel {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: 340px;
    background: var(--surface-1);
    border-left: 1px solid var(--border);
    box-shadow: -8px 0 24px rgba(0, 0, 0, 0.08);
    padding: 16px;
    overflow-y: auto;
    z-index: 40;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }
  ol {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  li {
    padding: 10px 0 10px 14px;
    border-left: 2px solid var(--baseline);
    position: relative;
  }
  li::before {
    content: '';
    position: absolute;
    left: -5px;
    top: 16px;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--series-1);
    box-shadow: 0 0 0 2px var(--surface-1);
  }
  .label {
    font-weight: 600;
  }
</style>
