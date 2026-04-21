"""OpenAI 호환 API면 어디든 연결하는 범용 어댑터.

지원 provider 예시:
  openrouter  — https://openrouter.ai/api/v1
  copilot     — https://api.githubcopilot.com
  kilo        — base_url 직접 지정 (kilocode.ai 설정에서 확인)
  ollama      — http://localhost:11434/v1
  lm_studio   — http://localhost:1234/v1
  custom      — EXPERT_BASE_URL 로 임의 지정
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.agents.base import ExpertAgent
from app.prompts import build_user_message
from app.schemas import Turn

# provider 이름 → 기본 base_url
PROVIDER_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "kilo": "https://api.kilo.ai/api/gateway",
    "ollama": "http://localhost:11434/v1",
    "lm_studio": "http://localhost:1234/v1",
}


class GenericOpenAICompatibleExpert(ExpertAgent):
    """OpenAI 호환 API를 base_url 교체만으로 연결하는 범용 전문가 어댑터."""

    def __init__(
        self,
        expert_id: str,
        name: str,
        model_id: str,
        role_prompt: str,
        api_key: str,
        base_url: str,
        provider: str = "custom",
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.id = expert_id
        self.name = name
        self.model_id = model_id
        self.role_prompt = role_prompt
        self.provider = provider
        self._extra_headers = extra_headers or {}

        # GitHub Copilot은 "token" 접두사 방식으로 인증하기도 함
        # openai SDK는 Bearer를 자동으로 붙이므로 raw token 값만 전달
        self._client = AsyncOpenAI(
            api_key=api_key or "unused",
            base_url=base_url,
            default_headers=self._extra_headers,
        )

    async def respond(
        self,
        question: str,
        round_num: int,
        prior_turns: list[Turn],
    ) -> AsyncIterator[str]:
        from app.config import settings

        user_msg = build_user_message(question, round_num, prior_turns)
        stream = await self._client.chat.completions.create(
            model=self.model_id,
            max_tokens=settings.max_tokens_per_turn,
            stream=True,
            messages=[
                {"role": "system", "content": self.role_prompt},
                {"role": "user", "content": user_msg},
            ],
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
