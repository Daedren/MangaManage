import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import config from '@/config';

type TaskResponse = { message: string; [key: string]: unknown };
type TaskRun = {
    id: string;
    label: string;
    status: 'running' | 'succeeded' | 'failed' | 'interrupted';
    result: TaskResponse | null;
    error: string | null;
};

export const useTasksStore = defineStore('tasks', () => {
    const isRunning = ref(false);
    const isRestoring = ref(false);
    const activeTask = ref('');
    const runId = ref('');
    const lastMessage = ref('');
    const error = ref('');
    const statusError = ref('');
    let timer: ReturnType<typeof setTimeout> | undefined;
    let version = 0;

    function apply(run: TaskRun) {
        runId.value = run.id;
        isRunning.value = run.status === 'running';
        activeTask.value = run.label;
        lastMessage.value = run.status === 'succeeded' ? run.result?.message || `${run.label} completed.` : '';
        error.value = run.error || '';
        statusError.value = '';
    }

    function poll(expectedVersion: number) {
        clearTimeout(timer);
        timer = setTimeout(async () => {
            if (expectedVersion !== version) return;
            try {
                const response = await axios.get<TaskRun>(`${config.apiBaseUrl}/tasks/runs/${runId.value}`, { timeout: 10000 });
                if (expectedVersion !== version) return;
                apply(response.data);
            } catch (caughtError) {
                if (expectedVersion !== version) return;
                if (axios.isAxiosError(caughtError) && caughtError.response?.status === 404) {
                    isRunning.value = false;
                    error.value = 'This run is no longer retained. Refresh the page to check the latest task.';
                } else {
                    // Losing a connection does not mean a task failed or permit a second start.
                    statusError.value = 'Task status is unavailable. Reconnecting…';
                }
            }
            if (isRunning.value) poll(expectedVersion);
        }, 1000);
    }

    async function restore() {
        if (isRunning.value || isRestoring.value) return;
        isRestoring.value = true;
        const expectedVersion = ++version;
        try {
            const response = await axios.get<{ run: TaskRun | null }>(`${config.apiBaseUrl}/tasks/runs/latest`, { timeout: 10000 });
            if (expectedVersion !== version) return;
            if (response.data.run) {
                apply(response.data.run);
                if (isRunning.value) poll(expectedVersion);
            }
        } catch {
            statusError.value = 'Unable to recover the latest task status. You can retry by refreshing the page.';
        } finally {
            isRestoring.value = false;
        }
    }

    async function runTask(label: string, request: () => Promise<{ data: TaskRun }>) {
        if (isRunning.value || isRestoring.value) return;
        const expectedVersion = ++version;
        clearTimeout(timer);
        isRunning.value = true;
        activeTask.value = label;
        lastMessage.value = '';
        error.value = '';
        statusError.value = '';
        try {
            const response = await request();
            apply(response.data);
            if (isRunning.value) poll(expectedVersion);
        } catch (caughtError) {
            isRunning.value = false;
            const startError = axios.isAxiosError<{ detail?: string }>(caughtError)
                ? caughtError.response?.data.detail || `Unable to confirm that ${label} started. Check the latest task before retrying.`
                : `Unable to start ${label}.`;
            error.value = startError;
            // A timed-out response may still have started a task; reconcile, never retry POST.
            await restore();
            if (!isRunning.value) error.value = startError;
        }
    }

    const options = { timeout: 10000 };
    const processSource = () => runTask('Process source', () => axios.post<TaskRun>(`${config.apiBaseUrl}/tasks/process-source`, null, options));
    const checkMissingSql = (fix: boolean) => runTask(fix ? 'Fix missing SQL' : 'Check missing SQL', () =>
        axios.post<TaskRun>(`${config.apiBaseUrl}/tasks/check-missing-sql`, null, { ...options, params: { fix } }));
    const checkMissingChapters = () => runTask('Check missing chapters', () =>
        axios.post<TaskRun>(`${config.apiBaseUrl}/tasks/check-missing-chapters`, null, options));
    const checkMangaUpdates = () => runTask('Check MangaUpdates', () =>
        axios.post<TaskRun>(`${config.apiBaseUrl}/tasks/check-manga-updates`, null, options));
    const updateAnilistId = (series: string, anilistId: string) => runTask('Update AniList ID', () =>
        axios.post<TaskRun>(`${config.apiBaseUrl}/tasks/update-anilist-id`, { series, anilistId }, options));

    return { isRunning, isRestoring, activeTask, runId, lastMessage, error, statusError, restore,
        processSource, checkMissingSql, checkMissingChapters, checkMangaUpdates, updateAnilistId };
});
