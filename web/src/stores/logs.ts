import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import config from '@/config';

type LogChunk = {
    logs: string;
    exists: boolean;
    cursor: string;
    reset: boolean;
    truncated: boolean;
};

const MAX_DISPLAY_CHARS = 256 * 1024;

export const useLogsStore = defineStore('logs', () => {
    const logs = ref('');
    const exists = ref(false);
    const isLoading = ref(false);
    const error = ref('');
    const truncated = ref(false);
    const connection = ref<'connecting' | 'live' | 'reconnecting' | 'complete' | 'offline'>('offline');
    let source: EventSource | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | null = null;
    let epoch = 0;
    let cursor = '';
    let selectedRun: string | undefined;
    let watching = false;

    function apply(chunk: LogChunk) {
        exists.value = chunk.exists;
        if (chunk.reset) {
            logs.value = chunk.logs;
            truncated.value = chunk.truncated;
        } else if (chunk.cursor !== cursor) {
            logs.value += chunk.logs;
        }
        if (logs.value.length > MAX_DISPLAY_CHARS) {
            logs.value = logs.value.slice(-MAX_DISPLAY_CHARS);
            truncated.value = true;
        }
        cursor = chunk.cursor;
        error.value = '';
        isLoading.value = false;
    }

    function stop() {
        watching = false;
        epoch++;
        source?.close();
        source = null;
        clearTimeout(retryTimer);
        controller?.abort();
        controller = null;
        isLoading.value = false;
        connection.value = 'offline';
    }

    async function snapshot(version: number, resume = false) {
        controller = new AbortController();
        try {
            const response = await axios.get<LogChunk>(`${config.apiBaseUrl}/logs`, {
                params: { run_id: selectedRun, cursor: resume ? cursor || undefined : undefined },
                signal: controller.signal,
                timeout: 10000,
            });
            if (version !== epoch) return;
            apply({ ...response.data, reset: resume ? response.data.reset : true });
        } catch (caughtError) {
            if (version !== epoch || axios.isCancel(caughtError)) return;
            if (axios.isAxiosError(caughtError) && caughtError.response?.status === 404 && selectedRun) {
                error.value = 'This run is no longer retained. Open the Logs page for the latest output.';
                watching = false;
                connection.value = 'offline';
                isLoading.value = false;
                return;
            }
            error.value = 'Unable to fetch logs. Retrying…';
            isLoading.value = false;
        }
    }

    function connect(version: number) {
        if (!watching || version !== epoch) return;
        const url = new URL(`${config.apiBaseUrl}/logs/stream`, window.location.origin);
        if (selectedRun) url.searchParams.set('run_id', selectedRun);
        if (cursor) url.searchParams.set('cursor', cursor);
        const stream = new EventSource(url.toString());
        source = stream;
        stream.onopen = () => {
            if (source !== stream) return;
            connection.value = 'live';
            error.value = '';
        };
        stream.addEventListener('logs', (event) => {
            if (source !== stream) return;
            apply(JSON.parse((event as MessageEvent<string>).data) as LogChunk);
        });
        stream.addEventListener('done', () => {
            if (source !== stream) return;
            connection.value = 'complete';
            stream.close();
            source = null;
        });
        stream.addEventListener('unavailable', () => {
            if (source !== stream) return;
            error.value = 'This run is no longer retained. Start a task or open the Logs page for the latest output.';
            connection.value = 'offline';
            stream.close();
            source = null;
        });
        stream.onerror = () => {
            if (source !== stream) return;
            stream.close();
            source = null;
            connection.value = 'reconnecting';
            // Bounded polling keeps output usable if a proxy cannot stream SSE.
            // Reconnect from the polling cursor, never replay already displayed bytes.
            retryTimer = setTimeout(async () => {
                await snapshot(version, true);
                connect(version);
            }, 2000);
        };
    }

    async function start(runId?: string) {
        stop();
        watching = true;
        const version = epoch;
        selectedRun = runId;
        cursor = '';
        logs.value = '';
        exists.value = false;
        truncated.value = false;
        error.value = '';
        isLoading.value = true;
        connection.value = 'connecting';
        await snapshot(version);
        connect(version);
    }

    const fetchLogs = () => start(selectedRun);

    return { logs, exists, isLoading, error, truncated, connection, start, stop, fetchLogs };
});
