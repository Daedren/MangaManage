<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { gapDownloadKey, useSeriesStore } from '../stores/series';
import QuarantineGapAction from '../components/QuarantineGapAction.vue';
import SeriesMigrationDialog from '../components/SeriesMigrationDialog.vue';
import type { MangaUpdatesStatus, Series, SortColumn, SortDirection } from '../stores/series';

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
const migration = ref<{ anilistId: number; originalMangaId: number; series: string } | null>(null);
const refreshingMangaUpdates = ref(new Set<number>());
const mangaUpdatesRefreshErrors = ref<Record<number, string>>({});
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

const refreshMangaUpdates = async (seriesId: number) => {
  if (refreshingMangaUpdates.value.has(seriesId)) return;
  refreshingMangaUpdates.value = new Set(refreshingMangaUpdates.value).add(seriesId);
  const errors = { ...mangaUpdatesRefreshErrors.value };
  delete errors[seriesId];
  mangaUpdatesRefreshErrors.value = errors;

  try {
    await seriesStore.refreshMangaUpdatesChapter(seriesId);
    await seriesStore.fetchSeries({
      title: appliedTitle.value,
      quarantined: appliedQuarantine.value === 'all' ? undefined : appliedQuarantine.value === 'yes',
      mangaupdatesStatus: appliedMangaUpdatesStatus.value === 'all'
        ? undefined
        : appliedMangaUpdatesStatus.value,
      sortBy: sortBy.value,
      sortDirection: sortDirection.value,
      limit: PAGE_SIZE,
      offset: (currentPage.value - 1) * PAGE_SIZE,
    });
  } catch {
    mangaUpdatesRefreshErrors.value = {
      ...mangaUpdatesRefreshErrors.value,
      [seriesId]: 'Unable to refresh this MangaUpdates chapter. Try again.',
    };
  } finally {
    const refreshing = new Set(refreshingMangaUpdates.value);
    refreshing.delete(seriesId);
    refreshingMangaUpdates.value = refreshing;
  }
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
    case 'unavailable': return 'Unavailable';
    case 'unknown': return 'Unknown';
    default: return '';
  }
};

const seriesKey = (series: Series) => series.anilistId !== null
  ? `anilist-${series.anilistId}` : `name-${series.series}`;

const toggleDetails = (series: Series) => {
  const key = seriesKey(series);
  if (expandedSeries.value.has(key)) {
    expandedSeries.value.delete(key);
  } else {
    expandedSeries.value.add(key);
    if (series.quarantined && series.anilistId !== null) void seriesStore.fetchQuarantineDetails(series.anilistId);
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
        MangaUpdates chapters are cached; expand a series detail row to refresh its chapter, or use the MangaUpdates check on the Tasks page to refresh them all.
        Up to date means stored chapters or AniList last read have reached the cached chapter, not that there are no gaps.
      </p>

      <div v-if="seriesStore.series.length > 0" class="table-wrapper">
        <table aria-label="Series">
          <thead>
            <tr>
              <th scope="col" :aria-sort="ariaSort('series')">
                <button class="sort-button" :disabled="seriesStore.isLoading" @click="changeSort('series')">Series <span aria-hidden="true">{{ sortIndicator('series') }}</span></button>
              </th>
              <th scope="col" class="col-source">Suwayomi source</th>
              <th scope="col" class="col-date" :aria-sort="ariaSort('last_updated')">
                <button class="sort-button" :disabled="seriesStore.isLoading" @click="changeSort('last_updated')">Last updated <span aria-hidden="true">{{ sortIndicator('last_updated') }}</span></button>
              </th>
              <th scope="col" class="col-latest-chapter">Latest available chapter</th>
              <th scope="col" class="col-anilist-progress">AniList last read</th>
              <th scope="col" class="col-updates">MangaUpdates</th>
              <th scope="col" class="col-status" :aria-sort="ariaSort('quarantined')">
                <button class="sort-button" :disabled="seriesStore.isLoading" @click="changeSort('quarantined')">Quarantined <span aria-hidden="true">{{ sortIndicator('quarantined') }}</span></button>
              </th>
            </tr>
          </thead>
          <tbody>
            <template v-for="series in seriesStore.series" :key="seriesKey(series)">
              <tr>
                <td class="col-series">
                  <button class="series-details-toggle" :aria-expanded="expandedSeries.has(seriesKey(series))"
                    :aria-controls="`series-details-${seriesKey(series)}`"
                    :aria-label="`${expandedSeries.has(seriesKey(series)) ? 'Hide' : 'Show'} series details for ${series.series}`"
                    @click="toggleDetails(series)">
                    <span aria-hidden="true">{{ expandedSeries.has(seriesKey(series)) ? '▾' : '▸' }}</span>
                    <span>{{ series.series }}</span>
                  </button>
                </td>
                <td class="col-source">
                  <ul v-if="series.suwayomi_sources.length" class="source-links">
                    <li v-for="source in series.suwayomi_sources" :key="source.manga_id">
                      <a :href="source.url" target="_blank" rel="noopener noreferrer"
                        :aria-label="`Open ${series.series} on Suwayomi (${source.name})`"
                        :title="series.suwayomi_status_reason || undefined">{{ source.name }}</a>
                    </li>
                  </ul>
                  <span v-else :title="series.suwayomi_status_reason || undefined"
                    :aria-label="series.suwayomi_status_reason || 'No Suwayomi source'">—</span>
                  <span v-if="series.suwayomi_sources.length && series.suwayomi_status_reason" class="update-reason">
                    {{ series.suwayomi_status_reason }}
                  </span>
                </td>
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
                <td class="col-anilist-progress">
                  <a
                    v-if="series.anilistId !== null && series.anilist_last_read !== null"
                    class="chapter-number anilist-progress-link"
                    :href="`https://anilist.co/manga/${series.anilistId}`"
                    target="_blank"
                    rel="noopener noreferrer"
                    :aria-label="`AniList last read chapter ${series.anilist_last_read} for ${series.series}`"
                  >{{ series.anilist_last_read }}</a>
                  <span v-else>—</span>
                </td>
                <td class="col-updates">
                  <template v-if="series.mangaupdates_latest_chapter !== null">
                    <a v-if="series.mangaupdates_url" class="chapter-number mangaupdates-link"
                      :href="series.mangaupdates_url" target="_blank" rel="noopener noreferrer"
                      :aria-label="`Open ${series.series} on MangaUpdates`">
                      {{ series.mangaupdates_latest_chapter }}
                    </a>
                    <span v-else class="chapter-number">{{ series.mangaupdates_latest_chapter }}</span>
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
                  <span>{{ series.quarantined ? 'Yes' : 'No' }}</span>
                </td>
              </tr>
              <tr v-if="expandedSeries.has(seriesKey(series))" class="details-row">
                <td :id="`series-details-${seriesKey(series)}`" colspan="7">
                  <section class="series-detail-content" :aria-label="`Series details for ${series.series}`">
                    <h2 class="details-heading">Series details</h2>
                    <section class="details-section" aria-label="Suwayomi sources and migration">
                      <h3 class="details-heading">Suwayomi sources</h3>
                      <p class="details-note">Migrate an entry to another installed source in Suwayomi. Existing downloads and local archives are kept; quarantine status is unchanged.</p>
                      <ul v-if="series.suwayomi_sources.length" class="detail-sources">
                        <li v-for="source in series.suwayomi_sources" :key="source.manga_id">
                          <a :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.name }}</a>
                          <button v-if="series.anilistId !== null" type="button" class="ghost"
                            :aria-label="`Migrate ${series.series} from ${source.name}`"
                            @click="migration = { anilistId: series.anilistId, originalMangaId: source.manga_id, series: series.series }">Migrate source</button>
                        </li>
                      </ul>
                      <p v-if="series.suwayomi_status_reason || !series.suwayomi_sources.length" class="details-note">{{ series.suwayomi_status_reason || 'No linked Suwayomi sources. Configure Suwayomi and link this manga to AniList in its library first.' }}</p>
                    </section>
                    <section class="details-section" :aria-label="`MangaUpdates details for ${series.series}`">
                      <h3 class="details-heading">MangaUpdates</h3>
                      <p class="details-note">
                        Latest chapter: {{ series.mangaupdates_latest_chapter ?? 'Not cached' }}
                        <template v-if="series.mangaupdates_status"> · {{ updateStatusLabel(series.mangaupdates_status) }}</template>
                      </p>
                      <button v-if="series.mangaupdates_id !== null" type="button" class="ghost"
                        :disabled="refreshingMangaUpdates.has(series.mangaupdates_id)"
                        :aria-label="`Refresh MangaUpdates chapter for ${series.series}`"
                        @click="refreshMangaUpdates(series.mangaupdates_id)">
                        {{ refreshingMangaUpdates.has(series.mangaupdates_id) ? 'Refreshing…' : 'Refresh chapter' }}
                      </button>
                      <p v-else class="details-note">No MangaUpdates ID linked to this series.</p>
                      <p v-if="series.mangaupdates_id !== null && mangaUpdatesRefreshErrors[series.mangaupdates_id]" class="update-reason" role="alert">
                        {{ mangaUpdatesRefreshErrors[series.mangaupdates_id] }}
                      </p>
                    </section>
                    <section v-if="series.quarantined && series.anilistId !== null" class="details-section"
                      :aria-label="`Quarantine reasons for ${series.series}`" :aria-busy="seriesStore.quarantineDetails[series.anilistId]?.loading">
                      <h3 class="details-heading">Quarantine reasons</h3>
                      <p class="details-note">Current gap check; viewing this does not change quarantine status. Downloads are queued in Suwayomi, one copy per chapter across linked sources. Quarantine remains until chapters are imported and gaps are checked again.</p>
                      <p v-if="seriesStore.quarantineDetails[series.anilistId]?.loading" role="status">Checking chapter gaps…</p>
                      <template v-else-if="seriesStore.quarantineDetails[series.anilistId]?.error">
                        <p role="alert">{{ seriesStore.quarantineDetails[series.anilistId]?.error }}</p>
                        <button class="ghost" @click="seriesStore.fetchQuarantineDetails(series.anilistId)">Retry</button>
                      </template>
                      <template v-else>
                        <ul v-if="seriesStore.quarantineDetails[series.anilistId]?.data?.reasons.length" class="reasons-list">
                          <li v-for="reason in seriesStore.quarantineDetails[series.anilistId]?.data?.reasons" :key="gapDownloadKey(series.anilistId, reason)">
                            <QuarantineGapAction :anilist-id="series.anilistId" :series="series.series" :reason="reason" />
                          </li>
                        </ul>
                        <p v-else>{{ detailsMessage(seriesStore.quarantineDetails[series.anilistId]?.data?.status) }}</p>
                      </template>
                    </section>
                    <p v-else class="details-note">{{ series.quarantined ? 'No AniList ID assigned; quarantine reasons cannot be checked.' : 'This series is not quarantined.' }}</p>
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
    <SeriesMigrationDialog v-if="migration" :anilist-id="migration.anilistId"
      :original-manga-id="migration.originalMangaId" :series="migration.series"
      @close="migration = null" @changed="fetch(currentPage)" />
  </main>
</template>

<style scoped>
/* Hallmark · pre-emit critique: P4 H4 E4 S5 R5 V3
 * Existing app style preserved; general series details with explicit actions.
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
  min-width: 1000px;
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
  width: 17%;
  font-family: var(--font-display);
  font-size: var(--text-xs);
  color: var(--color-ink-2);
  font-variant-numeric: tabular-nums;
}

.col-source { width: 14%; }
.source-links { margin: 0; padding: 0; list-style: none; }
.source-links li + li { margin-top: var(--space-2); }
.source-links a { text-underline-offset: 2px; }
.source-links a:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
.col-latest-chapter { width: 10%; }
.col-anilist-progress { width: 10%; }
.col-status { width: 12%; }
.col-updates { width: 20%; }
.chapter-number { font-family: var(--font-display); font-variant-numeric: tabular-nums; }
.anilist-progress-link { color: inherit; text-decoration: none; }
.anilist-progress-link:hover { color: var(--color-accent); text-decoration: underline; text-underline-offset: 2px; }
.anilist-progress-link:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
.mangaupdates-link { color: inherit; text-decoration: none; }
.mangaupdates-link:hover { color: var(--color-accent); text-decoration: underline; text-underline-offset: 2px; }
.mangaupdates-link:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
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
.series-details-toggle { display: flex; align-items: flex-start; gap: var(--space-1); padding: 0; background: transparent; border: 0; color: inherit; font: inherit; text-align: left; white-space: normal; }
.series-details-toggle span:last-child { min-width: 0; overflow-wrap: anywhere; }
.series-details-toggle:hover { background: transparent; color: var(--color-accent); }
.series-details-toggle:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
.details-row, .details-row:hover { background: var(--color-paper-2); }
.series-detail-content { max-width: min(100%, calc(100vw - var(--space-16))); }
.details-heading { font-size: var(--text-sm); margin-bottom: var(--space-1); }
.details-note { color: var(--color-ink-2); margin-bottom: var(--space-3); font-size: var(--text-xs); }
.details-section { margin-top: var(--space-4); }
.detail-sources { list-style: none; margin: 0; padding: 0; }
.detail-sources li { display: flex; align-items: center; gap: var(--space-4); flex-wrap: wrap; margin-bottom: var(--space-2); }
.detail-sources button { padding: var(--space-1) var(--space-2); }
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
  .series-details-toggle, .detail-sources button { min-height: 44px; }
  .filter-bar button { align-self: flex-start; }
  th, td { padding: var(--space-3) var(--space-2); }
}
</style>
