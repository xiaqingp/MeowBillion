import assert from 'node:assert/strict';
import test from 'node:test';

import { createApiEndpointStore, DEFAULT_API_ENDPOINT, normalizeApiEndpoint } from './apiEndpoint';

test('normalizes supported backend URLs', () => {
  assert.equal(normalizeApiEndpoint(' http://10.0.2.2:8090/ '), DEFAULT_API_ENDPOINT);
  assert.equal(normalizeApiEndpoint('https://finance.example.test/api/'), 'https://finance.example.test/api');
});

test('rejects unsupported backend URLs', () => {
  assert.throws(() => normalizeApiEndpoint('ftp://finance.example.test'), Error);
  assert.throws(() => normalizeApiEndpoint('not a url'), Error);
});

test('stores a normalized endpoint and falls back to the emulator default', async () => {
  const values = new Map<string, string>();
  const store = createApiEndpointStore({
    getItemAsync: async (key) => values.get(key) ?? null,
    setItemAsync: async (key, value) => void values.set(key, value),
  });

  assert.equal(await store.load(), DEFAULT_API_ENDPOINT);
  await store.save(' https://home.example.test:8443/ ');
  assert.equal(await store.load(), 'https://home.example.test:8443');
});
