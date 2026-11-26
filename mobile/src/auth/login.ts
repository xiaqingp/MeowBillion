import { fetchJsonWithTimeout } from '../api/connection';
import { MobileSession } from './session';

const LOGIN_TIMEOUT_MS = 35_000;

export async function loginMobile(endpoint: string, email: string, password: string, fetchImpl = fetch): Promise<MobileSession> {
  const { response, payload } = await fetchJsonWithTimeout<{
    access_token?: string;
    error?: string;
    user?: { id: string; display_name: string };
  }>(`${endpoint}/api/auth/mobile/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ email, password, device_name: 'MeowBillion Android' }),
  }, fetchImpl, LOGIN_TIMEOUT_MS);
  if (!response.ok) throw new Error(payload?.error || 'Sign in failed.');
  if (!payload?.access_token || !payload.user?.id) {
    throw new Error('The server returned an incomplete sign-in response.');
  }
  return {
    accessToken: payload.access_token,
    user: { id: payload.user.id, displayName: payload.user.display_name },
  };
}
