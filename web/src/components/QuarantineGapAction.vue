<script setup lang="ts">
import { computed } from 'vue';
import { gapDownloadKey, useSeriesStore } from '../stores/series';
import type { QuarantineReason } from '../stores/series';

const props = defineProps<{ anilistId: number; series: string; reason: QuarantineReason }>();
const seriesStore = useSeriesStore();
const state = computed(() => seriesStore.gapDownloads[gapDownloadKey(props.anilistId, props.reason)]);
const result = computed(() => state.value?.result);
const bounds = computed(() => props.reason.type === 'tracker_gap'
  ? [props.reason.last_read, props.reason.first_stored]
  : [props.reason.before, props.reason.after]);
</script>

<template>
  <div :aria-busy="state?.loading || false">
    <div class="gap-action">
      <span v-if="reason.type === 'tracker_gap'">Last read chapter {{ reason.last_read }}; first stored chapter is {{ reason.first_stored }}.</span>
      <span v-else>Gap between stored chapters {{ reason.before }} and {{ reason.after }}.</span>
      <button type="button" class="ghost gap-download"
        :disabled="state?.loading"
        :aria-label="`Download missing chapters for ${series} between chapters ${bounds[0]} and ${bounds[1]}`"
        @click="seriesStore.downloadQuarantineGap(anilistId, reason)">
        {{ state?.loading ? 'Checking Suwayomi…' : 'Download missing chapters' }}
      </button>
    </div>
    <p v-if="state?.error" class="gap-feedback gap-feedback--error" role="alert">{{ state.error }}</p>
    <div v-if="result" class="gap-feedback" role="status" aria-live="polite">
      <p v-if="result.status === 'no_source'">No linked Suwayomi source found. Link this series to AniList in your Suwayomi library first.</p>
      <p v-else-if="result.status === 'no_matches'">No chapters inside this gap were found on the checked Suwayomi sources.</p>
      <p v-else-if="result.queued_chapters.length">
        Queued {{ result.queued_chapters.length }} {{ result.queued_chapters.length === 1 ? 'chapter' : 'chapters' }} in Suwayomi: {{ result.queued_chapters.join(', ') }}.
      </p>
      <p v-if="result.already_downloaded.length">
        Already downloaded in Suwayomi: {{ result.already_downloaded.join(', ') }}. Import these chapters to fill the gap.
      </p>
      <p v-if="result.already_queued.length">Already queued in Suwayomi: {{ result.already_queued.join(', ') }}.</p>
      <p v-for="warning in result.warnings" :key="warning">{{ warning }}</p>
    </div>
  </div>
</template>

<style scoped>
.gap-action { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-2) var(--space-4); }
.gap-download { padding: var(--space-1) var(--space-2); font-size: var(--text-xs); white-space: nowrap; }
.gap-feedback { margin-top: var(--space-1); font-size: var(--text-xs); color: var(--color-ink-2); }
.gap-feedback p { max-width: none; }
.gap-feedback--error { color: var(--color-error); }

@media (max-width: 640px) {
  .gap-download { min-height: 44px; }
}
</style>
