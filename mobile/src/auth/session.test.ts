import assert from 'node:assert/strict';
import test from 'node:test';

import { createSessionStore } from './session';

test('persists and clears the mobile session token', async () => {
  const values = new Map<string, string>();
  const store = createSessionStore({
    getItemAsync: async (key) => values.get(key) ?? null,
    setItemAsync: async (key, value) => void values.set(key, value),
    deleteItemAsync: async (key) => void values.delete(key),
  });

  await store.save({ accessToken: 'token-1', user: { id: 'user-1', displayName: 'Owner' } });
  assert.deepEqual(await store.load(), {
    accessToken: 'token-1',
    user: { id: 'user-1', displayName: 'Owner' },
  });

  await store.clear();
  assert.equal(await store.load(), null);
});
