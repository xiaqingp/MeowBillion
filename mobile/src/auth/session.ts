const SESSION_KEY = 'meowbillion.mobile.session';

export type MobileSession = {
  accessToken: string;
  user: {
    id: string;
    displayName: string;
  };
};

export type SecureStorage = {
  getItemAsync(key: string): Promise<string | null>;
  setItemAsync(key: string, value: string): Promise<void>;
  deleteItemAsync(key: string): Promise<void>;
};

export function createSessionStore(storage: SecureStorage) {
  return {
    async load(): Promise<MobileSession | null> {
      const raw = await storage.getItemAsync(SESSION_KEY);
      if (!raw) {
        return null;
      }
      try {
        return JSON.parse(raw) as MobileSession;
      } catch {
        await storage.deleteItemAsync(SESSION_KEY);
        return null;
      }
    },
    async save(session: MobileSession): Promise<void> {
      await storage.setItemAsync(SESSION_KEY, JSON.stringify(session));
    },
    async clear(): Promise<void> {
      await storage.deleteItemAsync(SESSION_KEY);
    },
  };
}
