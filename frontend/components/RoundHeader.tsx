const STAGE_LABELS: Record<string, string> = {
  opening: "Round 0 — 초기 의견",
  critique: "Round 1 — 상호 비판",
  final: "Round 2 — 최종 입장",
};

interface Props {
  round: number;
  stage: string;
}

export function RoundHeader({ round, stage }: Props) {
  return (
    <div className="flex items-center gap-3 my-4">
      <div className="h-px flex-1 bg-gray-200" />
      <span className="rounded-full bg-blue-100 px-4 py-1 text-xs font-semibold text-blue-700">
        {STAGE_LABELS[stage] ?? `Round ${round}`}
      </span>
      <div className="h-px flex-1 bg-gray-200" />
    </div>
  );
}
