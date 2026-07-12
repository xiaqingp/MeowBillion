import assert from 'node:assert/strict';
import test from 'node:test';

import { ApiError, createApiClient } from './client';

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

  await assert.rejects(client.get('/api/accounts'), (error: unknown) => {
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
