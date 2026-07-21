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
const rangeEnd = computed(() => Math.min(currentPage.value * PAGE_SIZE, chaptersStore.total));

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
    <section class="chapters-header">
      <div>
        <h1>Chapters</h1>
        <p>Browse archived chapters in the database.</p>
      </div>
    </section>

    <section class="filters">
      <label>
        Active
        <select v-model="activeFilter" @change="applyFilters">
          <option :value="1">Active (1)</option>
          <option :value="0">Inactive (0)</option>
        </select>
      </label>
      <label>
        Title
        <input
          v-model="titleFilter"
          type="text"
          placeholder="Search by series name"
          @keydown="handleTitleKeydown"
        />
      </label>
      <button @click="applyFilters">Search</button>
    </section>

    <div class="meta-row">
      <p class="count" v-if="chaptersStore.total > 0">
        Showing {{ rangeStart }}–{{ rangeEnd }} of {{ chaptersStore.total }} chapter{{ chaptersStore.total !== 1 ? 's' : '' }}
      </p>
      <p class="empty" v-else>No chapters found.</p>
    </div>

    <div class="table-wrapper" v-if="chaptersStore.chapters.length > 0">
      <table>
        <thead>
          <tr>
            <th>Series</th>
            <th>Chapter</th>
            <th>Date Added</th>
            <th>AniList ID</th>
            <th>Active</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="chapter in chaptersStore.chapters" :key="chapter.id">
            <td>{{ chapter.series_name }}</td>
            <td class="num">{{ chapter.chapter_number }}</td>
            <td class="date">{{ chapter.creation_date ?? '—' }}</td>
            <td class="num">{{ chapter.anilistId ?? '—' }}</td>
            <td class="num">{{ chapter.active }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <nav class="pagination" v-if="totalPages > 1">
      <button :disabled="currentPage === 1" @click="fetch(currentPage - 1)">← Prev</button>
      <span class="page-info">Page {{ currentPage }} of {{ totalPages }}</span>
      <button :disabled="currentPage === totalPages" @click="fetch(currentPage + 1)">Next →</button>
    </nav>
  </main>
</template>

<style scoped>
.chapters-page {
  width: min(1100px, 100%);
  margin: 0 auto;
}

.chapters-header {
  margin-bottom: 1rem;
}

.chapters-header p {
  margin: 0.25rem 0 0;
  color: #5f6f5f;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 1rem;
  margin-bottom: 1rem;
}

.filters label {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-weight: 700;
  font-size: 0.9rem;
}

select,
input[type='text'] {
  padding: 0.5rem;
  border: 1px solid #adc0aa;
  border-radius: 4px;
  font-size: 0.95rem;
}

input[type='text'] {
  min-width: 220px;
}

button {
  padding: 0.55rem 0.9rem;
  background-color: #315c3a;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 700;
  align-self: flex-end;
}

button:hover:not(:disabled) {
  background-color: #264a2e;
}

button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.meta-row {
  margin-bottom: 0.5rem;
}

.count {
  font-size: 0.85rem;
  color: #5f6f5f;
  margin: 0;
}

.empty {
  color: #5f6f5f;
  margin: 0;
}

.table-wrapper {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

thead tr {
  background: #edf4eb;
}

th {
  text-align: left;
  padding: 0.6rem 0.75rem;
  font-weight: 700;
  border-bottom: 2px solid #c9d5c7;
  white-space: nowrap;
}

td {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid #e2ebe0;
}

td.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

td.date {
  white-space: nowrap;
  color: #4f5d4f;
}

tbody tr:hover {
  background: #f4f9f3;
}

.pagination {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 1rem;
}

.page-info {
  font-size: 0.9rem;
  color: #4f5d4f;
}
</style>
