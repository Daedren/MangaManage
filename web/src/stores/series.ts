import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import config from '@/config';

interface Series {
    series: string;
    anilistId: number | null;
    last_updated: string | null;
    quarantined: boolean;
    latest_stored_chapter: number | null;
    mangaupdates_id: number | null;
    mangaupdates_latest_chapter: number | null;
    anilist_last_read: number | null;
    mangaupdates_status: 'up_to_date' | 'missing_chapters' | 'unavailable' | 'unknown';
    mangaupdates_status_reason: string | null;
}

export type SortColumn = 'series' | 'last_updated' | 'quarantined';
export type SortDirection = 'asc' | 'desc';
type QuarantineReason =
    | { type: 'tracker_gap'; last_read: number; first_stored: number }
    | { type: 'consecutive_gap'; before: number; after: number };
interface QuarantineDetails {
    quarantined: boolean;
    status: 'gaps_found' | 'no_gaps' | 'no_active_chapters' | 'tracker_unavailable' | 'not_quarantined';
    reasons: QuarantineReason[];
}
interface DetailsState {
    loading: boolean;
    error: string;
    data?: QuarantineDetails;
}

interface SeriesResponse {
    series: Series[];
    total: number;
    limit: number;
    offset: number;
}

interface FetchOptions {
    title?: string;
    limit?: number;
    offset?: number;
    quarantined?: boolean;
    sortBy?: SortColumn;
    sortDirection?: SortDirection;
}

export const useSeriesStore = defineStore('series', () => {
    const series = ref<Series[]>([]);
    const total = ref(0);
    const isLoading = ref(false);
    const error = ref('');
    const quarantineDetails = ref<Record<number, DetailsState>>({});

    const fetchQuarantineDetails = async (id: number) => {
        const existing = quarantineDetails.value[id];
        if (existing?.loading || existing?.data) return;
        quarantineDetails.value[id] = { loading: true, error: '' };
        try {
            const response = await axios.get<QuarantineDetails>(
                `${config.apiBaseUrl}/database/series/${id}/quarantine-details`,
            );
            quarantineDetails.value[id] = { loading: false, error: '', data: response.data };
        } catch (caughtError) {
            console.error('Error fetching quarantine details:', caughtError);
            quarantineDetails.value[id] = {
                loading: false, error: 'Unable to load quarantine reasons. Please try again.',
            };
        }
    };

    const fetchSeries = async (options: FetchOptions = {}) => {
        isLoading.value = true;
        error.value = '';

        try {
            const response = await axios.get<SeriesResponse>(`${config.apiBaseUrl}/database/series`, {
                params: {
                    title: options.title?.trim() || undefined,
                    limit: options.limit ?? 50,
                    offset: options.offset ?? 0,
                    quarantined: options.quarantined,
                    sort_by: options.sortBy ?? 'last_updated',
                    sort_direction: options.sortDirection ?? 'desc',
                },
            });
            series.value = response.data.series;
            total.value = response.data.total;
        } catch (caughtError) {
            console.error('Error fetching series:', caughtError);
            error.value = 'Unable to fetch series. Please try again.';
        } finally {
            isLoading.value = false;
        }
    };

    return { series, total, isLoading, error, fetchSeries, quarantineDetails, fetchQuarantineDetails };
});
