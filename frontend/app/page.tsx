"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ExpertStream } from "@/components/ExpertStream";
import { HistoryPanel } from "@/components/HistoryPanel";
import { JudgmentPanel } from "@/components/JudgmentPanel";
import { QuestionForm } from "@/components/QuestionForm";
import { loadHistory, saveHistory } from "@/lib/history";
import { downloadMarkdown } from "@/lib/markdown";
import { startDebate } from "@/lib/sse-client";
import type {
  DebateEvent,
  DebateHistory,
  DebateState,
  ExpertMeta,
  ExpertState,
  JudgeVerdictEvent,
} from "@/lib/types";

const ROUND_LABELS: Record<number, string> = {
  0: "Round 0 — 초기 의견",
  1: "Round 1 — 상호 비판",
  2: "Round 2 — 최종 입장",
};

function makeExpertState(meta: ExpertMeta): ExpertState {
  return { meta, rounds: {}, currentRound: 0, isDismissed: false };
}

const INITIAL_STATE: DebateState = {
  status: "idle",
  question: "",
  experts: [],
  currentRound: 0,
  maxRounds: 3,
  judgeText: "",
  verdict: null,
  errorMessage: null,
  totalTokens: 0,
  durationMs: 0,
};

export default function Home() {
  const [state, setState] = useState<DebateState>(INITIAL_STATE);
  const [streamingExperts, setStreamingExperts] = useState<Set<string>>(new Set());
  const [judgeStreaming, setJudgeStreaming] = useState(false);
  const [history, setHistory] = useState<DebateHistory[]>([]);
  const [selectedRound, setSelectedRound] = useState(0);
  const abortRef = useRef<AbortController | null>(null);
  const roundAdvanceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setHistory(loadHistory());
  }, []);

  // 타이머 정리 (언마운트 시)
  useEffect(() => {
    return () => {
      if (roundAdvanceTimerRef.current) clearTimeout(roundAdvanceTimerRef.current);
    };
  }, []);

  // 토론 완료 시 히스토리 목록 갱신 (setState 업데이터 내부에서 setHistory 호출 방지)
  useEffect(() => {
    if (state.status === "done") {
      setHistory(loadHistory());
    }
  }, [state.status]);

  const handleEvent = useCallback((event: DebateEvent) => {
    switch (event.type) {
      case "debate_start":
        if (roundAdvanceTimerRef.current) clearTimeout(roundAdvanceTimerRef.current);
        setState((s) => ({
          ...s,
          status: "running",
          question: event.question,
          experts: event.experts.map(makeExpertState),
          maxRounds: event.max_rounds,
          judgeText: "",
          verdict: null,
          errorMessage: null,
        }));
        setSelectedRound(0);
        break;

      case "round_start":
        setState((s) => ({ ...s, currentRound: event.round }));
        // round_start는 이전 라운드의 모든 expert_done 이후에 발생한다.
        // 700ms 지연을 두어 사용자가 Gemini(마지막 전문가)의 완료된 내용을
        // 확인한 뒤 탭이 전환되도록 한다.
        if (event.round > 0) {
          if (roundAdvanceTimerRef.current) clearTimeout(roundAdvanceTimerRef.current);
          roundAdvanceTimerRef.current = setTimeout(() => {
            setSelectedRound((prev) => (event.round > prev ? event.round : prev));
          }, 700);
        }
        break;

      case "expert_token":
        setState((s) => ({
          ...s,
          experts: s.experts.map((e) =>
            e.meta.id === event.expert_id
              ? {
                  ...e,
                  currentRound: event.round,
                  rounds: {
                    ...e.rounds,
                    [event.round]: (e.rounds[event.round] ?? "") + event.delta,
                  },
                }
              : e,
          ),
        }));
        setStreamingExperts((prev) => new Set(prev).add(event.expert_id));
        break;

      case "expert_done":
        // full_text로 덮어써 네트워크 청크 유실 시에도 완전한 텍스트를 보장한다.
        setState((s) => ({
          ...s,
          experts: s.experts.map((e) =>
            e.meta.id === event.expert_id
              ? { ...e, rounds: { ...e.rounds, [event.round]: event.full_text } }
              : e,
          ),
        }));
        setStreamingExperts((prev) => {
          const next = new Set(prev);
          next.delete(event.expert_id);
          return next;
        });
        break;

      case "judge_token":
        setState((s) => ({ ...s, judgeText: s.judgeText + event.delta }));
        setJudgeStreaming(true);
        break;

      case "judge_verdict":
        setState((s) => ({
          ...s,
          verdict: event as JudgeVerdictEvent,
          experts: s.experts.map((e) => ({
            ...e,
            isDismissed: (event as JudgeVerdictEvent).dismissed_experts.includes(e.meta.id),
          })),
        }));
        setJudgeStreaming(false);
        break;

      case "debate_end": {
        // crypto.randomUUID()로 밀리초 충돌 없는 고유 ID 생성
        // 업데이터 외부에서 생성해 StrictMode 이중 호출 시에도 동일 ID 유지
        const entryId = crypto.randomUUID();
        setState((s) => {
          const next = {
            ...s,
            status: "done" as const,
            totalTokens: event.total_tokens,
            durationMs: event.duration_ms,
          };
          const entry: DebateHistory = {
            id: entryId,
            timestamp: Date.now(),
            question: next.question,
            experts: next.experts,
            verdict: next.verdict,
            totalTokens: event.total_tokens,
            durationMs: event.duration_ms,
          };
          saveHistory(entry);
          return next;
        });
        break;
      }

      case "error":
        setState((s) => ({ ...s, status: "error", errorMessage: event.message }));
        setStreamingExperts(new Set());
        setJudgeStreaming(false);
        break;
    }
  }, []);

  const handleSubmit = useCallback(
    async (question: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setState({ ...INITIAL_STATE, status: "running", question });
      setStreamingExperts(new Set());
      setJudgeStreaming(false);

      try {
        await startDebate(question, handleEvent, controller.signal);
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setState((s) => ({
            ...s,
            status: "error",
            errorMessage: (err as Error).message,
          }));
        }
      }
    },
    [handleEvent],
  );

  const isRunning = state.status === "running";

  // 발언이 시작된 라운드 목록 (탭에 표시)
  const availableRounds = Array.from(
    new Set(state.experts.flatMap((e) => Object.keys(e.rounds).map(Number)))
  ).sort((a, b) => a - b);
  if (isRunning && !availableRounds.includes(state.currentRound)) {
    availableRounds.push(state.currentRound);
  }

  function handleSelectHistory(entry: DebateHistory) {
    abortRef.current?.abort();
    const maxRound = Math.max(
      0,
      ...entry.experts.flatMap((e) => Object.keys(e.rounds).map(Number))
    );
    setState({
      ...INITIAL_STATE,
      status: "done",
      question: entry.question,
      experts: entry.experts,
      verdict: entry.verdict,
      judgeText: entry.verdict?.final_answer ?? "",
      totalTokens: entry.totalTokens,
      durationMs: entry.durationMs,
    });
    setSelectedRound(maxRound);
    setStreamingExperts(new Set());
    setJudgeStreaming(false);
  }

  function handleReset() {
    abortRef.current?.abort();
    setState(INITIAL_STATE);
    setStreamingExperts(new Set());
    setJudgeStreaming(false);
    setSelectedRound(0);
  }

  function handleDownloadCurrent() {
    const entry: DebateHistory = {
      id: Date.now().toString(),
      timestamp: Date.now(),
      question: state.question,
      experts: state.experts,
      verdict: state.verdict,
      totalTokens: state.totalTokens,
      durationMs: state.durationMs,
    };
    downloadMarkdown(entry);
  }

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-7xl px-6 py-8">
        {/* 헤더 */}
        <div className="mb-8 text-center relative">
          <h1 className="text-3xl font-bold text-gray-900">🧠 Multi-LLM 전문가 토론</h1>
          <p className="mt-2 text-sm text-gray-500">
            Claude · GPT · Gemini 세 전문가가 토론하고 Judge가 결론을 도출합니다
          </p>
          {state.status !== "idle" && (
            <button
              type="button"
              onClick={handleReset}
              title="새 대화 시작"
              className="absolute right-0 top-0 flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-500 shadow-sm hover:border-gray-300 hover:text-gray-700 transition-colors"
            >
              ✕ 새 대화
            </button>
          )}
        </div>

        {/* 질문 입력 */}
        <div className="mb-6">
          <QuestionForm onSubmit={handleSubmit} disabled={isRunning} />
        </div>

        {/* 히스토리 패널 */}
        <HistoryPanel
          history={history}
          onSelect={handleSelectHistory}
          onHistoryChange={setHistory}
        />

        {/* 에러 */}
        {state.status === "error" && (
          <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            오류: {state.errorMessage}
          </div>
        )}

        {/* 토론 패널 */}
        {state.experts.length > 0 && (
          <>
            {/* 질문 표시 */}
            <div className="mb-4 rounded-lg bg-white border border-gray-200 px-4 py-3">
              <span className="text-xs text-gray-400 mr-2">질문</span>
              <span className="text-sm font-medium text-gray-800">{state.question}</span>
            </div>

            {/* 라운드 탭 */}
            {availableRounds.length > 0 && (
              <div className="flex gap-2 mb-4 border-b border-gray-200">
                {availableRounds.map((round) => {
                  const isActive = selectedRound === round;
                  const isStreaming = isRunning && state.currentRound === round;
                  return (
                    <button
                      key={round}
                      type="button"
                      onClick={() => setSelectedRound(round)}
                      className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                        isActive
                          ? "border-blue-500 text-blue-700"
                          : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                      }`}
                    >
                      {ROUND_LABELS[round] ?? `Round ${round}`}
                      {isStreaming && (
                        <span className="ml-1.5 inline-block w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse align-middle" />
                      )}
                    </button>
                  );
                })}
              </div>
            )}

            {/* 전문가 패널 — 선택된 라운드 횡 비교 */}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3 items-start">
              {state.experts.map((expert) => (
                <ExpertStream
                  key={expert.meta.id}
                  expert={expert.meta}
                  rounds={expert.rounds}
                  selectedRound={selectedRound}
                  streamingRound={
                    streamingExperts.has(expert.meta.id) ? expert.currentRound : null
                  }
                  isDismissed={expert.isDismissed}
                />
              ))}
            </div>

            {/* Judge 판정 */}
            <JudgmentPanel
              judgeText={state.judgeText}
              verdict={state.verdict}
              isStreaming={judgeStreaming}
            />

            {/* 완료 통계 + 저장 */}
            {state.status === "done" && (
              <div className="mt-4 flex items-center justify-center gap-4">
                <span className="text-xs text-gray-400">
                  총 토큰 {state.totalTokens} · {(state.durationMs / 1000).toFixed(1)}s 소요
                </span>
                <button
                  type="button"
                  onClick={handleDownloadCurrent}
                  className="text-xs text-blue-500 hover:text-blue-700 underline"
                >
                  ⬇ 마크다운 저장
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}
