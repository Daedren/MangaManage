<script setup lang="ts">
import { onMounted } from 'vue';
import { useLogsStore } from '../stores/logs';

const logsStore = useLogsStore();

onMounted(() => {
  logsStore.fetchLogs();
});
</script>

<template>
  <main class="logs-page">

    <!-- Page header -->
    <header class="page-header">
      <div class="page-header__text">
        <h1>Logs</h1>
        <p class="page-subtitle">Output from the last task run.</p>
      </div>
      <button
        @click="logsStore.fetchLogs"
        :disabled="logsStore.isLoading"
        class="ghost"
        aria-label="Refresh logs"
      >
        {{ logsStore.isLoading ? 'Refreshing…' : 'Refresh' }}
      </button>
    </header>

    <!-- States -->
    <p v-if="logsStore.error"     class="state-message state-message--error">{{ logsStore.error }}</p>
    <p v-else-if="logsStore.isLoading"             class="state-message">Loading…</p>
    <p v-else-if="!logsStore.exists"               class="state-message state-message--empty">No run logs have been captured yet.</p>

    <!-- Terminal output -->
    <div v-else class="terminal-wrap">
      <div class="terminal-chrome" aria-hidden="true">
        <span class="chrome-dot chrome-dot--1"></span>
        <span class="chrome-dot chrome-dot--2"></span>
        <span class="chrome-dot chrome-dot--3"></span>
        <span class="chrome-label">stdout</span>
      </div>
      <pre class="log-output" role="log" aria-label="Log output">{{ logsStore.logs || 'No log output was recorded.' }}</pre>
    </div>

  </main>
</template>

<style scoped>
.logs-page {
  /* inherits max-width + padding from main.css */
}

/* ─── Page header ────────────────────────────────────────────────── */
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-6);
  padding-bottom: var(--space-5);
  border-bottom: 1px solid var(--color-rule);
}

.page-subtitle {
  margin-top: var(--space-1);
  font-size: var(--text-sm);
  color: var(--color-ink-2);
  max-width: none;
}

/* ─── State messages ─────────────────────────────────────────────── */
.state-message {
  font-size: var(--text-sm);
  color: var(--color-ink-2);
  padding: var(--space-8) 0;
  max-width: none;
}

.state-message--error { color: var(--color-error); }
.state-message--empty { color: var(--color-ink-3); font-style: normal; }

/* ─── Terminal ───────────────────────────────────────────────────── */
.terminal-wrap {
  border: 1px solid var(--color-rule-strong);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

/* Chrome bar — purely decorative labels, no fake dots */
.terminal-chrome {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  background: var(--color-term-bg);
  border-bottom: 1px solid oklch(22% 0.015 145);
}

.chrome-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.chrome-dot--1 { background: oklch(56% 0.14  25); }  /* close — muted red   */
.chrome-dot--2 { background: oklch(60% 0.12  75); }  /* minimise — muted amber */
.chrome-dot--3 { background: oklch(56% 0.10 145); }  /* full screen — green */

.chrome-label {
  margin-left: auto;
  font-family: var(--font-display);
  font-size: var(--text-xs);
  color: var(--color-term-muted);
  letter-spacing: 0.10em;
  text-transform: uppercase;
}

/* Terminal output pane */
.log-output {
  display: block;
  background: var(--color-term-bg);
  color: var(--color-term-ink);
  font-family: var(--font-display);
  font-size: var(--text-sm);
  line-height: var(--leading-normal);
  padding: var(--space-5) var(--space-6);
  max-height: 72vh;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
  min-width: 0;
  tab-size: 2;
}

/* Scrollbar — terminal-themed */
.log-output::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.log-output::-webkit-scrollbar-track {
  background: var(--color-term-bg);
}
.log-output::-webkit-scrollbar-thumb {
  background: oklch(30% 0.015 145);
  border-radius: 3px;
}
.log-output::-webkit-scrollbar-thumb:hover {
  background: oklch(40% 0.020 145);
}

/* ─── Mobile ─────────────────────────────────────────────────────── */
@media (max-width: 640px) {
  .page-header {
    flex-direction: column;
    gap: var(--space-2);
  }

  .log-output {
    font-size: var(--text-xs);
    padding: var(--space-4);
    max-height: 60vh;
  }
}
</style>
