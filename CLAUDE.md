# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-LLM expert debate system: 3 LLM experts (Claude/GPT/Gemini) debate a question across 3 rounds, then an independent 4th Judge LLM synthesizes a final verdict. Streamed over SSE from a FastAPI backend to a Next.js frontend.

## Commands

### Backend (run from `backend/`)

```bash
# Install (editable + dev deps)
pip install -e ".[dev]"

# Run server
python -m uvicorn app.main:app --reload --port 8000

# Tests
python -m pytest tests/ -q
python -m pytest tests/test_orchestrator.py -q   # single file

# Lint
python -m ruff check app/
python -m ruff check app/ --fix                   # auto-fix

# Manual SSE test (server must be running)
python test_server.py "질문 내용"
```

> **Windows**: Use full path `C:/Users/MISTOP/AppData/Local/Programs/Python/Python313/python.exe` — the `python` command is not on PATH.

### Frontend (run from `frontend/`)

```bash
npm run dev        # dev server on :3000
npm run build
npm run lint
npx tsc --noEmit   # type check
```

## Architecture

```
POST /api/debate  →  DebateOrchestrator.run()  →  SSE stream
                          │
                    _build_experts()   ←  .env config
                          │
          ┌───────────────┼───────────────┐
     Expert1           Expert2        Expert3
   (round 0-2)      (round 0-2)    (round 0-2)
          └───────────────┼───────────────┘
                     JudgeAgent
                    (full transcript)
```

**Round stages**: `opening` → `critique` → `final` (controlled by `MAX_ROUNDS` env var, capped at 3).

Each expert streams tokens sequentially (not parallel) per round — this preserves SSE ordering so the frontend can display one expert at a time.

### Expert Agent Selection (`orchestrator._build_experts()`)

`EXPERT{n}_PROVIDER` in `.env` controls which adapter is instantiated:

| PROVIDER value | Adapter used |
|---|---|
| *(empty)* | `ClaudeExpert` / `GPTExpert` / `GeminiExpert` (native SDKs) |
| `direct_anthropic` | `ClaudeExpert` |
| `direct_gemini` | `GeminiExpert` |
| `openai`, `kilo`, `openrouter`, `ollama`, `lm_studio`, `custom` | `GenericOpenAICompatibleExpert` |

`GenericOpenAICompatibleExpert` uses `AsyncOpenAI(base_url=..., api_key=...)` — same code path for all OpenAI-compatible providers. `PROVIDER_BASE_URLS` in `generic_expert.py` maps provider names to default base URLs.

API key fallback order (if `EXPERT{n}_API_KEY` is empty): `openai` → `OPENAI_API_KEY`, `kilo` → `KILO_API_KEY`, `openrouter` → `OPENROUTER_API_KEY`.

### SSE Contract

All events are `data: {JSON}\n\n` frames. The TypeScript `DebateEvent` union in `frontend/lib/types.ts` must stay in sync with the Pydantic models in `backend/app/schemas.py`. The frontend uses `fetch` + `ReadableStream` reader — **not** `EventSource` — because the endpoint is POST.

### Judge Provider Dispatch (`agents/judge.py`)

Judge supports: `anthropic` | `openai` | `google` | `kilo` | `openrouter`. The `kilo` and `openrouter` branches reuse `_stream_openai_compat()`. Default fallback is `google`.

### Prompts (`app/prompts.py`)

Expert roles are fixed per position (1=Critical Analyst, 2=Pragmatic Solver, 3=Creative Synthesizer). `ROUND_INSTRUCTIONS` dict maps round number to additional per-round directive injected via `build_user_message()`.

Each prior turn is trimmed to `_MAX_TURN_CHARS` (2000 chars ≈ 500 tokens) before being injected into the prompt. This prevents context explosion in later rounds and preserves output-token budget for providers like Kilo that bill on total tokens per request.

## Configuration (`.env`)

Copy `backend/.env.example` → `backend/.env`. Key variables:

```bash
# Required for default (direct API) mode
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
GOOGLE_API_KEY=...

# Kilo single-key mode (replaces all three above)
KILO_API_KEY=...
EXPERT1_PROVIDER=kilo
EXPERT1_MODEL=openai/gpt-4o-mini
EXPERT2_PROVIDER=kilo
EXPERT2_MODEL=anthropic/claude-opus-4-7
EXPERT3_PROVIDER=kilo
EXPERT3_MODEL=google/gemini-3.1-pro-preview   # exact Kilo model ID, use dots not hyphens

JUDGE_PROVIDER=anthropic   # anthropic | openai | google | kilo | openrouter
JUDGE_MODEL=claude-opus-4-7

MAX_ROUNDS=3
MAX_TOKENS_PER_TURN=1500
SESSION_TOKEN_BUDGET=50000
ALLOWED_ORIGINS=http://localhost:3000
```

Frontend needs `frontend/.env.local` with `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`.

## Known Issues

- **Gemini via Kilo truncates responses** — `google/gemini-3.1-pro-preview` on Kilo outputs 20–40 tokens then stops. Root cause: Kilo bills on total tokens per request; as `prior_turns` grows across rounds the input consumes most of the budget, leaving little room for output. Mitigation applied: `_MAX_TURN_CHARS = 2000` in `prompts.py` trims each prior turn before injection. If truncation persists, switch to a model that handles long context better (e.g. `google/gemini-2.0-flash`) or increase `MAX_TOKENS_PER_TURN`.
- **Pyright `reportMissingImports`** — false positives for all `app.*` and third-party imports because Pyright doesn't see the virtualenv. These resolve after `pip install -e ".[dev]"` in the correct environment; ignore in IDE.
- **Windows port reuse** — `uvicorn --reload` child processes survive `Ctrl-C`; find the listening PID with `netstat -ano | grep :8000` and kill via `cmd.exe /c "taskkill /PID <n> /F"`.

## Frontend Behaviour Notes

### Round tab auto-advance

The selected round tab advances automatically to keep pace with the live debate. The advance fires 700 ms after `round_start` (not on the first token of the new round). `round_start` is emitted by the backend only after all experts in the previous round have finished (`expert_done`), so the 700 ms window lets users see the last expert's completed response before the view moves forward.

### `expert_done` state sync

When the backend emits `expert_done`, the frontend overwrites the stored round text with `full_text` from the event. This corrects any gaps caused by dropped SSE chunks and guarantees the displayed text matches the authoritative server-side accumulation.

### Error recovery

On receiving an `error` SSE event the frontend clears `streamingExperts` so blinking cursors do not persist after a backend failure.

## Frontend Note

The frontend uses **Next.js 16 + React 19**, which has breaking API changes from older versions. Before modifying frontend code, check `node_modules/next/dist/docs/` for current conventions (see `frontend/AGENTS.md`).


---

# CLAUDE.md — orchestration policy

You are the **PM + Coder** in a 3-agent team.

| Role | Invocation |
|---|---|
| **PM + Coder** (you) | this session |
| **Researcher** (Gemini) | `.agents-dev/scripts/debate-gemini.sh r1 "question" <outfile>` |
| **Reviewer** (Codex) | `.agents-dev/scripts/debate-codex.sh r1 "focus" <outfile>` |

You are the **central router**. Codex and Gemini never call each other — when Codex returns a `NEED RESEARCH` block, you fetch the answers from Gemini and re-invoke Codex with the research attached.

## 질문·보고서 요청 시 — Gemini·Codex 다중 AI 소통 흐름 (기본 동작)

사용자가 **분석·조사·보고서·전략** 등 지식 기반 질문을 하면, 단독으로 답변하지 않고 아래 흐름을 따른다.

### 흐름 개요

```
사용자 질문
    │
    ▼
[Claude] 웹 리서치 + 1차 분석
    │
    ├──► [Gemini] debate-gemini.sh r1 "질문" outfile → 심층 조사 답변
    │
    └──► 결과 취합
              │
              ├──► [Codex]  debate-codex.sh r1 "검토 포인트" outfile → 비판·보완
              │
              ▼
        [Claude] 종합 보고서 작성 → 사용자 제시
```

### 단계별 실행 규칙

**1단계 — Claude 1차 리서치**
- WebSearch 등으로 최신 정보 수집
- 핵심 논점 초안 작성

**2단계 — Gemini 심층 조사**
```bash
.agents-dev/scripts/debate-gemini.sh r1 "질문 내용" <outfile>
```
- 조사 결과를 `.agents-dev/log/` 에 자동 저장
- 사용자에게 "Gemini 리서치 중..." 상태 안내

**3단계 — Codex 검토·보완**
```bash
.agents-dev/scripts/debate-codex.sh r1 "질문 내용" <outfile>
```
- Gemini 결과와 Claude 초안에 대한 비판적 검토
- 빠진 관점, 논리 허점, 추가 근거 확인

**4단계 — 종합 결과 제시**
- 각 AI의 주요 의견을 비교·대조 형식으로 정리
- 합의 영역 / 쟁점 영역 / 최종 결론 구조로 사용자에게 보고
- 필요 시 MD·PDF 보고서로 저장

### 토론(Debate) 모드 — 3라운드 교차 토론이 필요할 때

심층 분석이나 보고서 작성 요청에는 `multi-debate.sh` 를 활용한다.

```bash
# 1. 세션 초기화
.agents-dev/scripts/multi-debate.sh "토론 질문"

# 2. Claude R1 답변 작성 후 자동 실행
.agents-dev/scripts/multi-debate-auto.sh <session-dir>
```

- **R1**: Claude·Gemini·Codex 독립 답변
- **R2**: 3자 교차 분석 (동의·반대·추가 의견)
- **R3**: 반론·보충
- **Final**: Claude가 오케스트레이터로서 최종 보고서 자동 생성

### 어떤 질문에 다중 AI 소통을 쓰는가

| 질문 유형 | 적용 여부 | 스크립트 |
|---|---|---|
| 시장 분석·전략 수립 | ✅ 항상 | `multi-debate.sh` |
| 기술 조사·라이브러리 비교 | ✅ 항상 | `debate-gemini.sh r1` |
| 보고서·문서 작성 요청 | ✅ 항상 | `multi-debate.sh` |
| 코드 리뷰 | ✅ 항상 | `debate-codex.sh r1` |
| 단순 파일 조회·grep | ❌ 생략 | 직접 처리 |
| 1줄 수정·오타 교정 | ❌ 생략 | 직접 처리 |

### 사용자에게 진행 상황 안내

각 단계 시작 전 반드시 상태를 안내한다.

```
[1/4] Claude 1차 리서치 중...
[2/4] Gemini 심층 조사 중... (로그: .agents-dev/log/latest-gemini.log)
[3/4] Codex 검토 중... (로그: .agents-dev/log/latest-codex.log)
[4/4] 종합 결과 정리 중...
```

---

## When to call Gemini

Before coding, when you need:
- Library / framework / API behavior you're unsure of
- Recent changes / deprecations / breaking changes
- Spec or RFC details
- Comparison between options ("which approach")

Use `debate-gemini.sh r1 "question" outfile` (single-shot) or the full `multi-debate.sh` flow for multi-round debate.

Skip for things you can verify by reading repo files, `grep`, or a quick test.

## When to call Codex

After completing a logical unit of work:
- Before committing a non-trivial change
- When the user explicitly asks for review

Use `debate-codex.sh r1 "question" outfile` (single-shot) or the full `multi-debate.sh` flow for multi-round debate.

Skip Codex for trivial single-line edits, WIP code mid-feature, or doc-only changes.

## Handling Codex's `NEED RESEARCH`

If Codex output ends with a `## NEED RESEARCH` block:
1. Run `debate-gemini.sh r1` for each question; capture answers to a file.
2. Save the combined answers to `.agents-dev/log/research-<ts>.md`.
3. Re-invoke: `debate-codex.sh r2` with the research context attached.
4. Surface blockers / major findings to the user before continuing.

## Reporting back to the user

- After research: summarize Gemini's key points in 2–4 lines + cite the log path.
- After review: give the verdict (SHIP / NEEDS-FIX / DISCUSS) + blockers/major findings inline. Link the full log; don't dump everything.
- Logs live in `.agents-dev/log/` (gitignored).

## Don't

- Don't call Gemini / Codex from inside an `Agent` subagent — keep orchestration in the main session so the user sees the routing.
- Don't act on `NEEDS-FIX` findings without showing the user first.
- Don't paste secrets / credentials into prompts (both CLIs send to external providers).
