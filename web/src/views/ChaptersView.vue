<script setup lang="ts">
import { onMounted, ref, computed, watch } from 'vue';
import { useChaptersStore } from '../stores/chapters';

const chaptersStore = useChaptersStore();
const sortKey = ref<keyof typeof chaptersStore.chapters[0]>('id'); // The current column to sort by
const sortOrder = ref(1); // 1 for ascending, -1 for descending
const selectedChapters = ref<number[]>([]); // Array to store selected chapter IDs
const currentPage = ref(1);
const pageSize = ref(50);

// Computed property to sort chapters
const sortedChapters = computed(() => {
  if (!sortKey.value) return chaptersStore.chapters;

  return [...chaptersStore.chapters].sort((a, b) => {
    const valA = a[sortKey.value] ?? ''; // Default to empty string for null/undefined
    const valB = b[sortKey.value] ?? '';
    return valA > valB ? sortOrder.value : valA < valB ? -sortOrder.value : 0;
  });
});

const totalPages = computed(() => Math.max(1, Math.ceil(sortedChapters.value.length / pageSize.value)));
const pageStart = computed(() => (currentPage.value - 1) * pageSize.value);
const pageEnd = computed(() => Math.min(pageStart.value + pageSize.value, sortedChapters.value.length));
const paginatedChapters = computed(() => sortedChapters.value.slice(pageStart.value, pageEnd.value));

watch([totalPages, pageSize], () => {
  currentPage.value = Math.min(currentPage.value, totalPages.value);
});

const previousPage = () => {
  currentPage.value = Math.max(1, currentPage.value - 1);
};

const nextPage = () => {
  currentPage.value = Math.min(totalPages.value, currentPage.value + 1);
};

// Function to set the sort key and toggle sort order
const sortBy = (key: keyof typeof chaptersStore.chapters[0]) => {
  if (sortKey.value === key) {
    sortOrder.value *= -1; // Toggle sort order
  } else {
    sortKey.value = key;
    sortOrder.value = 1; // Default to ascending
  }
  currentPage.value = 1;
};

// Function to toggle selection of a chapter
const toggleSelection = (id: number) => {
  if (selectedChapters.value.includes(id)) {
    selectedChapters.value = selectedChapters.value.filter((chapterId) => chapterId !== id);
  } else {
    selectedChapters.value.push(id);
  }
};

// Function to delete selected chapters
const deleteSelectedChapters = async () => {
  await chaptersStore.deleteChapters(selectedChapters.value);
  selectedChapters.value = []; // Clear the selection
};

onMounted(() => {
  chaptersStore.fetchChapters();
});
</script>

<template>
  <main>
    <h1>Chapters</h1>
    <button @click="deleteSelectedChapters" :disabled="selectedChapters.length === 0">
      Delete Selected
    </button>
    <div class="pagination-controls">
      <span>
        Showing {{ sortedChapters.length === 0 ? 0 : pageStart + 1 }}-{{ pageEnd }} of
        {{ sortedChapters.length }} chapters
      </span>
      <label>
        Per page
        <select v-model.number="pageSize">
          <option :value="25">25</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
          <option :value="250">250</option>
        </select>
      </label>
      <button class="pagination-button" @click="previousPage" :disabled="currentPage === 1">
        Previous
      </button>
      <span>Page {{ currentPage }} of {{ totalPages }}</span>
      <button class="pagination-button" @click="nextPage" :disabled="currentPage === totalPages">
        Next
      </button>
    </div>
    <table class="chapter-table">
      <thead>
        <tr>
          <th></th>
          <th @click="sortBy('id')">ID</th>
          <th @click="sortBy('series_name')">Series Name</th>
          <th @click="sortBy('chapter_number')">Chapter Number</th>
          <th @click="sortBy('creation_date')">Creation Date</th>
          <th @click="sortBy('anilistId')">Anilist ID</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="chapter in paginatedChapters" :key="chapter.id">
          <td>
            <input
              type="checkbox"
              :value="chapter.id"
              @change="toggleSelection(chapter.id)"
              :checked="selectedChapters.includes(chapter.id)"
            />
          </td>
          <td>{{ chapter.id }}</td>
          <td>{{ chapter.series_name }}</td>
          <td>{{ chapter.chapter_number }}</td>
          <td>{{ chapter.creation_date || 'N/A' }}</td>
          <td>{{ chapter.anilistId || 'N/A' }}</td>
        </tr>
      </tbody>
    </table>
  </main>
</template>

<style scoped>
.chapter-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 1rem;
  color: #1f2933;
  cursor: pointer; /* Add pointer cursor for clickable headers */
}

.chapter-table th,
.chapter-table td {
  border: 1px solid #bbb;
  padding: 0.5rem;
  text-align: left;
}

.chapter-table th {
  background-color: #315c3a;
  font-weight: bold;
  color: white;
}

.chapter-table th:hover {
  background-color: #3f7a4a; /* Highlight header on hover */
}

.chapter-table tbody tr {
  background-color: #f7fbf6;
}

.chapter-table tr:nth-child(even) {
  background-color: #e7f1e4;
}

.chapter-table tr:hover {
  background-color: #cfe3c9;
}

button {
  margin-bottom: 1rem;
  padding: 0.5rem 1rem;
  background-color: #d9534f;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.pagination-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
  margin-top: 1rem;
}

.pagination-controls label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.pagination-controls select {
  padding: 0.35rem;
  border: 1px solid #8fa58c;
  border-radius: 4px;
}

.pagination-button {
  margin-bottom: 0;
  background-color: #315c3a;
}

.pagination-button:hover:not(:disabled) {
  background-color: #3f7a4a;
}
</style>
