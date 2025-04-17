import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import config from '@/config'; // Import the config file

// Define the type for a chapter
interface Chapter {
    id: number;
    series_name: string;
    chapter_number: number;
    creation_date?: string;
    anilistId?: number;
}

export const useChaptersStore = defineStore('chapters', () => {
    const chapters = ref<Chapter[]>([]); // Use the Chapter type here

    // Fetch all chapters from the API
    const fetchChapters = async () => {
        try {
            const response = await axios.get(`${config.apiBaseUrl}/database/chapters`);
            // Map Python-style keys to Vue-style keys
            chapters.value = response.data.chapters.map((chapter: any) => ({
                id: chapter.id,
                series_name: chapter.series, // Map 'series' to 'series_name'
                chapter_number: chapter.chapter, // Map 'chapter' to 'chapter_number'
                creation_date: chapter.creation_date, // Keep as-is if needed
                anilistId: chapter.anilistId, // Keep as-is if needed
            }));
        } catch (error) {
            console.error('Error fetching chapters:', error);
        }
    };

    // Delete selected chapters by their IDs
    const deleteChapters = async (chapterIds: number[]) => {
        try {
            // Send DELETE requests for each chapter ID
            await Promise.all(
                chapterIds.map((id) =>
                    axios.delete(`${config.apiBaseUrl}/database/chapter`, {
                        params: { database_id: id },
                    })
                )
            );

            // Remove deleted chapters from the state
            chapters.value = chapters.value.filter((chapter) => !chapterIds.includes(chapter.id));
        } catch (error) {
            console.error('Error deleting chapters:', error);
        }
    };

    return { chapters, fetchChapters, deleteChapters };
});