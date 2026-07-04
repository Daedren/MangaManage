import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import config from '@/config';

export const useLogsStore = defineStore('logs', () => {
    const logs = ref('');
    const exists = ref(false);
    const isLoading = ref(false);
    const error = ref('');

    const fetchLogs = async () => {
        isLoading.value = true;
        error.value = '';

        try {
            const response = await axios.get(`${config.apiBaseUrl}/logs`);
            logs.value = response.data.logs;
            exists.value = response.data.exists;
        } catch (caughtError) {
            console.error('Error fetching logs:', caughtError);
            error.value = 'Unable to fetch logs.';
        } finally {
            isLoading.value = false;
        }
    };

    return { logs, exists, isLoading, error, fetchLogs };
});
