import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { JudgeVerdictEvent } from "@/lib/types";

// 백엔드 JSON 파싱 실패 시 raw text가 final_answer에 들어올 수 있음 — 여기서 재처리
function cleanMarkdown(text: string): string {
  if (text.trimStart().startsWith("{")) {
    try {
      const data = JSON.parse(text) as Record<string, unknown>;
      if (typeof data.final_answer === "string") return data.final_answer;
    } catch {}
  }
  return text.replace(/\\n/g, "\n");
}

// consensus_level(0~100)을 Tailwind 너비 클래스로 변환
function levelWidthClass(level: number): string {
  const step = Math.round(level / 5) * 5;
  const map: Record<number, string> = {
    0: "w-0", 5: "w-[5%]", 10: "w-[10%]", 15: "w-[15%]", 20: "w-1/5",
    25: "w-1/4", 30: "w-[30%]", 35: "w-[35%]", 40: "w-2/5",
    45: "w-[45%]", 50: "w-1/2", 55: "w-[55%]", 60: "w-3/5",
    65: "w-[65%]", 70: "w-[70%]", 75: "w-3/4", 80: "w-4/5",
    85: "w-[85%]", 90: "w-[90%]", 95: "w-[95%]", 100: "w-full",
  };
  return map[step] ?? "w-1/2";
}

interface Props {
  judgeText: string;
  verdict: JudgeVerdictEvent | null;
  isStreaming: boolean;
}

export function JudgmentPanel({ judgeText, verdict, isStreaming }: Props) {
  if (!judgeText && !verdict) return null;

  const level = verdict?.consensus_level ?? 0;
  const levelColor =
    level >= 70 ? "bg-green-500" : level >= 40 ? "bg-yellow-500" : "bg-red-500";

  return (
    <div className="mt-6 rounded-2xl border-2 border-purple-300 bg-purple-50 p-5">
      <div className="mb-3 flex items-center gap-2">
        <span className="text-lg">⚖️</span>
        <h3 className="font-bold text-purple-800">Judge 최종 판정</h3>
      </div>

      {verdict ? (
        <>
          <div className="text-sm text-gray-800 leading-relaxed mb-4 prose prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {cleanMarkdown(verdict.final_answer)}
            </ReactMarkdown>
          </div>

          <div className="flex items-center gap-3 mb-3">
            <span className="text-xs text-gray-500">합의 수준</span>
            <div className="flex-1 rounded-full bg-gray-200 h-2">
              <div className={`h-2 rounded-full transition-all ${levelColor} ${levelWidthClass(level)}`} />
            </div>
            <span className="text-xs font-semibold text-gray-700">{level}%</span>
          </div>

          {verdict.reasoning && (
            <details className="text-xs text-gray-500">
              <summary className="cursor-pointer hover:text-gray-700">판정 근거</summary>
              <div className="mt-1 pl-2 border-l-2 border-purple-200 prose prose-xs max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {cleanMarkdown(verdict.reasoning)}
                </ReactMarkdown>
              </div>
            </details>
          )}

          <div className="mt-3 text-xs text-gray-400">
            총 토큰 {verdict.usage.total_tokens} · {(verdict.usage.duration_ms / 1000).toFixed(1)}s
          </div>
        </>
      ) : (
        <div className="text-sm text-gray-700 leading-relaxed prose prose-sm max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{judgeText}</ReactMarkdown>
          {isStreaming && (
            <span className="inline-block w-1.5 h-4 bg-purple-500 animate-pulse ml-0.5 align-middle" />
          )}
        </div>
      )}
    </div>
  );
}
