import assert from 'node:assert/strict';
import { after, beforeEach, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import { createPinia, setActivePinia } from 'pinia';
import axios from 'axios';

// Use Vite's existing TS/alias loader, with Node's test runner: no new dependencies.
const server = await createServer({
  configFile: false,
  server: { middlewareMode: true, hmr: false },
  optimizeDeps: { noDiscovery: true, include: [] },
  resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
});
const { useLogsStore } = await server.ssrLoadModule('/src/stores/logs.ts');
const { useTasksStore } = await server.ssrLoadModule('/src/stores/tasks.ts');
const { useSeriesStore } = await server.ssrLoadModule('/src/stores/series.ts');
after(() => server.close());

class FakeEventSource {
  static instances = [];
  listeners = new Map();
  closed = false;
  constructor(url) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }
  addEventListener(name, callback) { this.listeners.set(name, callback); }
  emit(name, data) { this.listeners.get(name)?.({ data: JSON.stringify(data) }); }
  close() { this.closed = true; }
}

beforeEach(() => {
  setActivePinia(createPinia());
  FakeEventSource.instances = [];
  globalThis.EventSource = FakeEventSource;
  globalThis.window = { location: { origin: 'http://test.local' } };
});

const chunk = (logs, cursor, reset = false) => ({ logs, cursor, reset, exists: true, truncated: false });
const run = (status = 'running', id = 'a'.repeat(32)) => ({
  id, label: 'Check missing SQL', status,
  result: status === 'succeeded' ? { message: 'Finished check' } : null,
  error: status === 'failed' ? 'Task failed. See its logs for details.' : null,
});
const settle = () => new Promise(setImmediate);

test('series problem filters send true and false and retain the unclassified count', async (t) => {
  const requested = [];
  t.mock.method(axios, 'get', async (url, options) => {
    assert.match(url, /\/database\/series$/);
    requested.push(options.params);
    return { data: { series: [], total: 0, limit: 50, offset: 0,
      ...(options.params.has_problems === undefined ? {} : { unknown_problem_count: 3 }) } };
  });
  const store = useSeriesStore();
  await store.fetchSeries({ hasProblems: true, title: 'Alpha', quarantined: false, offset: 50 });
  assert.equal(requested[0].has_problems, true);
  assert.equal(requested[0].title, 'Alpha');
  assert.equal(requested[0].quarantined, false);
  assert.equal(requested[0].offset, 50);
  assert.equal(store.unknownProblemCount, 3);
  await store.fetchSeries({ hasProblems: false });
  assert.equal(requested[1].has_problems, false);
  assert.equal(store.unknownProblemCount, 3);
  await store.fetchSeries();
  assert.equal(requested[2].has_problems, undefined);
  assert.equal(store.unknownProblemCount, 0);
});

test('series problems check all or individually and merge only the checked types', async (t) => {
  const gap = { type: 'consecutive_gap', before: 5, after: 8 };
  const lag = { type: 'mangaupdates_lag', after: 8, through: 10 };
  let calls = 0;
  t.mock.method(axios, 'get', async (url, options) => {
    assert.match(url, /\/database\/series\/42\/problems$/);
    calls++;
    assert.equal(options.params.toString(), calls === 1 ? '' : 'checks=mangaupdates_lag');
    return { data: calls === 1 ? {
      problems: [gap, lag],
      checks: [{ type: 'consecutive_gap', status: 'checked', message: null },
        { type: 'mangaupdates_lag', status: 'checked', message: null }],
    } : { problems: [], checks: [{ type: 'mangaupdates_lag', status: 'checked', message: null }] } };
  });
  const store = useSeriesStore();
  await store.fetchSeriesProblems(42);
  assert.deepEqual(store.seriesProblems[42].data.problems, [gap, lag]);
  await store.fetchSeriesProblems(42, ['mangaupdates_lag']);
  assert.deepEqual(store.seriesProblems[42].data.problems, [gap]);
  assert.equal(store.seriesProblems[42].data.checks.length, 2);
});

test('series problem checks prevent duplicate requests and retain unavailable status', async (t) => {
  let resolve;
  let calls = 0;
  t.mock.method(axios, 'get', () => {
    calls++;
    return new Promise(done => { resolve = done; });
  });
  const store = useSeriesStore();
  const pending = store.fetchSeriesProblems(42);
  await store.fetchSeriesProblems(42, ['tracker_gap']);
  assert.equal(calls, 1);
  resolve({ data: { problems: [], checks: [{ type: 'tracker_gap', status: 'unavailable', message: 'No progress.' }] } });
  await pending;
  assert.equal(store.seriesProblems[42].loading, false);
  assert.equal(store.seriesProblems[42].data.checks[0].status, 'unavailable');
});

test('problem download sends the finding once and keeps queue feedback', async (t) => {
  const problem = { type: 'mangaupdates_lag', after: 8, through: 10.5 };
  const result = { status: 'queued', queued_chapters: [9, 10, 10.5], already_downloaded: [], already_queued: [], warnings: [] };
  let resolve;
  let calls = 0;
  t.mock.method(axios, 'post', (url, body) => {
    calls++;
    assert.match(url, /\/database\/series\/42\/problems\/download$/);
    assert.deepEqual(body, problem);
    return new Promise(done => { resolve = done; });
  });
  const store = useSeriesStore();
  const pending = store.downloadSeriesProblem(42, problem);
  await store.downloadSeriesProblem(42, problem);
  assert.equal(calls, 1);
  resolve({ data: result });
  await pending;
  assert.deepEqual(store.problemDownloads['42:mangaupdates:8:10.5'].result, result);
});

test('stale problem download refreshes only its individual check without retrying the mutation', async (t) => {
  const problem = { type: 'mangaupdates_lag', after: 8, through: 10 };
  let posts = 0;
  t.mock.method(axios, 'post', async () => {
    posts++;
    throw { isAxiosError: true, response: { status: 409, data: { detail: 'Problem changed.' } } };
  });
  t.mock.method(axios, 'get', async (_url, options) => {
    assert.equal(options.params.toString(), 'checks=mangaupdates_lag');
    return { data: { problems: [], checks: [{ type: 'mangaupdates_lag', status: 'checked', message: null }] } };
  });
  const store = useSeriesStore();
  await store.downloadSeriesProblem(42, problem);
  assert.equal(posts, 1);
  assert.equal(store.problemDownloads['42:mangaupdates:8:10'].error, 'Problem changed.');
  assert.equal(store.seriesProblems[42].notice, 'Problem changed.');
  assert.deepEqual(store.seriesProblems[42].data.problems, []);
});

test('series problems check failure is explicit and can be retried', async (t) => {
  t.mock.method(axios, 'get', async () => { throw new Error('Unavailable'); });
  const store = useSeriesStore();
  await store.fetchSeriesProblems(42);
  assert.match(store.seriesProblems[42].error, /Unable to check/);
  assert.equal(store.seriesProblems[42].loading, false);
});

test('migration suggestions send only original entry and title and preserve ranked candidates', async (t) => {
  const result = {
    candidates: [{ manga_id: 2, source_id: '9007199254740995', source_name: 'English source',
      title: 'Example manga', chapter_count: 12, in_library: false, url: 'http://reader/manga/2' }],
    warnings: ['One source failed.'], complete: false,
  };
  t.mock.method(axios, 'post', async (url, body) => {
    assert.match(url, /\/database\/series\/42\/migration\/suggest$/);
    assert.deepEqual(body, { original_manga_id: 1, query: 'Example manga' });
    return { data: result };
  });
  assert.deepEqual(await useSeriesStore().suggestMigration(42, 1, 'Example manga'), result);
});

test('migration suggestion errors propagate without retrying or migrating', async (t) => {
  let calls = 0;
  t.mock.method(axios, 'post', async () => {
    calls++;
    throw new Error('Unavailable');
  });
  await assert.rejects(useSeriesStore().suggestMigration(42, 1, 'Example manga'), /Unavailable/);
  assert.equal(calls, 1);
});

test('snapshot + SSE append, duplicate cursors, rotation and completed stream', async (t) => {
  t.mock.method(axios, 'get', async () => ({ data: chunk('first\n', 'one:6', true) }));
  const store = useLogsStore();
  await store.start('a'.repeat(32));
  const source = FakeEventSource.instances.at(-1);
  assert.equal(new URL(source.url).searchParams.get('cursor'), 'one:6');
  source.onopen();
  source.emit('logs', chunk('second\n', 'one:13'));
  source.emit('logs', chunk('second\n', 'one:13'));
  assert.equal(store.logs, 'first\nsecond\n');
  source.emit('logs', chunk('new run\n', 'two:8', true));
  assert.equal(store.logs, 'new run\n');
  source.emit('done', run('succeeded'));
  assert.equal(store.connection, 'complete');
  assert.equal(source.closed, true);
  store.stop();
});

test('reconnect polls bounded output and resumes SSE from the updated cursor', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const requests = [];
  t.mock.method(axios, 'get', async (_url, options) => {
    requests.push(options.params);
    return { data: requests.length === 1 ? chunk('first\n', 'one:6', true) : chunk('second\n', 'one:13') };
  });
  const store = useLogsStore();
  await store.start();
  const firstSource = FakeEventSource.instances.at(-1);
  firstSource.onerror();
  assert.equal(store.connection, 'reconnecting');
  assert.equal(firstSource.closed, true);
  t.mock.timers.tick(2000);
  await settle();
  assert.equal(requests[1].cursor, 'one:6');
  assert.equal(store.logs, 'first\nsecond\n');
  const nextSource = FakeEventSource.instances.at(-1);
  assert.equal(new URL(nextSource.url).searchParams.get('cursor'), 'one:13');
  firstSource.emit('logs', chunk('obsolete', 'one:999'));
  assert.equal(store.logs, 'first\nsecond\n');
  store.stop();
});

test('bounded display and stale snapshot cancellation on navigation', async (t) => {
  let resolveFirst;
  t.mock.method(axios, 'get', (_url, options) => options.params.run_id === 'old'
    ? new Promise(resolve => { resolveFirst = resolve; })
    : Promise.resolve({ data: chunk('new output', 'two:10', true) }));
  const store = useLogsStore();
  const pending = store.start('old');
  await store.start('new');
  resolveFirst({ data: chunk('old output', 'one:10', true) });
  await pending;
  assert.equal(store.logs, 'new output');
  assert.equal(FakeEventSource.instances.length, 1);
  const source = FakeEventSource.instances.at(-1);
  source.emit('logs', chunk('x'.repeat(300 * 1024), 'two:307210'));
  assert.equal(store.logs.length, 256 * 1024);
  assert.equal(store.truncated, true);
  store.stop();
});

test('missing retained run stops retrying rather than reconnecting forever', async (t) => {
  t.mock.method(axios, 'get', async () => {
    throw { isAxiosError: true, response: { status: 404 } };
  });
  const store = useLogsStore();
  await store.start('a'.repeat(32));
  assert.match(store.error, /no longer retained/);
  assert.equal(store.connection, 'offline');
  assert.equal(FakeEventSource.instances.length, 0);
  store.stop();
});

test('restores a running task after refresh and polls its final result', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  t.mock.method(axios, 'get', async url => ({ data: url.endsWith('/latest') ? { run: run() } : run('succeeded') }));
  const store = useTasksStore();
  await store.restore();
  assert.equal(store.isRunning, true);
  assert.equal(store.runId, 'a'.repeat(32));
  t.mock.timers.tick(1000);
  await settle();
  assert.equal(store.isRunning, false);
  assert.equal(store.lastMessage, 'Finished check');
});

test('status network loss keeps tasks disabled and retries without restarting work', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let polls = 0;
  t.mock.method(axios, 'get', async url => {
    if (url.endsWith('/latest')) return { data: { run: run() } };
    if (++polls === 1) throw new Error('offline');
    return { data: run('failed') };
  });
  const post = t.mock.method(axios, 'post', async () => ({ data: run() }));
  const store = useTasksStore();
  await store.restore();
  t.mock.timers.tick(1000);
  await settle();
  assert.equal(store.isRunning, true);
  assert.match(store.statusError, /Reconnecting/);
  await store.processSource();
  assert.equal(post.mock.callCount(), 0);
  t.mock.timers.tick(1000);
  await settle();
  assert.equal(store.isRunning, false);
  assert.match(store.error, /Task failed/);
  assert.equal(store.statusError, '');
});

test('lost POST response reconciles the running task, never resubmits', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const post = t.mock.method(axios, 'post', async () => { throw new Error('lost response'); });
  t.mock.method(axios, 'get', async () => ({ data: { run: run() } }));
  const store = useTasksStore();
  await store.checkMissingSql(false);
  assert.equal(store.isRunning, true);
  assert.equal(store.runId, 'a'.repeat(32));
  assert.equal(post.mock.callCount(), 1);
});

test('rejected start preserves server error instead of reporting an older task success', async (t) => {
  t.mock.method(axios, 'post', async () => {
    throw { isAxiosError: true, response: { status: 409, data: { detail: 'A CLI task is running.' } } };
  });
  t.mock.method(axios, 'get', async () => ({ data: { run: run('succeeded') } }));
  const store = useTasksStore();
  await store.checkMissingSql(false);
  assert.equal(store.isRunning, false);
  assert.equal(store.error, 'A CLI task is running.');
});
