from __future__ import annotations

from collections.abc import AsyncIterator

import anthropic

from app.agents.base import ExpertAgent
from app.config import settings
from app.prompts import CLAUDE_ROLE, build_user_message
from app.schemas import Turn


class ClaudeExpert(ExpertAgent):
    id = "claude"
    name = "Claude 비판적 분석가"
    provider = "anthropic"
    role_prompt = CLAUDE_ROLE

    def __init__(self) -> None:
        self.model_id = settings.claude_model
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def respond(
        self,
        question: str,
        round_num: int,
        prior_turns: list[Turn],
    ) -> AsyncIterator[str]:
        user_msg = build_user_message(question, round_num, prior_turns)
        async with self._client.messages.stream(
            model=self.model_id,
            max_tokens=settings.max_tokens_per_turn,
            system=self.role_prompt,
            messages=[{"role": "user", "content": user_msg}],
        ) as stream:
            async for delta in stream.text_stream:
                yield delta
