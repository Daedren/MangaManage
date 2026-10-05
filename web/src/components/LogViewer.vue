<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useLogsStore } from '../stores/logs';

const props = defineProps<{ runId?: string }>();
const logsStore = useLogsStore();
const output = ref<HTMLElement>();
const following = ref(true);
let mounted = false;

onMounted(() => {
  mounted = true;
  void logsStore.start(props.runId || undefined);
});
onUnmounted(() => {
  mounted = false;
  logsStore.stop();
});
watch(() => props.runId, (runId) => {
  if (mounted) {
    following.value = true;
    void logsStore.start(runId || undefined);
  }
});
watch(() => logsStore.logs, async () => {
  if (!following.value) return;
  await nextTick();
  if (output.value) output.value.scrollTop = output.value.scrollHeight;
});

function onScroll() {
  const element = output.value;
  if (element) following.value = element.scrollHeight - element.scrollTop - element.clientHeight < 32;
}

function followLatest() {
  following.value = true;
  if (output.value) output.value.scrollTop = output.value.scrollHeight;
}
</script>

<template>
  <section class="log-viewer" aria-label="Task output">
    <div class="log-toolbar">
      <span role="status">{{ logsStore.connection === 'live' ? 'Live output' : logsStore.connection === 'complete' ? 'Run complete' : logsStore.connection === 'offline' ? 'Offline' : logsStore.connection === 'reconnecting' ? 'Reconnecting…' : 'Connecting…' }}</span>
      <div class="log-actions">
        <button v-if="!following" class="ghost" @click="followLatest">Follow latest</button>
        <button class="ghost" :disabled="logsStore.isLoading" @click="logsStore.fetchLogs">Refresh</button>
      </div>
    </div>
    <p v-if="logsStore.error" class="log-error" role="status">{{ logsStore.error }}</p>
    <p v-if="logsStore.truncated" class="log-note">Showing recent output only; older output remains in the log file.</p>
    <pre ref="output" class="log-output" tabindex="0" aria-label="Log output" @scroll="onScroll">{{ logsStore.logs || (logsStore.isLoading ? 'Loading…' : !logsStore.exists ? 'No run logs have been captured yet.' : 'Waiting for output…') }}</pre>
  </section>
</template>

<style scoped>
.log-viewer {
  border: 1px solid var(--color-rule-strong);
  border-radius: var(--radius-lg);
  overflow: hidden;
  min-width: 0;
}
.log-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  font-size: var(--text-sm);
  border-bottom: 1px solid var(--color-rule);
}
.log-actions { display: flex; gap: var(--space-2); }
.log-note, .log-error {
  padding: var(--space-2) var(--space-4);
  font-size: var(--text-sm);
  max-width: none;
}
.log-error { color: var(--color-error); }
.log-note { color: var(--color-ink-2); }
.log-output {
  margin: 0;
  min-height: 10rem;
  max-height: 60vh;
  overflow: auto;
  overflow-anchor: none;
  background: var(--color-term-bg);
  color: var(--color-term-ink);
  font-family: var(--font-display);
  font-size: var(--text-sm);
  line-height: var(--leading-normal);
  padding: var(--space-5) var(--space-6);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  tab-size: 2;
}
@media (max-width: 640px) {
  .log-output { font-size: var(--text-xs); padding: var(--space-4); }
}
</style>
