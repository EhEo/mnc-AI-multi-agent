# Multi-LLM 3인 전문가 토론 시스템

Claude + GPT + Gemini 세 개의 LLM이 각자 전문가 역할로 토론(Debate)하고,
독립된 4번째 Judge LLM이 최종 결론을 도출하는 시스템입니다.

## 구조

```text
backend/   FastAPI + Python (asyncio) — 토론 엔진, SSE 스트리밍
frontend/  Next.js + TypeScript       — 실시간 토론 UI
```

## 빠른 시작

### 백엔드

```bash
cd backend
pip install -e ".[dev]"
cp .env.example .env   # API 키 입력
uvicorn app.main:app --reload
```

### 프런트엔드

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

브라우저에서 `http://localhost:3000` 접속 후 질문 입력.

## 토론 프로토콜

| 단계 | 설명 |
| --- | --- |
| Round 0 — Opening | 3인이 독립적으로 초기 의견 제시 |
| Round 1 — Critique | 서로의 의견을 보고 비판/보완 |
| Round 2 — Final | 최종 입장 정리 |
| Judge Verdict | 독립 LLM이 합의문·최종 답변 작성 |

## 환경변수

`.env.example` 참고. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` 필수.

Kilo 단일 키 모드로 세 전문가를 모두 운영하는 경우:

```bash
KILO_API_KEY=...
EXPERT1_PROVIDER=kilo
EXPERT1_MODEL=openai/gpt-4o-mini
EXPERT2_PROVIDER=kilo
EXPERT2_MODEL=anthropic/claude-opus-4-7
EXPERT3_PROVIDER=kilo
EXPERT3_MODEL=google/gemini-2.0-flash   # gemini-3.1-pro-preview는 응답 절단 이슈 있음
```

## 알려진 이슈

| 증상 | 원인 | 해결 |
| --- | --- | --- |
| Gemini 응답이 라운드가 올라갈수록 짧아짐 | Kilo는 요청당 전체 토큰(입력+출력)을 과금하므로, 라운드가 쌓여 prior_turns가 길어지면 출력 할당이 줄어듦 | `prompts.py`의 `_MAX_TURN_CHARS`(기본 2000자)로 각 이전 발언을 잘라 입력 크기 제한. 또는 `google/gemini-2.0-flash`로 모델 교체 |
| Gemini 응답이 20–40 토큰 후 멈춤 | `google/gemini-3.1-pro-preview` 모델의 Kilo 통합 이슈 | `.env`에서 `EXPERT3_MODEL=google/gemini-2.0-flash`로 변경 |
| 오류 발생 후 커서가 계속 깜빡임 | 에러 이벤트 수신 시 스트리밍 상태 미정리 | 수정 완료 (`error` 핸들러에서 `streamingExperts` 초기화) |

---

## 원본 지침 (단일 LLM 버전 — 참고용)

이 프로젝트는 아래 단일 LLM 지침을 Multi-LLM Debate+Judge 방식으로 확장한 것입니다.

> Follow these guidelines without exception.
>
> 1. Think step by step.
> 2. Use a Tree of Thought collaboration process for problem-solving:
>    - Three experts with different perspectives approach the problem.
>    - Each expert uses their own unique method.
>    - At each stage, they share one step of their thinking.
>    - After hearing the others, each expert may adjust their direction.
>    - If an expert is deemed to be heading the wrong way, that expert is eliminated.
>    - Ultimately, derive the most promising solution.
> 3. Based on the user's question, identify and adopt the most appropriate expert role and answer thoroughly.
>    - Then, when responding, state the chosen role in the format "Role: [Selected Role]" and answer as that role.
