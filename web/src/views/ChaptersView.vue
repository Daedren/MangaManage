<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useChaptersStore } from '../stores/chapters';

const chaptersStore = useChaptersStore();

const PAGE_SIZE = 50;
const activeFilter = ref<0 | 1>(1);
const titleFilter = ref('');
const currentPage = ref(1);

const totalPages = computed(() => Math.max(1, Math.ceil(chaptersStore.total / PAGE_SIZE)));
const rangeStart = computed(() => (currentPage.value - 1) * PAGE_SIZE + 1);
const rangeEnd   = computed(() => Math.min(currentPage.value * PAGE_SIZE, chaptersStore.total));

const fetch = (page: number) => {
  currentPage.value = page;
  chaptersStore.fetchChapters({
    active: activeFilter.value,
    title: titleFilter.value,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  });
};

const applyFilters = () => fetch(1);

const handleTitleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter') applyFilters();
};

onMounted(() => fetch(1));
</script>

<template>
  <main class="chapters-page">

    <!-- Page header -->
    <header class="page-header">
      <div class="page-header__text">
        <h1>Chapters</h1>
        <p class="page-subtitle">Browse archived chapters in the database.</p>
      </div>
    </header>

    <!-- Filter bar -->
    <section class="filter-bar" aria-label="Filter chapters">
      <label class="filter-field">
        <span class="field-label">Status</span>
        <select v-model="activeFilter" @change="applyFilters" aria-label="Filter by status">
          <option :value="1">Active</option>
          <option :value="0">Inactive</option>
        </select>
      </label>

      <label class="filter-field filter-field--grow">
        <span class="field-label">Series</span>
        <input
          v-model="titleFilter"
          type="text"
          placeholder="Search by series name"
          @keydown="handleTitleKeydown"
          aria-label="Search by series name"
        />
      </label>

      <button @click="applyFilters" class="filter-bar__action">Search</button>
    </section>

    <!-- Result count -->
    <div class="meta-row" aria-live="polite" aria-atomic="true">
      <span class="meta-count" v-if="chaptersStore.total > 0">
        {{ rangeStart }}–{{ rangeEnd }}
        <span class="meta-of">of</span>
        {{ chaptersStore.total.toLocaleString() }}
        {{ chaptersStore.total !== 1 ? 'chapters' : 'chapter' }}
      </span>
      <span class="meta-empty" v-else>No chapters found.</span>
    </div>

    <!-- Data table -->
    <div class="table-wrapper" v-if="chaptersStore.chapters.length > 0">
      <table>
        <thead>
          <tr>
            <th scope="col">Series</th>
            <th scope="col" class="col-num">Chapter</th>
            <th scope="col" class="col-date">Date Added</th>
            <th scope="col" class="col-num">AniList ID</th>
            <th scope="col" class="col-num">Active</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="chapter in chaptersStore.chapters" :key="chapter.id">
            <td class="col-series">{{ chapter.series_name }}</td>
            <td class="col-num">{{ chapter.chapter_number }}</td>
            <td class="col-date">{{ chapter.creation_date ?? '—' }}</td>
            <td class="col-num">{{ chapter.anilistId ?? '—' }}</td>
            <td class="col-num">
              <span :class="['status-badge', chapter.active ? 'status-badge--on' : 'status-badge--off']">
                {{ chapter.active ? 'Y' : 'N' }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <nav class="pagination" v-if="totalPages > 1" aria-label="Page navigation">
      <button
        :disabled="currentPage === 1"
        @click="fetch(currentPage - 1)"
        aria-label="Previous page"
        class="ghost"
      >← Prev</button>

      <span class="pagination__info">{{ currentPage }} / {{ totalPages }}</span>

      <button
        :disabled="currentPage === totalPages"
        @click="fetch(currentPage + 1)"
        aria-label="Next page"
        class="ghost"
      >Next →</button>
    </nav>

  </main>
</template>

<style scoped>
.chapters-page {
  /* inherits max-width + padding from main.css */
}

/* ─── Page header ────────────────────────────────────────────────── */
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

/* ─── Filter bar ─────────────────────────────────────────────────── */
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}

.filter-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.filter-field--grow {
  flex: 1 1 220px;
}

.field-label {
  font-family: var(--font-display);
  font-size: var(--text-xs);
  font-weight: var(--weight-medium);
  color: var(--color-ink-2);
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.filter-bar select,
.filter-bar input[type='text'] {
  width: 100%;
}

.filter-bar__action {
  align-self: flex-end;
}

/* ─── Meta row ───────────────────────────────────────────────────── */
.meta-row {
  margin-bottom: var(--space-3);
}

.meta-count {
  font-family: var(--font-display);
  font-size: var(--text-xs);
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.04em;
}

.meta-of {
  opacity: 0.55;
}

.meta-empty {
  font-size: var(--text-sm);
  color: var(--color-ink-3);
}

/* ─── Table ──────────────────────────────────────────────────────── */
.table-wrapper {
  overflow-x: auto;
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-md);
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

thead tr {
  background: var(--color-paper-2);
  border-bottom: 1.5px solid var(--color-rule-strong);
}

th {
  font-family: var(--font-display);
  font-size: var(--text-xs);
  font-weight: var(--weight-medium);
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--color-ink-2);
  text-align: left;
  padding: var(--space-3) var(--space-4);
  white-space: nowrap;
}

td {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-rule);
  color: var(--color-ink);
  vertical-align: middle;
}

tbody tr:last-child td {
  border-bottom: none;
}

tbody tr:hover {
  background: var(--color-paper-3);
}

tbody tr:focus-within {
  background: var(--color-paper-3);
}

.col-num {
  text-align: right;
  font-family: var(--font-display);
  font-variant-numeric: tabular-nums;
  font-size: var(--text-xs);
  letter-spacing: 0.03em;
}

.col-date {
  white-space: nowrap;
  font-family: var(--font-display);
  font-size: var(--text-xs);
  color: var(--color-ink-2);
  letter-spacing: 0.03em;
}

.col-series {
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Active/inactive badge */
.status-badge {
  display: inline-block;
  font-family: var(--font-display);
  font-size: var(--text-xs);
  font-weight: var(--weight-medium);
  padding: 1px var(--space-2);
  border-radius: var(--radius-sm);
  letter-spacing: 0.06em;
}

.status-badge--on {
  background: var(--color-accent-muted);
  color: var(--color-accent);
}

.status-badge--off {
  background: var(--color-paper-3);
  color: var(--color-ink-3);
}

/* ─── Pagination ─────────────────────────────────────────────────── */
.pagination {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-top: var(--space-5);
}

.pagination__info {
  font-family: var(--font-display);
  font-size: var(--text-xs);
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.06em;
  min-width: 5ch;
  text-align: center;
}

/* ─── Mobile ─────────────────────────────────────────────────────── */
@media (max-width: 640px) {
  .filter-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-bar__action {
    align-self: flex-start;
  }

  th.col-date,
  td.col-date {
    display: none;
  }
}

@media (max-width: 414px) {
  th.col-num:last-child,
  td.col-num:last-child {
    display: none;
  }
}
</style>
