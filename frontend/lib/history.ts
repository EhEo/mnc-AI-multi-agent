import type { DebateHistory } from "./types";

const KEY = "debate_history";
const MAX_ITEMS = 50;

export function loadHistory(): DebateHistory[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const list = JSON.parse(raw) as DebateHistory[];
    // ID 중복 제거 (이전 버전 저장 데이터 대비 방어)
    const seen = new Set<string>();
    return list.filter((h) => {
      if (seen.has(h.id)) return false;
      seen.add(h.id);
      return true;
    });
  } catch {
    return [];
  }
}

export function saveHistory(entry: DebateHistory): void {
  const list = loadHistory();
  // 같은 ID가 이미 존재하면 저장 생략 (StrictMode 이중 호출 방어)
  if (list.some((h) => h.id === entry.id)) return;
  const updated = [entry, ...list].slice(0, MAX_ITEMS);
  localStorage.setItem(KEY, JSON.stringify(updated));
}

export function deleteHistory(id: string): DebateHistory[] {
  const updated = loadHistory().filter((h) => h.id !== id);
  localStorage.setItem(KEY, JSON.stringify(updated));
  return updated;
}

export function clearHistory(): void {
  localStorage.removeItem(KEY);
}
