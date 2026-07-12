const API_ENDPOINT_KEY = 'meowbillion.mobile.api-endpoint';

export const DEFAULT_API_ENDPOINT = 'http://10.0.2.2:8090';

export type EndpointStorage = {
  getItemAsync(key: string): Promise<string | null>;
  setItemAsync(key: string, value: string): Promise<void>;
};

export function normalizeApiEndpoint(value: string): string {
  const candidate = value.trim().replace(/\/+$/, '');
  let parsed: URL;

  try {
    parsed = new URL(candidate);
  } catch {
    throw new Error('Enter a valid server address.');
  }

  if (!parsed.hostname) {
    throw new Error('Enter a valid server address.');
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    throw new Error('The server address must start with http or https.');
  }

  return candidate;
}

export function createApiEndpointStore(storage: EndpointStorage) {
  return {
    async load(): Promise<string> {
      const stored = await storage.getItemAsync(API_ENDPOINT_KEY);
      if (!stored) {
        return DEFAULT_API_ENDPOINT;
      }
      try {
        return normalizeApiEndpoint(stored);
      } catch {
        return DEFAULT_API_ENDPOINT;
      }
    },
    async save(value: string): Promise<string> {
      const endpoint = normalizeApiEndpoint(value);
      await storage.setItemAsync(API_ENDPOINT_KEY, endpoint);
      return endpoint;
    },
  };
}
