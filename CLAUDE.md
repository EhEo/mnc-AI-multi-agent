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
