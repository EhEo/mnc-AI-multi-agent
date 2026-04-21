// EventSource는 GET만 지원하므로, fetch + ReadableStream reader로 POST SSE를 구독한다.

import type { DebateEvent } from "./types";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export async function startDebate(
  question: string,
  onEvent: (event: DebateEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${BACKEND_URL}/api/debate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
    signal,
  });

  if (!response.ok) {
    throw new Error(`Backend error: ${response.status} ${response.statusText}`);
  }

  if (!response.body) {
    throw new Error("No response body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() ?? "";

      for (const chunk of lines) {
        const line = chunk.trim();
        if (!line.startsWith("data: ")) continue;
        const json = line.slice("data: ".length);
        try {
          const event = JSON.parse(json) as DebateEvent;
          onEvent(event);
        } catch {
          // JSON 파싱 실패 시 무시
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
