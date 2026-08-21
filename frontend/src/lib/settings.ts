import { useSyncExternalStore } from "react";

export type AppSettings = {
  aiAssistance: boolean;
  liveToasts: boolean;
  autoRefreshMinutes: number; // 0 = off
  compactTables: boolean;
};

const DEFAULTS: AppSettings = {
  aiAssistance: true,
  liveToasts: true,
  autoRefreshMinutes: 0,
  compactTables: false,
};

const STORAGE_KEY = "perigee.settings";

function load(): AppSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<AppSettings>;
    return { ...DEFAULTS, ...parsed };
  } catch {
    return DEFAULTS;
  }
}

let current: AppSettings = load();
const listeners = new Set<() => void>();

export const settingsStore = {
  get: (): AppSettings => current,
  set(patch: Partial<AppSettings>): void {
    current = { ...current, ...patch };
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(current));
    } catch {
      // Private-mode browsers may block persistence; settings stay session-only.
    }
    listeners.forEach((listener) => listener());
  },
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

export function useSettings(): [AppSettings, (patch: Partial<AppSettings>) => void] {
  const value = useSyncExternalStore(settingsStore.subscribe, settingsStore.get);
  return [value, settingsStore.set];
}
