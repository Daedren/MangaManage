<script setup lang="ts">
import LogViewer from '../components/LogViewer.vue';
</script>

<template>
  <main class="logs-page">
    <header class="page-header">
      <h1>Logs</h1>
      <p class="page-subtitle">Live output from the latest CLI or API run.</p>
    </header>
    <LogViewer />
  </main>
</template>

<style scoped>
.page-header {
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
</style>
