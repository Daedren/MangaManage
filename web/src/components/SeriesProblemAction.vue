<script setup lang="ts">
import { computed } from 'vue';
import { problemDownloadKey, useSeriesStore } from '../stores/series';
import type { SeriesProblem } from '../stores/series';

const props = defineProps<{ anilistId: number; series: string; problem: SeriesProblem }>();
const store = useSeriesStore();
const state = computed(() => store.problemDownloads[problemDownloadKey(props.anilistId, props.problem)]);
const result = computed(() => state.value?.result);
const description = computed(() => {
  const problem = props.problem;
  switch (problem.type) {
    case 'tracker_gap': return `Last read chapter ${problem.last_read}; first stored chapter is ${problem.first_stored}.`;
    case 'consecutive_gap': return `Gap between stored chapters ${problem.before} and ${problem.after}.`;
    case 'mangaupdates_lag': return `Stored chapters and read progress reach chapter ${problem.after}; MangaUpdates lists chapter ${problem.through}.`;
  }
});
const buttonLabel = computed(() => props.problem.type === 'mangaupdates_lag'
  ? `Download chapters up to ${props.problem.through}` : 'Download missing chapters');
</script>

<template>
  <div :aria-busy="state?.loading || false">
    <div class="problem-action">
      <span>{{ description }}</span>
      <button type="button" class="ghost problem-download"
        :disabled="state?.loading || store.seriesProblems[anilistId]?.loading"
        :aria-label="`${buttonLabel} for ${series}. ${description}`"
        @click="store.downloadSeriesProblem(anilistId, problem)">
        {{ state?.loading ? 'Checking Suwayomi…' : buttonLabel }}
      </button>
    </div>
    <p v-if="state?.error" class="problem-feedback problem-feedback--error" role="alert">{{ state.error }}</p>
    <div v-if="result" class="problem-feedback" role="status" aria-live="polite">
      <p v-if="result.status === 'no_source'">No linked Suwayomi source found. Link this series to AniList in your Suwayomi library first.</p>
      <p v-else-if="result.status === 'no_matches'">No chapters in this range were found on the checked Suwayomi sources.</p>
      <p v-else-if="result.queued_chapters.length">
        Queued {{ result.queued_chapters.length }} {{ result.queued_chapters.length === 1 ? 'chapter' : 'chapters' }} in Suwayomi: {{ result.queued_chapters.join(', ') }}.
      </p>
      <p v-if="result.already_downloaded.length">Already downloaded in Suwayomi: {{ result.already_downloaded.join(', ') }}. Import these chapters, then check again.</p>
      <p v-if="result.already_queued.length">Already queued in Suwayomi: {{ result.already_queued.join(', ') }}.</p>
      <p v-for="warning in result.warnings" :key="warning">{{ warning }}</p>
    </div>
  </div>
</template>

<style scoped>
.problem-action { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-2) var(--space-4); }
.problem-download { padding: var(--space-1) var(--space-2); font-size: var(--text-xs); white-space: nowrap; }
.problem-feedback { margin-top: var(--space-1); font-size: var(--text-xs); color: var(--color-ink-2); }
.problem-feedback p { max-width: none; }
.problem-feedback--error { color: var(--color-error); }
@media (max-width: 640px) {
  .problem-download { min-height: 44px; }
}
</style>
