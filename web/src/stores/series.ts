import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import config from '@/config';

export interface Series {
    series: string;
    anilistId: number | null;
    last_updated: string | null;
    quarantined: boolean;
    latest_stored_chapter: number | null;
    mangaupdates_id: number | null;
    mangaupdates_latest_chapter: number | null;
    mangaupdates_url: string | null;
    anilist_last_read: number | null;
    mangaupdates_status: 'up_to_date' | 'missing_chapters' | 'unavailable' | 'unknown';
    mangaupdates_status_reason: string | null;
    suwayomi_sources: { manga_id: number; name: string; url: string }[];
    suwayomi_status_reason: string | null;
}

export type MangaUpdatesStatus = Series['mangaupdates_status'];
export interface MigrationManga {
    manga_id: number;
    title: string;
    source_id: string;
    source_name: string;
    in_library: boolean;
    url: string;
}
export interface MigrationContext {
    original: MigrationManga;
    sources: { id: string; name: string; language: string }[];
}
export interface MigrationSearchResult {
    results: { manga_id: number; title: string; in_library: boolean; url: string }[];
    has_next_page: boolean;
    page: number;
}
export interface MigrationOptions {
    original_manga_id: number;
    destination_manga_id: number;
    migrate_chapters: boolean;
    migrate_categories: boolean;
}
export interface MigrationPreview {
    original: MigrationManga;
    destination: MigrationManga;
    read_chapters: number;
    bookmarked_chapters: number;
    categories: number;
    tracking_records: number;
    unmatched_bookmarks: number[];
    preview_token: string;
}
export interface MigrationResult {
    status: 'completed' | 'partial' | 'uncertain';
    stage: string;
    completed_steps: string[];
    message: string;
    destination: MigrationManga;
    warnings: string[];
}
export const migrationErrorMessage = (error: unknown) => {
    const detail = axios.isAxiosError(error) ? error.response?.data?.detail : undefined;
    return typeof detail === 'string' ? detail : 'Unable to contact Suwayomi. Check the connection and try again.';
};
export const migrationPreviewChanged = (error: unknown) => axios.isAxiosError(error) && error.response?.status === 409;
export type SortColumn = 'series' | 'last_updated' | 'quarantined';
export type SortDirection = 'asc' | 'desc';
export type QuarantineReason =
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

interface GapDownloadResult {
    status: 'queued' | 'already_available' | 'no_matches' | 'no_source';
    queued_chapters: number[];
    already_downloaded: number[];
    already_queued: number[];
    warnings: string[];
}
interface GapDownloadState {
    loading: boolean;
    error: string;
    result?: GapDownloadResult;
}

export const gapDownloadKey = (id: number, reason: QuarantineReason) => reason.type === 'tracker_gap'
    ? `${id}:tracker:${reason.last_read}:${reason.first_stored}`
    : `${id}:consecutive:${reason.before}:${reason.after}`;

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
    mangaupdatesStatus?: MangaUpdatesStatus;
    sortBy?: SortColumn;
    sortDirection?: SortDirection;
}

export const useSeriesStore = defineStore('series', () => {
    const series = ref<Series[]>([]);
    const total = ref(0);
    const isLoading = ref(false);
    const error = ref('');
    const quarantineDetails = ref<Record<number, DetailsState>>({});
    const gapDownloads = ref<Record<string, GapDownloadState>>({});

    const fetchMigrationContext = async (id: number, originalMangaId: number) => {
        const response = await axios.get<MigrationContext>(`${config.apiBaseUrl}/database/series/${id}/migration`, {
            params: { original_manga_id: originalMangaId },
        });
        return response.data;
    };
    const searchMigration = async (id: number, originalMangaId: number, sourceId: string, query: string, page: number) => {
        const response = await axios.post<MigrationSearchResult>(
            `${config.apiBaseUrl}/database/series/${id}/migration/search`,
            { original_manga_id: originalMangaId, source_id: sourceId, query, page },
        );
        return response.data;
    };
    const previewMigration = async (id: number, options: MigrationOptions) => {
        const response = await axios.post<MigrationPreview>(
            `${config.apiBaseUrl}/database/series/${id}/migration/preview`, options,
        );
        return response.data;
    };
    const migrateSeries = async (id: number, options: MigrationOptions, previewToken: string) => {
        const response = await axios.post<MigrationResult>(
            `${config.apiBaseUrl}/database/series/${id}/migration`, { ...options, preview_token: previewToken },
        );
        return response.data;
    };

    const fetchQuarantineDetails = async (id: number, force = false) => {
        const existing = quarantineDetails.value[id];
        if (existing?.loading || (existing?.data && !force)) return;
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

    const downloadQuarantineGap = async (id: number, reason: QuarantineReason) => {
        const key = gapDownloadKey(id, reason);
        if (gapDownloads.value[key]?.loading) return;
        gapDownloads.value[key] = { loading: true, error: '' };
        try {
            const response = await axios.post<GapDownloadResult>(
                `${config.apiBaseUrl}/database/series/${id}/quarantine-gap/download`, reason,
            );
            gapDownloads.value[key] = { loading: false, error: '', result: response.data };
        } catch (caughtError) {
            const detail = axios.isAxiosError(caughtError) ? caughtError.response?.data?.detail : undefined;
            gapDownloads.value[key] = {
                loading: false,
                error: typeof detail === 'string' ? detail : 'Unable to queue missing chapters. Please try again.',
            };
            if (axios.isAxiosError(caughtError) && caughtError.response?.status === 409) {
                await fetchQuarantineDetails(id, true);
            }
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
                    mangaupdates_status: options.mangaupdatesStatus,
                    sort_by: options.sortBy ?? 'last_updated',
                    sort_direction: options.sortDirection ?? 'desc',
                },
            });
            series.value = response.data.series.map((item) => ({
                ...item,
                // Keep the UI usable while an older backend is awaiting restart.
                suwayomi_sources: item.suwayomi_sources ?? [],
                suwayomi_status_reason: item.suwayomi_status_reason ?? null,
            }));
            total.value = response.data.total;
        } catch (caughtError) {
            console.error('Error fetching series:', caughtError);
            error.value = 'Unable to fetch series. Please try again.';
        } finally {
            isLoading.value = false;
        }
    };

    const refreshMangaUpdatesChapter = async (seriesId: number) => {
        const response = await axios.get<{ series_id: number; latest_chapter: number | null }>(
            `${config.apiBaseUrl}/mangaupd/latest/${seriesId}`,
        );
        return response.data.latest_chapter;
    };

    return {
        series, total, isLoading, error, fetchSeries, quarantineDetails,
        fetchQuarantineDetails, refreshMangaUpdatesChapter, gapDownloads, downloadQuarantineGap,
        fetchMigrationContext, searchMigration, previewMigration, migrateSeries,
    };
});
