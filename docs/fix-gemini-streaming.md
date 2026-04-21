# Fix: Gemini 스트리밍 응답 끊김 버그

## 문제 설명

Gemini(3번째 전문가)의 응답이 중간에 끊기거나 전혀 출력되지 않는 현상이 발생했다.
토론이 끝난 후에도 Gemini 패널이 "발언 중..." 상태로 고착되는 문제도 동반되었다.

---

## 근본 원인 분석

단일 원인이 아닌 **세 가지 원인이 복합적으로 작용**하고 있었다.

### 원인 1 — Gemini SDK의 침묵적 실패 (가장 유력)

**파일**: `backend/app/agents/gemini_expert.py`

```python
# 수정 전
async for chunk in await self._client.aio.models.generate_content_stream(...):
    if chunk.text:
        yield chunk.text  # chunk.text=None이면 조용히 통과, 예외도 처리 안 함
```

Gemini API가 토큰 제한(max_output_tokens=1500)에 도달하거나 네트워크 오류가 발생하면
`chunk.text = None`을 반환하거나 예외를 던진다. 기존 코드는 두 경우 모두 **로그 없이
무시(silent failure)** 했다. 특히 예외 발생 시에는 스트림이 중단되어 `ExpertDoneEvent`가
전송되지 않는 상황으로 이어졌다.

### 원인 2 — ExpertDoneEvent 송출 미보장

**파일**: `backend/app/orchestrator.py`

```python
# 수정 전
async def _stream_expert_frames(self, expert, ...):
    full_text = ""
    async for delta in expert.respond(...):  # 여기서 예외 발생 시
        full_text += delta
        yield ExpertTokenEvent(...)

    # 예외로 루프가 중단되면 아래 코드가 실행되지 않음
    yield turn, ExpertDoneEvent(...)  # ← 미송출!
```

`expert.respond()`가 예외를 던지면 `async for` 루프가 중단되고, 이후의
`ExpertDoneEvent` yield 코드가 **실행되지 않는다**. 프론트엔드는 이 이벤트를 받아야만
`streamingExperts` Set에서 해당 전문가를 제거하므로, 이벤트가 오지 않으면
**UI가 영구적으로 "발언 중..." 상태**로 고착된다.

### 원인 3 — 프론트엔드 안전망 부재

**파일**: `frontend/app/page.tsx`

`debate_end` 이벤트(토론 전체 종료)를 수신해도 `streamingExperts` 상태를 정리하는
로직이 없었다. `expert_done` 이벤트가 유실된 경우 토론이 끝난 후에도
"발언 중..." UI가 남아있게 된다.

---

## 수정 내용

### 1. `backend/app/agents/gemini_expert.py`

- `try/except` 블록으로 스트리밍 루프 전체를 감쌌다.
- `chunk.text`가 None인 경우 DEBUG 레벨 로그를 남긴다(토큰 제한 도달 여부 추적용).
- 예외 발생 시 `logger.exception`으로 기록한 뒤 `raise`로 재전파한다.
  orchestrator가 최종 catch를 담당하도록 책임을 분리했다.

```python
# 수정 후
try:
    async for chunk in await self._client.aio.models.generate_content_stream(...):
        if chunk.text:
            yield chunk.text
        else:
            logger.debug("Gemini chunk with no text (round=%d): %r", round_num, chunk)
except Exception:
    logger.exception("Gemini streaming error (round=%d)", round_num)
    raise
```

### 2. `backend/app/orchestrator.py`

- `_stream_expert_frames` 내부의 `expert.respond()` 루프를 `try/except`로 감쌌다.
- 예외가 발생해도 `full_text`(부분 응답)를 보존하고, 루프 밖에서 `ExpertDoneEvent`를
  **항상 전송**한다.
- 예외 발생 시 expert ID, 라운드 번호, 누적 텍스트 길이를 로그에 기록한다.

```python
# 수정 후
async def _stream_expert_frames(self, expert, question, round_num, prior_turns):
    full_text = ""
    try:
        async for delta in expert.respond(question, round_num, prior_turns):
            full_text += delta
            yield format_sse(ExpertTokenEvent(...))
    except Exception:
        logger.exception(
            "Expert %s failed in round %d — sending done with partial text (%d chars)",
            expert.id, round_num, len(full_text),
        )

    # 예외 발생 여부와 무관하게 항상 실행된다
    turn = Turn(...)
    yield turn, format_sse(ExpertDoneEvent(..., full_text=full_text))
```

### 3. `frontend/app/page.tsx`

- `debate_end` 이벤트 처리 시 `setStreamingExperts(new Set())`와
  `setJudgeStreaming(false)`를 추가했다.
- 정상 케이스에서는 이미 `expert_done`으로 정리되어 있으므로 무해하다.
- `expert_done` 이벤트가 유실된 비정상 케이스에서만 효과를 발휘하는 **안전망**이다.

```typescript
// 수정 후
case "debate_end": {
    // expert_done 이벤트가 유실됐을 경우의 안전망
    setStreamingExperts(new Set());
    setJudgeStreaming(false);
    // ... 기존 로직
}
```

---

## 수정 전후 동작 비교

| 상황 | 수정 전 | 수정 후 |
|---|---|---|
| Gemini API 예외 발생 | silent failure, `expert_done` 미송출 | 로그 기록 후 `expert_done` 송출(부분 응답 포함) |
| `chunk.text = None` | 조용히 무시 | DEBUG 로그 기록 후 무시 |
| "발언 중..." 고착 | 토론 끝나도 UI 고착 | `debate_end` 수신 시 강제 정리 |
| 다음 라운드 진행 | 고착 상태로 라운드 전환 불가 | 부분 응답이라도 저장하고 정상 진행 |

---

## 영향 범위

- `ClaudeExpert`, `GPTExpert`, `GenericOpenAICompatibleExpert`도
  orchestrator의 `try/except` 덕분에 동일한 보호를 받는다.
- 기존 정상 동작 경로(예외 없음)에는 성능 영향이 없다.
