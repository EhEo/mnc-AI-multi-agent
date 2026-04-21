import json

from pydantic import BaseModel


def format_sse(event: BaseModel) -> str:
    """Pydantic 이벤트를 SSE 프레임 문자열로 변환."""
    return f"data: {event.model_dump_json()}\n\n"


def format_sse_dict(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
