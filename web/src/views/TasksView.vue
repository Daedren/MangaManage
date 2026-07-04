<script setup lang="ts">
import { ref } from 'vue';
import { useTasksStore } from '../stores/tasks';
import { useLogsStore } from '../stores/logs';

const tasksStore = useTasksStore();
const logsStore = useLogsStore();
const series = ref('');
const anilistId = ref('');

const runAndRefreshLogs = async (action: () => Promise<unknown>) => {
  try {
    await action();
    await logsStore.fetchLogs();
  } catch {
    await logsStore.fetchLogs();
  }
};

const updateAnilistId = async () => {
  if (!series.value.trim() || !anilistId.value.trim()) {
    return;
  }

  await runAndRefreshLogs(() => tasksStore.updateAnilistId(series.value.trim(), anilistId.value.trim()));
};
</script>

<template>
  <main class="tasks-page">
    <section class="tasks-header">
      <div>
        <h1>Tasks</h1>
        <p>Run the same maintenance entrypoints exposed by the CLI.</p>
      </div>
      <RouterLink to="/logs" class="logs-link">View logs</RouterLink>
    </section>

    <p v-if="tasksStore.error" class="error-message">{{ tasksStore.error }}</p>
    <p v-else-if="tasksStore.lastMessage" class="success-message">{{ tasksStore.lastMessage }}</p>
    <p v-if="tasksStore.isRunning" class="running-message">Running {{ tasksStore.activeTask }}...</p>

    <section class="task-grid">
      <article class="task-card">
        <h2>Process Source</h2>
        <p>Run the default import/archive/delete/quarantine workflow.</p>
        <button :disabled="tasksStore.isRunning" @click="runAndRefreshLogs(tasksStore.processSource)">
          Process source
        </button>
      </article>

      <article class="task-card">
        <h2>Missing SQL</h2>
        <p>Find archive files that are missing database rows, or insert rows for them.</p>
        <div class="button-row">
          <button :disabled="tasksStore.isRunning" @click="runAndRefreshLogs(() => tasksStore.checkMissingSql(false))">
            Check only
          </button>
          <button class="warning" :disabled="tasksStore.isRunning" @click="runAndRefreshLogs(() => tasksStore.checkMissingSql(true))">
            Check and fix
          </button>
        </div>
      </article>

      <article class="task-card">
        <h2>Missing Chapters</h2>
        <p>Check all series for tracker or consecutive chapter gaps and update quarantine state.</p>
        <button :disabled="tasksStore.isRunning" @click="runAndRefreshLogs(tasksStore.checkMissingChapters)">
          Check chapters
        </button>
      </article>

      <article class="task-card">
        <h2>MangaUpdates</h2>
        <p>Update MangaUpdates IDs and check for releases newer than the archive.</p>
        <button :disabled="tasksStore.isRunning" @click="runAndRefreshLogs(tasksStore.checkMangaUpdates)">
          Check updates
        </button>
      </article>

      <article class="task-card update-card">
        <h2>Update AniList ID</h2>
        <p>Manually map a local series name to an AniList media ID.</p>
        <label>
          Series
          <input v-model="series" :disabled="tasksStore.isRunning" type="text" placeholder="Series name" />
        </label>
        <label>
          AniList ID
          <input v-model="anilistId" :disabled="tasksStore.isRunning" type="text" placeholder="12345" />
        </label>
        <button :disabled="tasksStore.isRunning || !series.trim() || !anilistId.trim()" @click="updateAnilistId">
          Update ID
        </button>
      </article>
    </section>
  </main>
</template>

<style scoped>
.tasks-page {
  width: min(1100px, 100%);
  margin: 0 auto;
}

.tasks-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.tasks-header p {
  margin: 0.25rem 0 0;
  color: #5f6f5f;
}

.logs-link {
  color: #315c3a;
  font-weight: 700;
}

.task-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 1rem;
}

.task-card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem;
  border: 1px solid #c9d5c7;
  border-radius: 8px;
  background: #f8fbf6;
}

.task-card h2 {
  margin: 0;
  font-size: 1.1rem;
}

.task-card p {
  flex: 1;
  margin: 0;
  color: #4f5d4f;
}

.button-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

button {
  width: fit-content;
  padding: 0.55rem 0.9rem;
  background-color: #315c3a;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 700;
}

button.warning {
  background-color: #7a4a16;
}

button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.update-card label {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-weight: 700;
}

input {
  padding: 0.5rem;
  border: 1px solid #adc0aa;
  border-radius: 4px;
}

.error-message {
  color: #b3261e;
}

.success-message {
  color: #315c3a;
  font-weight: 700;
}

.running-message {
  color: #7a4a16;
}

@media (max-width: 640px) {
  .tasks-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
