const STORAGE_VERSION = 1;
const PREFIX = 'apos_';

function key(name: string): string {
  return `${PREFIX}v${STORAGE_VERSION}_${name}`;
}

export function loadState<T>(name: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key(name));
    if (raw === null) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function saveState<T>(name: string, value: T): void {
  try {
    localStorage.setItem(key(name), JSON.stringify(value));
  } catch {
    // storage full or unavailable
  }
}
