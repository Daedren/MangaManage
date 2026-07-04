<script setup lang="ts">
import { onMounted } from 'vue';
import { useLogsStore } from '../stores/logs';

const logsStore = useLogsStore();

onMounted(() => {
  logsStore.fetchLogs();
});
</script>

<template>
  <main>
    <div class="logs-header">
      <h1>Logs</h1>
      <button @click="logsStore.fetchLogs" :disabled="logsStore.isLoading">
        {{ logsStore.isLoading ? 'Refreshing...' : 'Refresh' }}
      </button>
    </div>

    <p v-if="logsStore.error" class="error-message">{{ logsStore.error }}</p>
    <p v-else-if="logsStore.isLoading">Loading logs...</p>
    <p v-else-if="!logsStore.exists">No run logs have been captured yet.</p>
    <pre v-else class="log-output">{{ logsStore.logs || 'No log output was recorded.' }}</pre>
  </main>
</template>

<style scoped>
.logs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

button {
  padding: 0.5rem 1rem;
  background-color: #315c3a;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.error-message {
  color: #b3261e;
}

.log-output {
  max-height: 70vh;
  overflow: auto;
  padding: 1rem;
  border: 1px solid #8fa58c;
  border-radius: 6px;
  background-color: #101510;
  color: #e7f1e4;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
