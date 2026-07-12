import assert from 'node:assert/strict';
import test from 'node:test';

import { checkBackendConnection } from './connection';

test('reports a reachable backend status endpoint', async () => {
  const result = await checkBackendConnection('http://192.168.86.57:8090', async (url) => {
    assert.equal(url, 'http://192.168.86.57:8090/api/auth/status');
    return new Response(JSON.stringify({ authenticated: false }), { status: 200 });
  });

  assert.deepEqual(result, { ok: true, message: 'Server connection is available.' });
});

test('reports a backend HTTP error instead of silently waiting', async () => {
  const result = await checkBackendConnection('http://192.168.86.57:8090', async () => new Response('', { status: 503 }));

  assert.deepEqual(result, { ok: false, message: 'The server returned HTTP 503.' });
});

test('reports a network failure instead of silently waiting', async () => {
  const result = await checkBackendConnection('http://192.168.86.57:8090', async () => {
    throw new Error('Network request failed');
  });

  assert.equal(result.ok, false);
  assert.match(result.message, /Unable to reach the server/);
});
