import assert from 'node:assert/strict';
import test from 'node:test';

import { RequestTimeoutError } from '../api/connection';
import { loginMobile } from './login';

test('accepts a login response that arrives after the old ten-second deadline', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const result = loginMobile('http://server', 'person@example.com', 'test-password', (url, init) => {
    assert.equal(url, 'http://server/api/auth/mobile/login');
    assert.equal(init?.method, 'POST');
    assert.equal(JSON.parse(String(init?.body)).device_name, 'MeowBillion Android');
    return new Promise((resolve) => {
      setTimeout(() => {
        assert.equal(init?.signal?.aborted, false);
        resolve(Response.json({ access_token: 'token', user: { id: 'member', display_name: 'Member' } }));
      }, 15_000);
    });
  });

  t.mock.timers.tick(15_000);
  assert.deepEqual(await result, { accessToken: 'token', user: { id: 'member', displayName: 'Member' } });
});

test('preserves the server login error and rejects incomplete responses', async () => {
  await assert.rejects(loginMobile('http://server', 'person@example.com', 'incorrect', async () =>
    Response.json({ error: 'Invalid email or password' }, { status: 401 })), /Invalid email or password/);
  await assert.rejects(loginMobile('http://server', 'person@example.com', 'password', async () =>
    Response.json({ user: { id: 'member' } })), /incomplete sign-in response/);
});

test('aborts an unresponsive login without issuing a second login POST', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let attempts = 0;
  const result = loginMobile('http://server', 'person@example.com', 'test-password', (_url, init) => {
    attempts++;
    return new Promise((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new Error('Aborted')), { once: true });
    });
  });

  const rejected = assert.rejects(result, RequestTimeoutError);
  t.mock.timers.tick(35_000);
  await rejected;
  assert.equal(attempts, 1);
});
