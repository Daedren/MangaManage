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
  resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
});
const { useLogsStore } = await server.ssrLoadModule('/src/stores/logs.ts');
const { useTasksStore } = await server.ssrLoadModule('/src/stores/tasks.ts');
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
