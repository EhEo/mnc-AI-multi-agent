import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ExpertMeta } from "@/lib/types";

const PROVIDER_COLORS: Record<string, string> = {
  anthropic: "border-orange-400 bg-orange-50",
  openai:    "border-green-400 bg-green-50",
  google:    "border-blue-400 bg-blue-50",
  fake:      "border-gray-300 bg-gray-50",
};

const PROVIDER_BADGE: Record<string, string> = {
  anthropic: "bg-orange-100 text-orange-700",
  openai:    "bg-green-100 text-green-700",
  google:    "bg-blue-100 text-blue-700",
};

interface Props {
  expert: ExpertMeta;
  rounds: Record<number, string>;
  selectedRound: number;
  streamingRound: number | null; // 현재 스트리밍 중인 라운드 번호, 아니면 null
  isDismissed: boolean;
}

export function ExpertStream({ expert, rounds, selectedRound, streamingRound, isDismissed }: Props) {
  const borderColor = PROVIDER_COLORS[expert.provider] ?? "border-gray-300 bg-gray-50";
  const badge = PROVIDER_BADGE[expert.provider] ?? "bg-gray-100 text-gray-700";

  const text = rounds[selectedRound] ?? "";
  const hasContent = selectedRound in rounds;
  const showCursor = streamingRound === selectedRound && hasContent;

  return (
    <div className={`rounded-xl border-2 p-4 h-full transition-opacity ${borderColor} ${isDismissed ? "opacity-40" : "opacity-100"}`}>
      {/* 헤더 */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm text-gray-800">{expert.name}</span>
          {isDismissed && (
            <span className="rounded px-1.5 py-0.5 text-xs bg-red-100 text-red-600">탈락</span>
          )}
        </div>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${badge}`}>
          {expert.model}
        </span>
      </div>

      {/* 내용 */}
      {!hasContent ? (
        <p className="text-sm text-gray-400 italic min-h-15 flex items-center">
          {streamingRound !== null ? "발언 대기 중..." : "대기 중..."}
        </p>
      ) : (
        <div className="text-sm text-gray-800 leading-relaxed prose prose-sm max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
          {showCursor && (
            <span className="inline-block w-1.5 h-4 bg-gray-500 animate-pulse ml-0.5 align-middle" />
          )}
        </div>
      )}
    </div>
  );
}
