<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { migrationErrorMessage, migrationPreviewChanged, useSeriesStore } from '../stores/series';
import type { MigrationContext, MigrationOptions, MigrationPreview, MigrationResult, MigrationSearchResult } from '../stores/series';

const props = defineProps<{ anilistId: number; originalMangaId: number; series: string }>();
const emit = defineEmits<{ close: []; changed: [] }>();
const store = useSeriesStore();
const dialog = ref<HTMLDialogElement>();
const context = ref<MigrationContext>();
const sourceId = ref('');
const query = ref('');
const searchResults = ref<MigrationSearchResult>();
const selectedId = ref<number | null>(null);
const migrateChapters = ref(true);
const migrateCategories = ref(true);
const preview = ref<MigrationPreview>();
const result = ref<MigrationResult>();
const busy = ref<'context' | 'search' | 'preview' | 'migration' | ''>('context');
const error = ref('');
const requestUncertain = ref(false);
let generation = 0;
let opener: HTMLElement | null = null;
const options = computed<MigrationOptions>(() => ({
  original_manga_id: props.originalMangaId,
  destination_manga_id: selectedId.value ?? -1,
  migrate_chapters: migrateChapters.value,
  migrate_categories: migrateCategories.value,
}));

const close = () => {
  if (busy.value === 'migration') return;
  generation++;
  dialog.value?.close();
  emit('close');
};
const backdropClick = (event: MouseEvent) => {
  if (event.target !== dialog.value || !dialog.value) return;
  const bounds = dialog.value.getBoundingClientRect();
  if (event.clientX < bounds.left || event.clientX > bounds.right
    || event.clientY < bounds.top || event.clientY > bounds.bottom) close();
};

const loadContext = async () => {
  const current = ++generation;
  busy.value = 'context';
  error.value = '';
  try {
    const data = await store.fetchMigrationContext(props.anilistId, props.originalMangaId);
    if (current !== generation) return;
    context.value = data;
    query.value = data.original.title;
    await nextTick();
    dialog.value?.querySelector<HTMLSelectElement>('select')?.focus();
  } catch (caught) {
    if (current === generation) error.value = migrationErrorMessage(caught);
  } finally {
    if (current === generation) busy.value = '';
  }
};

watch([sourceId, query], () => {
  if (busy.value === 'context') return;
  generation++;
  if (busy.value === 'search' || busy.value === 'preview') busy.value = '';
  searchResults.value = undefined;
  selectedId.value = null;
  preview.value = undefined;
});
watch([selectedId, migrateChapters, migrateCategories], () => {
  generation++;
  if (busy.value === 'preview') busy.value = '';
  preview.value = undefined;
});

const search = async (page = 1) => {
  if (busy.value || !sourceId.value || !query.value.trim()) return;
  preview.value = undefined;
  selectedId.value = null;
  await nextTick();
  const current = ++generation;
  busy.value = 'search';
  error.value = '';
  try {
    const data = await store.searchMigration(props.anilistId, props.originalMangaId, sourceId.value, query.value.trim(), page);
    if (current === generation) searchResults.value = data;
  } catch (caught) {
    if (current === generation) error.value = migrationErrorMessage(caught);
  } finally {
    if (current === generation) busy.value = '';
  }
};

const review = async () => {
  if (busy.value || selectedId.value === null) return;
  const current = ++generation;
  busy.value = 'preview';
  preview.value = undefined;
  error.value = '';
  try {
    const data = await store.previewMigration(props.anilistId, options.value);
    if (current === generation) preview.value = data;
  } catch (caught) {
    if (current === generation) error.value = migrationErrorMessage(caught);
  } finally {
    if (current === generation) busy.value = '';
  }
};

const migrate = async () => {
  if (busy.value || !preview.value) return;
  busy.value = 'migration';
  error.value = '';
  const token = preview.value.preview_token;
  try {
    result.value = await store.migrateSeries(props.anilistId, options.value, token);
    emit('changed');
  } catch (caught) {
    // No automatic retry: the browser may have lost a successful response.
    error.value = migrationErrorMessage(caught);
    if (!migrationPreviewChanged(caught)) {
      requestUncertain.value = true;
      emit('changed');
    }
  } finally {
    preview.value = undefined;
    busy.value = '';
    await nextTick();
    dialog.value?.querySelector<HTMLButtonElement>('[data-close]')?.focus();
  }
};

onMounted(() => {
  opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  dialog.value?.showModal();
  void loadContext();
});
onBeforeUnmount(() => {
  generation++;
  dialog.value?.close();
  if (opener?.isConnected) opener.focus();
  else Array.from(document.querySelectorAll<HTMLButtonElement>('.series-details-toggle'))
    .find(button => button.getAttribute('aria-label')?.endsWith(`series details for ${props.series}`))?.focus();
});
</script>

<template>
  <Teleport to="body">
    <dialog ref="dialog" class="migration-dialog" aria-labelledby="migration-title"
      :aria-busy="Boolean(busy)" @cancel.prevent="close" @click="backdropClick">
      <header>
        <h2 id="migration-title">Migrate Suwayomi source</h2>
        <p>{{ series }}</p>
      </header>

      <p v-if="error" class="feedback feedback--error" role="alert">{{ error }}</p>
      <p v-if="busy" class="feedback" role="status">
        {{ busy === 'context' ? 'Loading installed sources…' : busy === 'search' ? 'Searching source…' : busy === 'preview' ? 'Refreshing destination and checking transfers…' : 'Migrating… Keep this window open until the result is confirmed.' }}
      </p>

      <template v-if="result">
        <section class="feedback" :class="result.status === 'completed' ? 'feedback--success' : 'feedback--warning'" role="status">
          <h3>{{ result.status === 'completed' ? 'Migration complete' : 'Check the migration in Suwayomi' }}</h3>
          <p>{{ result.message }}</p>
          <p v-if="result.status !== 'completed'">Stopped at: {{ result.stage.replace(/_/g, ' ') }}.</p>
          <p v-for="warning in result.warnings" :key="warning">{{ warning }}</p>
          <a :href="result.destination.url" target="_blank" rel="noopener noreferrer">Open destination in Suwayomi</a>
        </section>
      </template>
      <p v-else-if="requestUncertain" class="feedback feedback--warning" role="alert">
        The request was not confirmed; it may have changed either entry. Check both entries in Suwayomi before reopening migration. Do not retry blindly.
      </p>
      <template v-else-if="context">
        <p class="original-entry">From <a :href="context.original.url" target="_blank" rel="noopener noreferrer">{{ context.original.title }}</a> · {{ context.original.source_name }}</p>
        <p v-if="!context.sources.length" class="feedback">No other installed sources are available. Install a destination extension in Suwayomi first.</p>
        <template v-else>
          <form class="search-form" @submit.prevent="search()">
            <label>
              <span>Destination source</span>
              <select v-model="sourceId" :disabled="busy === 'migration'" required>
                <option value="" disabled>Choose a source</option>
                <option v-for="source in context.sources" :key="source.id" :value="source.id">{{ source.name }} ({{ source.language }})</option>
              </select>
            </label>
            <label>
              <span>Manga title</span>
              <input v-model="query" type="search" maxlength="300" required :disabled="busy === 'migration'" />
            </label>
            <button type="submit" :disabled="Boolean(busy) || !sourceId || !query.trim()">Search</button>
          </form>

          <fieldset v-if="searchResults" class="results" :disabled="Boolean(busy)">
            <legend>Choose the matching manga</legend>
            <p v-if="!searchResults.results.length">No manga matched this title. Try an alternate title or another source.</p>
            <label v-for="match in searchResults.results" :key="match.manga_id" class="result-option">
              <input v-model="selectedId" type="radio" name="migration-destination" :value="match.manga_id" />
              <span>{{ match.title }}<small v-if="match.in_library">Already in your library; existing state will be preserved.</small></span>
              <a :href="match.url" target="_blank" rel="noopener noreferrer" :aria-label="`Open ${match.title} in Suwayomi`">Open</a>
            </label>
            <nav v-if="searchResults.page > 1 || searchResults.has_next_page" class="actions" aria-label="Migration search pages">
              <button type="button" class="ghost" :disabled="Boolean(busy) || searchResults.page === 1" @click="search(searchResults.page - 1)">Previous</button>
              <span>Page {{ searchResults.page }}</span>
              <button type="button" class="ghost" :disabled="Boolean(busy) || !searchResults.has_next_page" @click="search(searchResults.page + 1)">Next</button>
            </nav>
          </fieldset>

          <section v-if="selectedId !== null" class="transfer-options">
            <h3>Transfer options</h3>
            <label class="checkbox"><input v-model="migrateChapters" type="checkbox" :disabled="busy === 'migration'" /> Read state and bookmarks</label>
            <label class="checkbox"><input v-model="migrateCategories" type="checkbox" :disabled="busy === 'migration'" /> Categories</label>
            <p>Tracking records, including AniList, are always transferred. Read state marks destination chapters through the original's highest read chapter; bookmarks match by chapter number.</p>
            <button v-if="!preview" type="button" class="ghost" :disabled="Boolean(busy)" @click="review">Review migration</button>
          </section>

          <section v-if="preview" class="review">
            <h3>Confirm migration</h3>
            <p><strong>{{ preview.original.source_name }}</strong> → <strong>{{ preview.destination.source_name }}</strong></p>
            <p>Destination: <a :href="preview.destination.url" target="_blank" rel="noopener noreferrer">{{ preview.destination.title }}</a></p>
            <dl>
              <div><dt>Chapters newly marked read</dt><dd>{{ preview.read_chapters }}</dd></div>
              <div><dt>New bookmarks</dt><dd>{{ preview.bookmarked_chapters }}</dd></div>
              <div><dt>Categories added</dt><dd>{{ preview.categories }}</dd></div>
              <div><dt>Tracking records retained on destination</dt><dd>{{ preview.tracking_records }}</dd></div>
            </dl>
            <p v-if="preview.unmatched_bookmarks.length" class="feedback feedback--warning">Bookmarks without matching destination chapters: {{ preview.unmatched_bookmarks.join(', ') }}.</p>
            <p class="consequence">The original will leave your Suwayomi library and its tracking bindings will be removed only after the destination is verified. Downloads, local CBZs, AniList progress and quarantine status stay unchanged. Client-specific metadata is not transferred.</p>
            <button type="button" :disabled="Boolean(busy)" @click="migrate">{{ busy === 'migration' ? 'Migrating…' : 'Confirm migration' }}</button>
          </section>
        </template>
      </template>
      <div class="actions dialog-footer">
        <button v-if="!context && !busy" type="button" class="ghost" @click="loadContext">Retry loading sources</button>
        <a v-if="context && (result || requestUncertain)" :href="context.original.url" target="_blank" rel="noopener noreferrer">Open original in Suwayomi</a>
        <button type="button" class="ghost" data-close :disabled="busy === 'migration'" @click="close">{{ result || requestUncertain ? 'Close' : 'Cancel' }}</button>
      </div>
    </dialog>
  </Teleport>
</template>

<style scoped>
/* Hallmark · pre-emit critique: P4 H4 E4 S5 R5 V3
 * Component-scope: migration dialog; existing custom-technical tokens.
 * states: default · hover · focus · active · disabled · loading · error · success
 */
.migration-dialog {
  position: fixed; inset: 0; margin: auto; height: fit-content;
  width: min(680px, calc(100vw - var(--space-8))); max-height: calc(100dvh - var(--space-8));
  overflow-y: auto; padding: var(--space-6); border: 1px solid var(--color-rule-strong);
  border-radius: var(--radius-md); background: var(--color-paper); color: var(--color-ink);
  font-family: var(--font-body); font-size: var(--text-sm);
}
.migration-dialog::backdrop { background: var(--color-ink); opacity: 0.55; }
header { padding-bottom: var(--space-4); border-bottom: 1px solid var(--color-rule); margin-bottom: var(--space-4); }
h2 { font-size: var(--text-md); }
h3 { font-size: var(--text-sm); margin-bottom: var(--space-2); }
p { max-width: none; margin-bottom: var(--space-3); }
header p { margin: var(--space-1) 0 0; color: var(--color-ink-2); }
.search-form { display: grid; gap: var(--space-3); }
.search-form label { display: grid; gap: var(--space-1); min-width: 0; }
input[type='search'], select { width: 100%; min-height: 44px; min-width: 0; }
button { white-space: nowrap; min-height: 44px; justify-self: start; }
button:active:not(:disabled) { background: var(--color-paper-4); color: var(--color-ink); }
button:disabled, fieldset:disabled { opacity: 0.6; cursor: not-allowed; }
input:focus-visible, select:focus-visible, button:focus-visible, a:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
input[type='checkbox'], input[type='radio'] { accent-color: var(--color-accent); flex: none; }
.results { margin-top: var(--space-5); border: 0; padding: 0; min-width: 0; }
legend { font-weight: var(--weight-medium); margin-bottom: var(--space-2); }
.result-option { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3) 0; border-bottom: 1px solid var(--color-rule); min-height: 44px; }
.result-option span { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.result-option small { display: block; color: var(--color-ink-2); margin-top: var(--space-1); }
.result-option a { flex: none; }
.transfer-options, .review { border-top: 1px solid var(--color-rule); margin-top: var(--space-5); padding-top: var(--space-4); }
.checkbox { display: flex; align-items: center; gap: var(--space-2); min-height: 44px; }
.transfer-options p, .consequence { color: var(--color-ink-2); }
dl { margin: var(--space-4) 0; }
dl div { display: flex; justify-content: space-between; gap: var(--space-3); padding: var(--space-1) 0; }
dd { font-family: var(--font-display); margin: 0; }
.actions { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-3); margin-top: var(--space-3); }
.dialog-footer { justify-content: flex-end; padding-top: var(--space-4); border-top: 1px solid var(--color-rule); margin-top: var(--space-5); }
.feedback { padding: var(--space-3); background: var(--color-paper-2); }
.feedback--error { color: var(--color-error); background: var(--color-error-bg); }
.feedback--warning { color: var(--color-warning); background: var(--color-warning-bg); }
.feedback--success { color: var(--color-success); border-left: 2px solid var(--color-success); }
@media (hover: hover) {
  .result-option:hover { background: var(--color-paper-2); }
  input[type='search']:hover, select:hover { background: var(--color-paper-2); }
}
@media (max-width: 640px) {
  .migration-dialog { padding: var(--space-4); width: calc(100vw - var(--space-4)); max-height: calc(100dvh - var(--space-4)); }
}
</style>
