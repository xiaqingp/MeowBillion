import assert from 'node:assert/strict';
import test from 'node:test';

import { ApiError, createApiClient } from './client';
import { RequestTimeoutError } from './connection';

test('adds the bearer token to API requests', async () => {
  let requestedUrl = '';
  let requestedHeaders: Headers | undefined;
  const client = createApiClient({
    baseUrl: 'http://10.0.2.2:5000',
    getToken: async () => 'mobile-token',
    fetchImpl: async (url, init) => {
      requestedUrl = String(url);
      requestedHeaders = new Headers(init?.headers);
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    },
  });

  const result = await client.get<{ ok: boolean }>('/api/accounts');

  assert.equal(requestedUrl, 'http://10.0.2.2:5000/api/accounts');
  assert.equal(requestedHeaders?.get('Authorization'), 'Bearer mobile-token');
  assert.deepEqual(result, { ok: true });
});

test('turns an unauthorized API response into an ApiError', async () => {
  let unauthorizedCalls = 0;
  const client = createApiClient({
    baseUrl: 'http://10.0.2.2:5000',
    getToken: async () => 'expired-token',
    fetchImpl: async () => new Response(JSON.stringify({ error: 'Authentication required' }), { status: 401 }),
    onUnauthorized: async () => { unauthorizedCalls += 1; },
  });

  await assert.rejects(client.get('/api/accounts', { retry: true }), (error: unknown) => {
    if (!(error instanceof ApiError)) {
      return false;
    }
    assert.equal(error.status, 401);
    assert.equal(error.message, 'Authentication required');
    return true;
  });
  assert.equal(unauthorizedCalls, 1);
});

test('sends PATCH and DELETE requests through the authenticated client', async () => {
  const requests: RequestInit[] = [];
  const api = createApiClient({ baseUrl: 'http://server', getToken: async () => 'token', fetchImpl: async (_url, init) => { requests.push(init || {}); return new Response('{}', { status: 200 }); } });
  await api.patch('/api/trips/trip_1', { name: 'Paris' });
  await api.delete('/api/trips/trip_1');
  assert.equal(requests[0]?.method, 'PATCH');
  assert.equal(requests[0]?.body, JSON.stringify({ name: 'Paris' }));
  assert.equal(requests[1]?.method, 'DELETE');
});

test('retries a slow overview GET once without asking the user to refresh', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let attempts = 0;
  let pendingSignal: AbortSignal | null | undefined;
  const api = createApiClient({
    baseUrl: 'http://server',
    getToken: async () => 'token',
    fetchImpl: async (_url, init) => {
      attempts++;
      if (attempts === 2) return new Response('{"net_worth":42}');
      pendingSignal = init?.signal;
      return new Promise((_resolve, reject) => {
        pendingSignal?.addEventListener('abort', () => reject(new TypeError('Network request failed')), { once: true });
      });
    },
  });

  const result = api.get('/api/allocation_accounts', { retry: true });
  await Promise.resolve();
  t.mock.timers.tick(10_000);
  assert.equal(pendingSignal?.aborted, true);
  assert.deepEqual(await result, { net_worth: 42 });
  assert.equal(attempts, 2);
});

test('uses the longer Plaid sync deadline and never resends the POST after a timeout', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let attempts = 0;
  let pendingSignal: AbortSignal | null | undefined;
  const api = createApiClient({
    baseUrl: 'http://server',
    getToken: async () => 'token',
    fetchImpl: async (url, init) => {
      attempts++;
      assert.equal(url, 'http://server/api/sync_transactions');
      assert.equal(init?.method, 'POST');
      assert.equal(new Headers(init?.headers).get('Authorization'), 'Bearer token');
      pendingSignal = init?.signal;
      return new Promise((_resolve, reject) => {
        pendingSignal?.addEventListener('abort', () => reject(new Error('Aborted')), { once: true });
      });
    },
  });

  const result = api.post('/api/sync_transactions', undefined, { timeoutMs: 180_000 });
  const rejected = assert.rejects(result, RequestTimeoutError);
  await Promise.resolve();
  t.mock.timers.tick(10_000);
  assert.equal(pendingSignal?.aborted, false);
  t.mock.timers.tick(170_000);
  await rejected;
  assert.equal(attempts, 1);
});
