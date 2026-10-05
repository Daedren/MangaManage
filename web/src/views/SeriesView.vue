<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useSeriesStore } from '../stores/series';
import type { MangaUpdatesStatus, SortColumn, SortDirection } from '../stores/series';

const seriesStore = useSeriesStore();
const PAGE_SIZE = 50;
const titleFilter = ref('');
const appliedTitle = ref('');
const quarantineFilter = ref('all');
const appliedQuarantine = ref('all');
const mangaUpdatesStatusFilter = ref<'all' | MangaUpdatesStatus>('all');
const appliedMangaUpdatesStatus = ref<'all' | MangaUpdatesStatus>('all');
const sortBy = ref<SortColumn>('last_updated');
const sortDirection = ref<SortDirection>('desc');
const expandedSeries = ref(new Set<string>());
const currentPage = ref(1);
const totalPages = computed(() => Math.max(1, Math.ceil(seriesStore.total / PAGE_SIZE)));
const rangeStart = computed(() => (currentPage.value - 1) * PAGE_SIZE + 1);
const rangeEnd = computed(() => Math.min(currentPage.value * PAGE_SIZE, seriesStore.total));
const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
});

const formatDate = (timestamp: string | null) => {
  if (!timestamp) return '—';
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? '—' : dateFormatter.format(date);
};

const fetch = (page: number) => {
  if (seriesStore.isLoading) return;
  currentPage.value = page;
  void seriesStore.fetchSeries({
    title: appliedTitle.value,
    quarantined: appliedQuarantine.value === 'all' ? undefined : appliedQuarantine.value === 'yes',
    mangaupdatesStatus: appliedMangaUpdatesStatus.value === 'all'
      ? undefined
      : appliedMangaUpdatesStatus.value,
    sortBy: sortBy.value,
    sortDirection: sortDirection.value,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  });
};

const applyFilters = () => {
  if (seriesStore.isLoading) return;
  appliedTitle.value = titleFilter.value.trim();
  appliedQuarantine.value = quarantineFilter.value;
  appliedMangaUpdatesStatus.value = mangaUpdatesStatusFilter.value;
  expandedSeries.value.clear();
  fetch(1);
};

const changeSort = (column: SortColumn) => {
  if (seriesStore.isLoading) return;
  sortDirection.value = sortBy.value === column
    ? (sortDirection.value === 'asc' ? 'desc' : 'asc')
    : (column === 'last_updated' ? 'desc' : 'asc');
  sortBy.value = column;
  fetch(1);
};

const ariaSort = (column: SortColumn) => sortBy.value !== column
  ? 'none' : sortDirection.value === 'asc' ? 'ascending' : 'descending';
const sortIndicator = (column: SortColumn) => sortBy.value !== column
  ? '↕' : sortDirection.value === 'asc' ? '↑' : '↓';

const updateStatusLabel = (status: string) => {
  switch (status) {
    case 'up_to_date': return 'Up to date';
    case 'missing_chapters': return 'Missing chapters';
    case 'unknown': return 'Unknown';
    default: return '';
  }
};

const toggleDetails = (series: string, id: number) => {
  if (expandedSeries.value.has(series)) {
    expandedSeries.value.delete(series);
  } else {
    expandedSeries.value.add(series);
    void seriesStore.fetchQuarantineDetails(id);
  }
};

const detailsMessage = (status?: string) => {
  switch (status) {
    case 'no_gaps': return 'No current gaps detected. This series remains quarantined; it may have been quarantined manually or the original gap may now be resolved.';
    case 'no_active_chapters': return 'Unable to determine the reason: no active chapters are available for this series.';
    case 'tracker_unavailable': return 'Unable to determine the reason: tracker progress is unavailable.';
    case 'not_quarantined': return 'This series is no longer quarantined. Refresh the list to update its status.';
    default: return '';
  }
};

onMounted(() => fetch(1));
</script>

<template>
  <main class="series-page" :aria-busy="seriesStore.isLoading">
    <header class="page-header">
      <h1>Series</h1>
      <p class="page-subtitle">Last updated includes inactive chapters; latest available chapter includes active chapters only.</p>
    </header>

    <form class="filter-bar" aria-label="Filter series" @submit.prevent="applyFilters">
      <label class="filter-field">
        <span class="field-label">Series</span>
        <input v-model="titleFilter" type="search" placeholder="Search by series name" aria-label="Search by series name" />
      </label>
      <label class="filter-field filter-field--status">
        <span class="field-label">Quarantined</span>
        <select v-model="quarantineFilter" aria-label="Filter by quarantine status">
          <option value="all">All series</option>
          <option value="yes">Quarantined</option>
          <option value="no">Not quarantined</option>
        </select>
      </label>
      <label class="filter-field filter-field--status">
        <span class="field-label">MangaUpdates status</span>
        <select v-model="mangaUpdatesStatusFilter" aria-label="Filter by MangaUpdates status">
          <option value="all">All statuses</option>
          <option value="up_to_date">Up to date</option>
          <option value="missing_chapters">Missing chapters</option>
          <option value="unavailable">Unavailable</option>
          <option value="unknown">Unknown</option>
        </select>
      </label>
      <button type="submit" :disabled="seriesStore.isLoading">Search</button>
    </form>

    <p v-if="seriesStore.isLoading" class="state-message" role="status">Loading series…</p>
    <div v-else-if="seriesStore.error" class="error-state">
      <p class="state-message state-message--error" role="alert">{{ seriesStore.error }}</p>
      <button class="ghost" @click="fetch(currentPage)">Retry</button>
    </div>
    <template v-else>
      <p class="meta-count" aria-live="polite" aria-atomic="true">
        <template v-if="seriesStore.total > 0">
          {{ rangeStart }}–{{ rangeEnd }} of {{ seriesStore.total.toLocaleString() }} series
        </template>
        <template v-else>No series found.</template>
      </p>

      <p v-if="seriesStore.series.length > 0" class="updates-note">
        MangaUpdates chapters are cached; refresh them using the MangaUpdates check on the Tasks page.
        Up to date means stored chapters or AniList last read have reached the cached chapter, not that there are no gaps.
      </p>

      <div v-if="seriesStore.series.length > 0" class="table-wrapper">
        <table aria-label="Series">
          <thead>
            <tr>
              <th scope="col" :aria-sort="ariaSort('series')">
                <button class="sort-button" :disabled="seriesStore.isLoading" @click="changeSort('series')">Series <span aria-hidden="true">{{ sortIndicator('series') }}</span></button>
              </th>
              <th scope="col" class="col-date" :aria-sort="ariaSort('last_updated')">
                <button class="sort-button" :disabled="seriesStore.isLoading" @click="changeSort('last_updated')">Last updated <span aria-hidden="true">{{ sortIndicator('last_updated') }}</span></button>
              </th>
              <th scope="col" class="col-latest-chapter">Latest available chapter</th>
              <th scope="col" class="col-updates">MangaUpdates</th>
              <th scope="col" class="col-status" :aria-sort="ariaSort('quarantined')">
                <button class="sort-button" :disabled="seriesStore.isLoading" @click="changeSort('quarantined')">Quarantined <span aria-hidden="true">{{ sortIndicator('quarantined') }}</span></button>
              </th>
            </tr>
          </thead>
          <tbody>
            <template v-for="(series, index) in seriesStore.series" :key="series.series">
              <tr>
                <td class="col-series">{{ series.series }}</td>
                <td class="col-date">
                  <time v-if="series.last_updated" :datetime="series.last_updated">
                    {{ formatDate(series.last_updated) }}
                  </time>
                  <span v-else>—</span>
                </td>
                <td class="col-latest-chapter">
                  <span v-if="series.latest_stored_chapter !== null" class="chapter-number">
                    {{ series.latest_stored_chapter }}
                  </span>
                  <span v-else>—</span>
                </td>
                <td class="col-updates">
                  <template v-if="series.mangaupdates_latest_chapter !== null">
                    <span class="chapter-number">{{ series.mangaupdates_latest_chapter }}</span>
                    <span class="update-status" :class="`update-status--${series.mangaupdates_status}`">
                      {{ updateStatusLabel(series.mangaupdates_status) }}
                    </span>
                  </template>
                  <span v-else>N/A</span>
                  <span v-if="series.mangaupdates_status_reason" class="update-reason">
                    {{ series.mangaupdates_status_reason }}
                  </span>
                </td>
                <td class="col-status">
                  <button v-if="series.quarantined && series.anilistId !== null" class="details-toggle ghost"
                    :aria-expanded="expandedSeries.has(series.series)"
                    :aria-controls="`quarantine-details-${index}`"
                    :aria-label="`${expandedSeries.has(series.series) ? 'Hide' : 'Show'} quarantine reasons for ${series.series}`"
                    @click="toggleDetails(series.series, series.anilistId)">
                    <span aria-hidden="true">{{ expandedSeries.has(series.series) ? '▾' : '▸' }}</span> Yes
                  </button>
                  <span v-else>{{ series.quarantined ? 'Yes' : 'No' }}</span>
                </td>
              </tr>
              <tr v-if="expandedSeries.has(series.series) && series.anilistId !== null" class="details-row">
                <td :id="`quarantine-details-${index}`" colspan="5">
                  <section :aria-label="`Quarantine reasons for ${series.series}`" :aria-busy="seriesStore.quarantineDetails[series.anilistId]?.loading">
                    <h2 class="details-heading">Quarantine reasons</h2>
                    <p class="details-note">Current gap check; viewing this does not change quarantine status.</p>
                    <p v-if="seriesStore.quarantineDetails[series.anilistId]?.loading" role="status">Checking chapter gaps…</p>
                    <template v-else-if="seriesStore.quarantineDetails[series.anilistId]?.error">
                      <p role="alert">{{ seriesStore.quarantineDetails[series.anilistId]?.error }}</p>
                      <button class="ghost" @click="seriesStore.fetchQuarantineDetails(series.anilistId)">Retry</button>
                    </template>
                    <template v-else>
                      <ul v-if="seriesStore.quarantineDetails[series.anilistId]?.data?.reasons.length" class="reasons-list">
                        <li v-for="(reason, reasonIndex) in seriesStore.quarantineDetails[series.anilistId]?.data?.reasons" :key="reasonIndex">
                          <template v-if="reason.type === 'tracker_gap'">Last read chapter {{ reason.last_read }}; first stored chapter is {{ reason.first_stored }}.</template>
                          <template v-else>Gap between stored chapters {{ reason.before }} and {{ reason.after }}.</template>
                        </li>
                      </ul>
                      <p v-else>{{ detailsMessage(seriesStore.quarantineDetails[series.anilistId]?.data?.status) }}</p>
                    </template>
                  </section>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <nav v-if="totalPages > 1" class="pagination" aria-label="Series page navigation">
        <button class="ghost" :disabled="currentPage === 1" @click="fetch(currentPage - 1)">← Prev</button>
        <span class="pagination__info">{{ currentPage }} / {{ totalPages }}</span>
        <button class="ghost" :disabled="currentPage === totalPages" @click="fetch(currentPage + 1)">Next →</button>
      </nav>
    </template>
  </main>
</template>

<style scoped>
/* Hallmark · pre-emit critique: P4 H4 E4 S5 R5 V3
 * Existing app style preserved; browse-only series table.
 */
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

.filter-bar {
  display: flex;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}

.filter-field {
  display: flex;
  flex: 1 1 220px;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-1);
}

.filter-field input { width: 100%; }
.filter-field--status { flex: 0 1 200px; }
.filter-field select { width: 100%; }
.filter-field input:hover { border-color: var(--color-ink-3); }
.filter-field input:focus-visible {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 2px var(--color-focus);
}

.field-label,
th {
  font-family: var(--font-display);
  font-size: var(--text-xs);
  font-weight: var(--weight-medium);
  color: var(--color-ink-2);
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.meta-count,
.pagination__info {
  font-family: var(--font-display);
  font-size: var(--text-xs);
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.04em;
}

.meta-count { margin-bottom: var(--space-3); }
.updates-note { margin-bottom: var(--space-3); color: var(--color-ink-2); font-size: var(--text-xs); max-width: none; }

.state-message {
  font-size: var(--text-sm);
  color: var(--color-ink-2);
  padding: var(--space-4) 0;
}

.state-message--error { color: var(--color-error); }

.table-wrapper {
  overflow-x: auto;
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-md);
}

table {
  width: 100%;
  min-width: 720px;
  table-layout: fixed;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

thead tr {
  background: var(--color-paper-2);
  border-bottom: 1.5px solid var(--color-rule-strong);
}

th,
td {
  padding: var(--space-3) var(--space-4);
  text-align: left;
  overflow-wrap: anywhere;
}

td {
  border-bottom: 1px solid var(--color-rule);
  color: var(--color-ink);
  vertical-align: top;
}

tbody tr:last-child td { border-bottom: none; }
tbody tr:hover { background: var(--color-paper-3); }

.col-date {
  width: 20%;
  font-family: var(--font-display);
  font-size: var(--text-xs);
  color: var(--color-ink-2);
  font-variant-numeric: tabular-nums;
}

.col-latest-chapter { width: 13%; }
.col-status { width: 17%; }
.col-updates { width: 24%; }
.chapter-number { font-family: var(--font-display); font-variant-numeric: tabular-nums; }
.update-status { display: block; margin-top: var(--space-1); font-size: var(--text-xs); color: var(--color-ink-2); }
.update-status--up_to_date { color: var(--color-success); }
.update-status--missing_chapters { color: var(--color-warning); }
.update-reason { display: block; margin-top: var(--space-1); font-size: var(--text-xs); color: var(--color-ink-2); }
.sort-button {
  background: transparent;
  border: none;
  padding: 0;
  color: inherit;
  font: inherit;
  letter-spacing: inherit;
  text-transform: inherit;
  white-space: normal;
  text-align: left;
  box-shadow: none;
}
.sort-button:hover { color: var(--color-accent); background: transparent; }
.details-toggle { padding: var(--space-1) var(--space-2); }
.details-row, .details-row:hover { background: var(--color-paper-2); }
.details-heading { font-size: var(--text-sm); margin-bottom: var(--space-1); }
.details-note { color: var(--color-ink-2); margin-bottom: var(--space-3); font-size: var(--text-xs); }
.reasons-list { margin: 0; padding-left: var(--space-5); list-style: disc; }
.reasons-list li + li { margin-top: var(--space-1); }

.pagination {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-top: var(--space-5);
}

.pagination__info { text-align: center; }
button { white-space: nowrap; }

@media (max-width: 640px) {
  .filter-bar { align-items: stretch; flex-direction: column; }
  .filter-field { flex-basis: auto; }
  .filter-field--status { flex: auto; }
  .sort-button { font-size: 10px; letter-spacing: 0.02em; overflow-wrap: normal; }
  .details-toggle { min-height: 44px; }
  .filter-bar button { align-self: flex-start; }
  th, td { padding: var(--space-3) var(--space-2); }
}
</style>
