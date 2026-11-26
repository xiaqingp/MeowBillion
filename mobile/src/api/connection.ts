type FetchImplementation = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

const REQUEST_TIMEOUT_MS = 10_000;

export class RequestTimeoutError extends Error {
  constructor() {
    super('Connection timed out. Check the server address and network connection.');
    this.name = 'RequestTimeoutError';
  }
}

export async function fetchJsonWithTimeout<T>(
  input: RequestInfo | URL,
  init: RequestInit = {},
  fetchImpl: FetchImplementation = fetch,
  timeoutMs = REQUEST_TIMEOUT_MS,
): Promise<{ response: Response; payload: T }> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetchImpl(input, { ...init, signal: controller.signal });
    const text = await response.text();
    let payload: T;
    try {
      payload = (text ? JSON.parse(text) : null) as T;
    } catch {
      throw new Error(`The server returned an unreadable response (HTTP ${response.status}).`);
    }
    return { response, payload };
  } catch (error) {
    if (controller.signal.aborted) throw new RequestTimeoutError();
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export async function checkBackendConnection(
  baseUrl: string,
  fetchImpl: FetchImplementation = fetch,
): Promise<{ ok: boolean; message: string }> {
  try {
    const { response } = await fetchJsonWithTimeout(`${baseUrl}/api/auth/status`, {}, fetchImpl);
    if (!response.ok) {
      return { ok: false, message: `The server returned HTTP ${response.status}.` };
    }
    return { ok: true, message: 'Server connection is available.' };
  } catch {
    return { ok: false, message: 'Unable to reach the server. Check the address, port, and network connection.' };
  }
}
