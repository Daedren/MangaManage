import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import config from '@/config';

type TaskResponse = {
    message: string;
    [key: string]: unknown;
};

export const useTasksStore = defineStore('tasks', () => {
    const isRunning = ref(false);
    const activeTask = ref('');
    const lastMessage = ref('');
    const error = ref('');

    const runTask = async (label: string, request: () => Promise<{ data: TaskResponse }>) => {
        isRunning.value = true;
        activeTask.value = label;
        lastMessage.value = '';
        error.value = '';

        try {
            const response = await request();
            lastMessage.value = response.data.message || `${label} completed.`;
            return response.data;
        } catch (caughtError) {
            console.error(`Error running ${label}:`, caughtError);
            error.value = `Unable to run ${label}.`;
            throw caughtError;
        } finally {
            isRunning.value = false;
            activeTask.value = '';
        }
    };

    const processSource = () =>
        runTask('Process source', () => axios.post(`${config.apiBaseUrl}/tasks/process-source`));

    const checkMissingSql = (fix: boolean) =>
        runTask(fix ? 'Fix missing SQL' : 'Check missing SQL', () =>
            axios.post(`${config.apiBaseUrl}/tasks/check-missing-sql`, null, { params: { fix } })
        );

    const checkMissingChapters = () =>
        runTask('Check missing chapters', () =>
            axios.post(`${config.apiBaseUrl}/tasks/check-missing-chapters`)
        );

    const checkMangaUpdates = () =>
        runTask('Check MangaUpdates', () =>
            axios.post(`${config.apiBaseUrl}/tasks/check-manga-updates`)
        );

    const updateAnilistId = (series: string, anilistId: string) =>
        runTask('Update AniList ID', () =>
            axios.post(`${config.apiBaseUrl}/tasks/update-anilist-id`, { series, anilistId })
        );

    return {
        isRunning,
        activeTask,
        lastMessage,
        error,
        processSource,
        checkMissingSql,
        checkMissingChapters,
        checkMangaUpdates,
        updateAnilistId,
    };
});
