from __future__ import annotations

from collections.abc import AsyncIterator

from google import genai
from google.genai import types

from app.agents.base import ExpertAgent
from app.config import settings
from app.prompts import GEMINI_ROLE, build_user_message
from app.schemas import Turn


class GeminiExpert(ExpertAgent):
    id = "gemini"
    name = "Gemini 창의적 종합가"
    provider = "google"
    role_prompt = GEMINI_ROLE

    def __init__(self) -> None:
        self.model_id = settings.gemini_model
        self._client = genai.Client(api_key=settings.google_api_key)

    async def respond(
        self,
        question: str,
        round_num: int,
        prior_turns: list[Turn],
    ) -> AsyncIterator[str]:
        user_msg = build_user_message(question, round_num, prior_turns)
        full_prompt = f"{self.role_prompt}\n\n{user_msg}"

        async for chunk in await self._client.aio.models.generate_content_stream(
            model=self.model_id,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=settings.max_tokens_per_turn,
            ),
        ):
            if chunk.text:
                yield chunk.text
