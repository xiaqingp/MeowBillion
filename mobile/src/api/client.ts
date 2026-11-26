import { fetchJsonWithTimeout, RequestTimeoutError } from './connection';

type FetchImplementation = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

type ApiClientOptions = {
  baseUrl: string;
  getToken: () => Promise<string | null>;
  fetchImpl?: FetchImplementation;
  onUnauthorized?: () => void | Promise<void>;
};

export function createApiClient({ baseUrl, getToken, fetchImpl = fetch, onUnauthorized }: ApiClientOptions) {
  async function request<T>(path: string, init: RequestInit = {}, timeoutMs?: number): Promise<T> {
    const token = await getToken();
    const headers = new Headers(init.headers);
    headers.set('Accept', 'application/json');
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
    if (init.body && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }

    const { response, payload } = await fetchJsonWithTimeout<T | null>(`${baseUrl}${path}`, { ...init, headers }, fetchImpl, timeoutMs);
    if (!response.ok) {
      if (response.status === 401) await onUnauthorized?.();
      throw new ApiError((payload as { error?: string } | null)?.error || `Request failed (${response.status})`, response.status);
    }
    return payload as T;
  }

  async function get<T>(path: string, { retry = false } = {}): Promise<T> {
    try {
      return await request<T>(path);
    } catch (error) {
      const transient = error instanceof RequestTimeoutError
        || (error instanceof TypeError && /network request failed|failed to fetch/i.test(error.message))
        || (error instanceof ApiError && [502, 503, 504].includes(error.status));
      if (!retry || !transient) throw error;
      return request<T>(path);
    }
  }

  return {
    get,
    post: <T>(path: string, body?: unknown, { timeoutMs }: { timeoutMs?: number } = {}) => request<T>(path, {
      method: 'POST',
      body: body === undefined ? undefined : JSON.stringify(body),
    }, timeoutMs),
    patch: <T>(path: string, body?: unknown) => request<T>(path, {
      method: 'PATCH',
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
    delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  };
}
