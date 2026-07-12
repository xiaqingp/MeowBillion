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

const REQUEST_TIMEOUT_MS = 10_000;

export function createApiClient({ baseUrl, getToken, fetchImpl = fetch, onUnauthorized }: ApiClientOptions) {
  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const token = await getToken();
    const headers = new Headers(init.headers);
    headers.set('Accept', 'application/json');
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
    if (init.body && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    let response: Response;
    let payload: T | null;
    try {
      response = await fetchImpl(`${baseUrl}${path}`, { ...init, headers, signal: controller.signal });
      const text = await response.text();
      try { payload = text ? JSON.parse(text) as T : null; } catch { throw new Error(`The server returned an unreadable response (HTTP ${response.status}).`); }
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') throw new Error('Connection timed out. Check the server address and network connection.');
      throw error;
    } finally { clearTimeout(timeout); }
    if (!response.ok) {
      if (response.status === 401) await onUnauthorized?.();
      throw new ApiError((payload as { error?: string } | null)?.error || `Request failed (${response.status})`, response.status);
    }
    return payload as T;
  }

  return {
    get: <T>(path: string) => request<T>(path),
    post: <T>(path: string, body?: unknown) => request<T>(path, {
      method: 'POST',
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
    patch: <T>(path: string, body?: unknown) => request<T>(path, {
      method: 'PATCH',
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
    delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  };
}
