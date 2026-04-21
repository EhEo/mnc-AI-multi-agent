from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator

from app.config import settings
from app.prompts import JUDGE_ROLE, build_judge_message
from app.schemas import JudgeVerdictEvent, Turn, UsageSummary


async def _stream_anthropic(prompt: str) -> AsyncIterator[str]:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    async with client.messages.stream(
        model=settings.judge_model,
        max_tokens=2000,
        system=JUDGE_ROLE,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for delta in stream.text_stream:
            yield delta


async def _stream_openai(prompt: str) -> AsyncIterator[str]:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    stream = await client.chat.completions.create(
        model=settings.judge_model,
        max_tokens=2000,
        stream=True,
        messages=[
            {"role": "system", "content": JUDGE_ROLE},
            {"role": "user", "content": prompt},
        ],
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def _stream_openai_compat(
    prompt: str,
    base_url: str,
    api_key: str,
    extra_headers: dict[str, str] | None = None,
) -> AsyncIterator[str]:
    """OpenAI 호환 엔드포인트 범용 스트리머 (kilo, openrouter 공용)."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        api_key=api_key or "unused",
        base_url=base_url,
        default_headers=extra_headers or {},
    )
    stream = await client.chat.completions.create(
        model=settings.judge_model,
        max_tokens=2000,
        stream=True,
        messages=[
            {"role": "system", "content": JUDGE_ROLE},
            {"role": "user", "content": prompt},
        ],
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def _stream_google(prompt: str) -> AsyncIterator[str]:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=settings.google_api_key)
    async for chunk in await client.aio.models.generate_content_stream(
        model=settings.judge_model,
        contents=f"{JUDGE_ROLE}\n\n{prompt}",
        config=types.GenerateContentConfig(max_output_tokens=2000),
    ):
        if chunk.text:
            yield chunk.text


def _extract_json(raw: str) -> dict:
    """LLM 출력에서 JSON 블록만 추출한다. 마크다운 코드펜스 및 이중 이스케이프 처리."""
    text = raw.strip()

    # 1) 직접 파싱 시도
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2) 마크다운 코드펜스 제거 후 재시도
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3) 최외곽 { } 블록 추출 (중첩 브레이스 안전 처리)
    start = text.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break

    raise ValueError(f"JSON을 찾을 수 없습니다: {raw[:200]}")


class JudgeAgent:
    """전체 transcript를 받아 최종 판정을 스트리밍한다."""

    async def run(
        self,
        question: str,
        turns: list[Turn],
        duration_ms: int,
    ) -> AsyncIterator[tuple[str | None, JudgeVerdictEvent | None]]:
        """
        Yields:
          (delta_text, None)  — 스트리밍 중 토큰
          (None, verdict)     — 완료 후 판정 이벤트
        """
        prompt = build_judge_message(question, turns)
        provider = settings.judge_provider
        full_text = ""

        if provider == "anthropic":
            stream = _stream_anthropic(prompt)
        elif provider == "openai":
            stream = _stream_openai(prompt)
        elif provider == "google":
            stream = _stream_google(prompt)
        elif provider == "kilo":
            api_key = settings.judge_api_key or settings.kilo_api_key
            stream = _stream_openai_compat(prompt, "https://api.kilo.ai/api/gateway", api_key)
        elif provider == "openrouter":
            api_key = settings.judge_api_key or settings.openrouter_api_key
            stream = _stream_openai_compat(prompt, "https://openrouter.ai/api/v1", api_key)
        else:
            stream = _stream_google(prompt)

        async for delta in stream:
            full_text += delta
            yield delta, None

        total_tokens = sum(t.tokens for t in turns)
        try:
            data = _extract_json(full_text)
            verdict = JudgeVerdictEvent(
                final_answer=data.get("final_answer", ""),
                consensus_level=int(data.get("consensus_level", 50)),
                dismissed_experts=data.get("dismissed_experts", []),
                reasoning=data.get("reasoning", ""),
                usage=UsageSummary(total_tokens=total_tokens, duration_ms=duration_ms),
            )
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            verdict = JudgeVerdictEvent(
                final_answer=full_text,
                consensus_level=50,
                dismissed_experts=[],
                reasoning=f"JSON 파싱 오류: {exc}",
                usage=UsageSummary(total_tokens=total_tokens, duration_ms=duration_ms),
            )
        yield None, verdict
