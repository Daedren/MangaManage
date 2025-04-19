<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { useChaptersStore } from '../stores/chapters';

const chaptersStore = useChaptersStore();
const sortKey = ref<keyof typeof chaptersStore.chapters[0]>('id'); // The current column to sort by
const sortOrder = ref(1); // 1 for ascending, -1 for descending
const selectedChapters = ref<number[]>([]); // Array to store selected chapter IDs

// Computed property to sort chapters
const sortedChapters = computed(() => {
  if (!sortKey.value) return chaptersStore.chapters;

  return [...chaptersStore.chapters].sort((a, b) => {
    const valA = a[sortKey.value] ?? ''; // Default to empty string for null/undefined
    const valB = b[sortKey.value] ?? '';
    return valA > valB ? sortOrder.value : valA < valB ? -sortOrder.value : 0;
  });
});

// Function to set the sort key and toggle sort order
const sortBy = (key: string) => {
  if (sortKey.value === key) {
    sortOrder.value *= -1; // Toggle sort order
  } else {
    sortKey.value = key;
    sortOrder.value = 1; // Default to ascending
  }
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
        <tr v-for="chapter in sortedChapters" :key="chapter.id">
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
  cursor: pointer; /* Add pointer cursor for clickable headers */
}

.chapter-table th,
.chapter-table td {
  border: 1px solid #bbb;
  padding: 0.5rem;
  text-align: left;
}

.chapter-table th {
  background-color: #586655;
  font-weight: bold;
  color: white;
}

.chapter-table th:hover {
  background-color: #45834f; /* Highlight header on hover */
}

.chapter-table tr:nth-child(even) {
  background-color: #39463f;
}

.chapter-table tr:hover {
  background-color: #45834f;
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
</style>
