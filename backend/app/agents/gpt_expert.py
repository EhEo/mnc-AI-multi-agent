from __future__ import annotations

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.agents.base import ExpertAgent
from app.config import settings
from app.prompts import GPT_ROLE, build_user_message
from app.schemas import Turn


class GPTExpert(ExpertAgent):
    id = "gpt"
    name = "GPT 실용적 문제해결사"
    provider = "openai"
    role_prompt = GPT_ROLE

    def __init__(self) -> None:
        self.model_id = settings.gpt_model
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def respond(
        self,
        question: str,
        round_num: int,
        prior_turns: list[Turn],
    ) -> AsyncIterator[str]:
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
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
