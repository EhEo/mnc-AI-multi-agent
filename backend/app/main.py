from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.config import settings
from app.orchestrator import DebateOrchestrator
from app.schemas import DebateRequest

app = FastAPI(title="Multi-LLM Debate API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.post("/api/debate")
async def debate(req: DebateRequest) -> StreamingResponse:
    """
    SSE 스트리밍으로 3인 토론 + Judge 판정을 전달한다.
    클라이언트는 fetch + ReadableStream reader로 구독한다.
    """
    orchestrator = DebateOrchestrator()

    async def event_stream():
        try:
            async for frame in orchestrator.run(req.question):
                yield frame
        except Exception as exc:
            import json
            yield f'data: {json.dumps({"type":"error","code":"internal","message":str(exc)})}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
