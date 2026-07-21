<script setup lang="ts">
import { ref } from 'vue';
import { useTasksStore } from '../stores/tasks';
import { useLogsStore } from '../stores/logs';

const tasksStore = useTasksStore();
const logsStore  = useLogsStore();
const series     = ref('');
const anilistId  = ref('');

const runAndRefreshLogs = async (action: () => Promise<unknown>) => {
  try {
    await action();
    await logsStore.fetchLogs();
  } catch {
    await logsStore.fetchLogs();
  }
};

const updateAnilistId = async () => {
  if (!series.value.trim() || !anilistId.value.trim()) return;
  await runAndRefreshLogs(() =>
    tasksStore.updateAnilistId(series.value.trim(), anilistId.value.trim()),
  );
};
</script>

<template>
  <main class="tasks-page">

    <!-- Page header -->
    <header class="page-header">
      <div class="page-header__text">
        <h1>Tasks</h1>
        <p class="page-subtitle">Run the same maintenance entrypoints exposed by the CLI.</p>
      </div>
      <RouterLink to="/logs" class="header-link">View logs →</RouterLink>
    </header>

    <!-- Status messages -->
    <div class="status-strip" role="status" aria-live="polite" aria-atomic="true">
      <p v-if="tasksStore.error"       class="status status--error">{{ tasksStore.error }}</p>
      <p v-else-if="tasksStore.lastMessage" class="status status--success">{{ tasksStore.lastMessage }}</p>
      <p v-if="tasksStore.isRunning"   class="status status--running">
        <span class="running-dot" aria-hidden="true"></span>
        Running {{ tasksStore.activeTask }}…
      </p>
    </div>

    <!-- Task grid -->
    <section class="task-grid" aria-label="Available tasks">

      <article class="task-card">
        <header class="task-card__header">
          <h2>Process Source</h2>
        </header>
        <p>Run the default import / archive / delete / quarantine workflow.</p>
        <footer class="task-card__footer">
          <button :disabled="tasksStore.isRunning" @click="runAndRefreshLogs(tasksStore.processSource)">
            Process source
          </button>
        </footer>
      </article>

      <article class="task-card">
        <header class="task-card__header">
          <h2>Missing SQL</h2>
        </header>
        <p>Find archive files missing database rows, or insert rows for them.</p>
        <footer class="task-card__footer task-card__footer--row">
          <button :disabled="tasksStore.isRunning" class="ghost" @click="runAndRefreshLogs(() => tasksStore.checkMissingSql(false))">
            Check only
          </button>
          <button :disabled="tasksStore.isRunning" class="warning" @click="runAndRefreshLogs(() => tasksStore.checkMissingSql(true))">
            Check and fix
          </button>
        </footer>
      </article>

      <article class="task-card">
        <header class="task-card__header">
          <h2>Missing Chapters</h2>
        </header>
        <p>Check all series for tracker or consecutive chapter gaps, update quarantine state.</p>
        <footer class="task-card__footer">
          <button :disabled="tasksStore.isRunning" @click="runAndRefreshLogs(tasksStore.checkMissingChapters)">
            Check chapters
          </button>
        </footer>
      </article>

      <article class="task-card">
        <header class="task-card__header">
          <h2>MangaUpdates</h2>
        </header>
        <p>Update MangaUpdates IDs and check for releases newer than the archive.</p>
        <footer class="task-card__footer">
          <button :disabled="tasksStore.isRunning" @click="runAndRefreshLogs(tasksStore.checkMangaUpdates)">
            Check updates
          </button>
        </footer>
      </article>

      <article class="task-card task-card--form">
        <header class="task-card__header">
          <h2>Update AniList ID</h2>
        </header>
        <p>Manually map a local series name to an AniList media ID.</p>
        <div class="form-fields">
          <label class="form-field">
            <span class="field-label">Series name</span>
            <input
              v-model="series"
              :disabled="tasksStore.isRunning"
              type="text"
              placeholder="e.g. Berserk"
              aria-label="Series name"
            />
          </label>
          <label class="form-field">
            <span class="field-label">AniList ID</span>
            <input
              v-model="anilistId"
              :disabled="tasksStore.isRunning"
              type="text"
              placeholder="e.g. 30002"
              aria-label="AniList ID"
            />
          </label>
        </div>
        <footer class="task-card__footer">
          <button
            :disabled="tasksStore.isRunning || !series.trim() || !anilistId.trim()"
            @click="updateAnilistId"
          >
            Update ID
          </button>
        </footer>
      </article>

    </section>
  </main>
</template>

<style scoped>
.tasks-page {
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

.header-link {
  font-family: var(--font-display);
  font-size: var(--text-xs);
  font-weight: var(--weight-medium);
  color: var(--color-ink-3);
  white-space: nowrap;
  margin-top: var(--space-2);
  letter-spacing: 0.04em;
}

.header-link:hover {
  color: var(--color-accent);
  text-decoration: none;
}

/* ─── Status strip ───────────────────────────────────────────────── */
.status-strip {
  margin-bottom: var(--space-5);
  min-height: 1.4em;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.status {
  font-size: var(--text-sm);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  max-width: none;
}

.status--error   { color: var(--color-error); }
.status--success { color: var(--color-success); font-weight: var(--weight-medium); }
.status--running { color: var(--color-running); }

/* Animated running dot */
.running-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-running);
  animation: pulse 1.4s var(--ease-in-out) infinite;
  flex-shrink: 0;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.3; }
}

@media (prefers-reduced-motion: reduce) {
  .running-dot { animation: none; opacity: 1; }
}

/* ─── Task grid ──────────────────────────────────────────────────── */
.task-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr));
  gap: var(--space-4);
}

/* ─── Task card ──────────────────────────────────────────────────── */
.task-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-5);
  background: var(--color-paper);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  transition: border-color var(--dur-fast) var(--ease-out),
              box-shadow var(--dur-fast) var(--ease-out);
}

.task-card:hover {
  border-color: var(--color-rule-strong);
  box-shadow: 0 2px 8px oklch(0% 0 0 / 0.04);
}

.task-card__header {
  border-bottom: 1px solid var(--color-rule);
  padding-bottom: var(--space-3);
}

.task-card h2 {
  font-size: var(--text-base);
  font-weight: var(--weight-medium);
  color: var(--color-ink);
  letter-spacing: -0.01em;
}

.task-card p {
  font-size: var(--text-sm);
  color: var(--color-ink-2);
  flex: 1;
  max-width: none;
  line-height: var(--leading-snug);
}

.task-card__footer {
  margin-top: auto;
  padding-top: var(--space-2);
}

.task-card__footer--row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

/* ─── Form card ──────────────────────────────────────────────────── */
.form-fields {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.field-label {
  font-family: var(--font-display);
  font-size: var(--text-xs);
  font-weight: var(--weight-medium);
  color: var(--color-ink-2);
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.form-field input {
  width: 100%;
}

/* ─── Mobile ─────────────────────────────────────────────────────── */
@media (max-width: 640px) {
  .page-header {
    flex-direction: column;
    gap: var(--space-2);
  }
}
</style>
