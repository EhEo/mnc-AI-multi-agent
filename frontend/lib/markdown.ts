import type { DebateHistory } from "./types";

const ROUND_LABELS: Record<number, string> = {
  0: "Round 0 — 초기 의견",
  1: "Round 1 — 상호 비판",
  2: "Round 2 — 최종 입장",
};

export function toMarkdown(h: DebateHistory): string {
  const date = new Date(h.timestamp).toLocaleString("ko-KR");
  const consensus = h.verdict?.consensus_level ?? "—";
  const lines: string[] = [
    `# ${h.question}`,
    ``,
    `> ${date} | 합의 수준 ${consensus}% | 총 토큰 ${h.totalTokens} | ${(h.durationMs / 1000).toFixed(1)}s`,
    ``,
    `---`,
    ``,
  ];

  // 라운드별 전문가 발언
  const roundNums = Array.from(
    new Set(h.experts.flatMap((e) => Object.keys(e.rounds).map(Number)))
  ).sort((a, b) => a - b);

  for (const round of roundNums) {
    lines.push(`## ${ROUND_LABELS[round] ?? `Round ${round}`}`);
    lines.push(``);
    for (const expert of h.experts) {
      const text = expert.rounds[round];
      if (!text) continue;
      lines.push(`### ${expert.meta.name}`);
      lines.push(``);
      lines.push(text.trim());
      lines.push(``);
    }
  }

  // Judge 최종 판정
  if (h.verdict) {
    lines.push(`---`);
    lines.push(``);
    lines.push(`## ⚖️ 최종 판정`);
    lines.push(``);
    lines.push(h.verdict.final_answer.trim());
    lines.push(``);

    if (h.verdict.reasoning) {
      lines.push(`### 판정 근거`);
      lines.push(``);
      lines.push(h.verdict.reasoning.trim());
      lines.push(``);
    }

    if (h.verdict.dismissed_experts.length > 0) {
      lines.push(`> 탈락 전문가: ${h.verdict.dismissed_experts.join(", ")}`);
      lines.push(``);
    }
  }

  return lines.join("\n");
}

export function downloadMarkdown(h: DebateHistory): void {
  const content = toMarkdown(h);
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const slug = h.question.slice(0, 30).replace(/\s+/g, "_").replace(/[^\w가-힣]/g, "");
  a.download = `debate_${slug}_${h.id}.md`;
  a.click();
  URL.revokeObjectURL(url);
}
