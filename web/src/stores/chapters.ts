import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import config from '@/config';

interface Chapter {
    id: number;
    series_name: string;
    chapter_number: number;
    creation_date?: string;
    anilistId?: number;
    active: number;
}

interface FetchOptions {
    active?: 0 | 1;
    title?: string;
    limit?: number;
    offset?: number;
}

export const useChaptersStore = defineStore('chapters', () => {
    const chapters = ref<Chapter[]>([]);
    const total = ref(0);
    const limit = ref(50);
    const offset = ref(0);

    const fetchChapters = async (options: FetchOptions = {}) => {
        const params: Record<string, string | number> = {
            active: options.active ?? 1,
            limit: options.limit ?? limit.value,
            offset: options.offset ?? 0,
        };
        if (options.title && options.title.trim()) {
            params.title = options.title.trim();
        }
        try {
            const response = await axios.get(`${config.apiBaseUrl}/database/chapters`, { params });
            chapters.value = response.data.chapters.map((chapter: any) => ({
                id: chapter.id,
                series_name: chapter.series,
                chapter_number: chapter.chapter,
                creation_date: chapter.creation_date,
                anilistId: chapter.anilistId,
                active: chapter.active,
            }));
            total.value = response.data.total;
            limit.value = response.data.limit;
            offset.value = response.data.offset;
        } catch (error) {
            console.error('Error fetching chapters:', error);
        }
    };

    const deleteChapters = async (chapterIds: number[]) => {
        try {
            await Promise.all(
                chapterIds.map((id) =>
                    axios.delete(`${config.apiBaseUrl}/database/chapter`, {
                        params: { database_id: id },
                    })
                )
            );
            chapters.value = chapters.value.filter((chapter) => !chapterIds.includes(chapter.id));
            total.value -= chapterIds.length;
        } catch (error) {
            console.error('Error deleting chapters:', error);
        }
    };

    return { chapters, total, limit, offset, fetchChapters, deleteChapters };
});
