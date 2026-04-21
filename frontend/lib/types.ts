// 백엔드 schemas.py의 SSE 이벤트 스키마와 동기화

export interface ExpertMeta {
  id: string;
  name: string;
  model: string;
  provider: string;
}

export interface UsageSummary {
  total_tokens: number;
  duration_ms: number;
}

export interface DebateStartEvent {
  type: "debate_start";
  question: string;
  experts: ExpertMeta[];
  max_rounds: number;
}

export interface RoundStartEvent {
  type: "round_start";
  round: number;
  stage: "opening" | "critique" | "final";
}

export interface ExpertTokenEvent {
  type: "expert_token";
  round: number;
  expert_id: string;
  delta: string;
}

export interface ExpertDoneEvent {
  type: "expert_done";
  round: number;
  expert_id: string;
  full_text: string;
  tokens: number;
}

export interface JudgeTokenEvent {
  type: "judge_token";
  delta: string;
}

export interface JudgeVerdictEvent {
  type: "judge_verdict";
  final_answer: string;
  consensus_level: number;
  dismissed_experts: string[];
  reasoning: string;
  usage: UsageSummary;
}

export interface ErrorEvent {
  type: "error";
  code: string;
  message: string;
}

export interface DebateEndEvent {
  type: "debate_end";
  total_tokens: number;
  duration_ms: number;
}

export type DebateEvent =
  | DebateStartEvent
  | RoundStartEvent
  | ExpertTokenEvent
  | ExpertDoneEvent
  | JudgeTokenEvent
  | JudgeVerdictEvent
  | ErrorEvent
  | DebateEndEvent;

// ── UI 상태 타입 ──────────────────────────────────────────────

export interface ExpertState {
  meta: ExpertMeta;
  rounds: Record<number, string>; // round_num → 누적 텍스트
  currentRound: number;
  isDismissed: boolean;
}

export interface DebateState {
  status: "idle" | "running" | "done" | "error";
  question: string;
  experts: ExpertState[];
  currentRound: number;
  maxRounds: number;
  judgeText: string;
  verdict: JudgeVerdictEvent | null;
  errorMessage: string | null;
  totalTokens: number;
  durationMs: number;
}

export interface DebateHistory {
  id: string;
  timestamp: number;
  question: string;
  experts: ExpertState[];
  verdict: JudgeVerdictEvent | null;
  totalTokens: number;
  durationMs: number;
}
