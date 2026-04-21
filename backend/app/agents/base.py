from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.schemas import ExpertMeta, Turn


class ExpertAgent(ABC):
    """모든 LLM 전문가 어댑터의 공통 인터페이스."""

    id: str           # "claude" | "gpt" | "gemini"
    name: str         # "Claude 분석가" 등
    model_id: str
    provider: str     # "anthropic" | "openai" | "google"
    role_prompt: str  # 전문가 역할 시스템 프롬프트

    @abstractmethod
    async def respond(
        self,
        question: str,
        round_num: int,
        prior_turns: list[Turn],
    ) -> AsyncIterator[str]:
        """토큰 단위 async 스트림을 yield한다."""
        ...  # pragma: no cover

    def meta(self) -> ExpertMeta:
        return ExpertMeta(id=self.id, name=self.name, model=self.model_id, provider=self.provider)
