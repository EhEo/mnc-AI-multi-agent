from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator

from app.agents.base import ExpertAgent

logger = logging.getLogger(__name__)
from app.agents.claude_expert import ClaudeExpert
from app.agents.gemini_expert import GeminiExpert
from app.agents.generic_expert import PROVIDER_BASE_URLS, GenericOpenAICompatibleExpert
from app.agents.gpt_expert import GPTExpert
from app.agents.judge import JudgeAgent
from app.config import settings
from app.prompts import CLAUDE_ROLE, GEMINI_ROLE, GPT_ROLE
from app.schemas import (
    DebateEndEvent,
    DebateStartEvent,
    ExpertDoneEvent,
    ExpertTokenEvent,
    JudgeTokenEvent,
    RoundStage,
    RoundStartEvent,
    Transcript,
    Turn,
)
from app.sse import format_sse

_ROUND_STAGES: list[RoundStage] = [
    RoundStage.OPENING,
    RoundStage.CRITIQUE,
    RoundStage.FINAL,
]


def _build_experts() -> list[ExpertAgent]:
    """config 기반으로 expert 목록을 동적 생성.

    EXPERT1/2/3_PROVIDER가 비어 있으면 direct API(기존 방식) 사용.
    값이 있으면 GenericOpenAICompatibleExpert로 위임.
    """
    _DEFAULT_ROLES = [CLAUDE_ROLE, GPT_ROLE, GEMINI_ROLE]
    _DEFAULT_NAMES = ["Claude 비판적 분석가", "GPT 실용적 문제해결사", "Gemini 창의적 종합가"]
    _DEFAULT_IDS = ["claude", "gpt", "gemini"]

    experts: list[ExpertAgent] = []
    for num in (1, 2, 3):
        provider = settings.expert_provider(num)

        if not provider:
            # .env에 EXPERT{num}_PROVIDER 미설정 → 기존 direct 어댑터 사용
            if num == 1:
                experts.append(ClaudeExpert())
            elif num == 2:
                experts.append(GPTExpert())
            else:
                experts.append(GeminiExpert())
            continue

        model = settings.expert_model(num)
        api_key = settings.expert_api_key(num)
        base_url = settings.expert_base_url(num)
        name = settings.expert_name(num) or _DEFAULT_NAMES[num - 1]
        role = _DEFAULT_ROLES[num - 1]
        expert_id = _DEFAULT_IDS[num - 1]

        # provider별 기본 키 폴백
        if not api_key:
            if provider == "openai":
                api_key = settings.openai_api_key
            elif provider == "openrouter":
                api_key = settings.openrouter_api_key
            elif provider == "kilo":
                api_key = settings.kilo_api_key
            elif provider == "direct_anthropic":
                api_key = settings.anthropic_api_key

        # provider별 기본 base_url 폴백
        if not base_url:
            base_url = PROVIDER_BASE_URLS.get(provider, "")

        # direct_anthropic / direct_gemini는 generic이 아닌 전용 어댑터 사용
        if provider == "direct_anthropic":
            experts.append(ClaudeExpert())
        elif provider == "direct_gemini":
            experts.append(GeminiExpert())
        else:
            experts.append(
                GenericOpenAICompatibleExpert(
                    expert_id=expert_id,
                    name=name,
                    model_id=model,
                    role_prompt=role,
                    api_key=api_key,
                    base_url=base_url,
                    provider=provider,
                )
            )

    return experts


class DebateOrchestrator:
    def __init__(self, experts: list[ExpertAgent] | None = None) -> None:
        self._experts: list[ExpertAgent] = experts or _build_experts()
        self._judge = JudgeAgent()

    async def run(self, question: str) -> AsyncIterator[str]:
        """질문을 받아 SSE 프레임 문자열 스트림을 yield한다."""
        start_ms = _now_ms()
        transcript = Transcript()
        max_rounds = min(settings.max_rounds, len(_ROUND_STAGES))

        yield format_sse(
            DebateStartEvent(
                question=question,
                experts=[e.meta() for e in self._experts],
                max_rounds=max_rounds,
            )
        )

        for round_num in range(max_rounds):
            if transcript.total_tokens() >= settings.session_token_budget:
                break

            yield format_sse(RoundStartEvent(round=round_num, stage=_ROUND_STAGES[round_num]))
            prior_turns = transcript.before_round(round_num)

            for expert in self._experts:
                async for item in self._stream_expert_frames(
                    expert, question, round_num, prior_turns
                ):
                    if isinstance(item, str):
                        yield item
                    else:
                        turn, done_frame = item
                        transcript.add(turn)
                        yield done_frame

        async for judge_frame in self._run_judge(question, transcript, start_ms):
            yield judge_frame

        yield format_sse(
            DebateEndEvent(
                total_tokens=transcript.total_tokens(),
                duration_ms=_now_ms() - start_ms,
            )
        )

    async def _stream_expert_frames(
        self,
        expert: ExpertAgent,
        question: str,
        round_num: int,
        prior_turns: list[Turn],
    ) -> AsyncIterator[str | tuple[Turn, str]]:
        """전문가 토큰 SSE 프레임을 yield하고, 마지막에 (Turn, done_frame) 튜플을 yield.

        expert.respond()가 예외를 던지더라도 ExpertDoneEvent는 반드시 전송한다.
        이를 통해 프론트엔드의 streamingExperts 상태가 절대 고착되지 않도록 보장한다.
        """
        full_text = ""
        try:
            async for delta in expert.respond(question, round_num, prior_turns):
                full_text += delta
                yield format_sse(ExpertTokenEvent(round=round_num, expert_id=expert.id, delta=delta))
        except Exception:
            logger.exception(
                "Expert %s failed in round %d — sending done with partial text (%d chars)",
                expert.id,
                round_num,
                len(full_text),
            )

        turn = Turn(
            expert_id=expert.id,
            expert_name=expert.name,
            round_num=round_num,
            text=full_text,
            # 근사치 토큰 카운트 (실제 SDK 토큰과 다를 수 있음)
            tokens=len(full_text.split()),
        )
        yield turn, format_sse(
            ExpertDoneEvent(
                round=round_num,
                expert_id=expert.id,
                full_text=full_text,
                tokens=turn.tokens,
            )
        )

    async def _run_judge(
        self,
        question: str,
        transcript: Transcript,
        start_ms: int,
    ) -> AsyncIterator[str]:
        duration = _now_ms() - start_ms
        async for delta, verdict in self._judge.run(question, transcript.turns, duration):
            if delta is not None:
                yield format_sse(JudgeTokenEvent(delta=delta))
            if verdict is not None:
                yield format_sse(verdict)


def _now_ms() -> int:
    return int(time.monotonic() * 1000)
